import contextlib
import json
import warnings
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import datetime
from asyncio import QueueEmpty, sleep, gather
from copy import copy
from typing import Any, Dict, List, Tuple, Set, Union
import xarray as xr
import numpy as np

import itertools
from loguru import logger

from daquiri.interlock import InterlockException
from daquiri.utils import RichEncoder
from daquiri.actor import Actor
from daquiri.panels import ExperimentPanel


class AccessRecorder:
    def __init__(self, scope):
        self.path = []
        self.scope = scope

    def __getattr__(self, item):
        self.path.append(item)
        return self

    def __getitem__(self, item):
        self.path.append(item)
        return self

    def write(self, value):
        return {
            'write': value,
            'path': self.path,
            'scope': self.scope
        }

    def read(self):
        return {
            'read': None,
            'path': self.path,
            'scope': self.scope,
        }

    def __call__(self, *args, **kwargs):
        return {
            'call': (args, kwargs),
            'path': self.path,
            'scope': self.scope,
        }

    def full_path_(self):
        return tuple([self.scope] + self.path)


class ScopedAccessRecorder:
    def __init__(self, scope):
        self.scope = scope

    def __getattr__(self, item):
        return getattr(AccessRecorder(self.scope), item)

    def __getitem__(self, item):
        return AccessRecorder(self.scope)[item]


def tokenize_access_path(str_or_list) -> Tuple[Union[str, int]]:
    """
    Turns a string-like accessor into a list of tokens

    a.b[0].c -> ['a', 'b', 0, 'c']

    :param str_or_list:
    :return:
    """
    if isinstance(str_or_list, (tuple, list)):
        return str_or_list

    def safe_unwrap_int(value):
        try:
            return int(value)
        except ValueError:
            return str(value)

    return tuple([safe_unwrap_int(x) for x in str_or_list.replace('[', '.').replace(']', '').split('.') if x])


class FSM(Actor):
    STATE_TABLE = {
        'IDLE': [{
            'match': 'start',
            'to': 'RUNNING'
        }],
        'RUNNING': [{
            'match': 'pause',
            'to': 'PAUSED',
        }],
        'PAUSED': [{
            'match': 'start',
            'to': 'RUNNING',
        }],
    }
    STARTING_STATE = 'IDLE'

    def __init__(self, app):
        super().__init__(app)
        self.state = self.STARTING_STATE
        assert(self.state in self.STATE_TABLE)

    async def transition_to(self, transition, trigger):
        """
        Roughly speaking, we call

        1. A function to transition out of the current state
        2. A function to transition specifically from the current state into the new one
        3. A function to transition into the next state

        1. and 3. represent teardown and setup for the states respectively, and 2.
        can capture and transition specific state logic
        :param transition:
        :param trigger:
        :return:
        """
        from_state = self.state.lower()
        logger.info(f'{transition}, {trigger}')
        to_state = transition['to'].lower()
        try:
            f = getattr(self, f'leave_{from_state}')
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

        try:
            f = getattr(self, f'{from_state}_to_{to_state}')
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

        self.state = transition['to']

        try:
            f = getattr(self, f'enter_{to_state}')
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

    async def fsm_handle_message(self, message):
        """
        First check if there is a transition available in the state table,
        if there is, then perform the transition with the message as context
        and invoke the appropriate transition functions and updating the internal state.

        If there is no transition available, then the message is passed off to the client message
        handler `handle_message`
        :param message:
        :return:
        """
        found_transition = None
        if isinstance(message, str):
            # possible transitions
            for transition in self.STATE_TABLE[self.state]:
                match = transition['match']
                if isinstance(match, str) and match == message:
                    found_transition = transition
                elif callable(match) and match(message):
                    found_transition = transition

                if found_transition:
                    break

        if found_transition is None:
            await self.handle_message(message)
        else:
            await self.transition_to(found_transition, message)

    async def handle_message(self, message):
        """
        Handler for messages not related to state transitions
        :param message:
        :return:
        """
        raise Exception(message)

    async def run(self):
        while True:
            try:
                while True:
                    message = self.messages.get_nowait()
                    await self.fsm_handle_message(message)
                    self.messages.task_done()
            except QueueEmpty:
                f = getattr(self, 'run_{}'.format(self.state.lower()))
                await f()
                # NEVER TRUST THE USER, this ensures we yield back to the scheduler
                await sleep(0)


@dataclass
class Collation:
    independent: Dict[Tuple[Union[str, int]], str] = None
    dependent: Dict[Tuple[Union[str, int]], str] = None

    # contains the min, max, and observed values
    statistics: Dict[str, Tuple[float, float, Set[float]]] = field(default_factory=dict)

    def receive(self, device, value):
        """
        Records statistics and observed values for the given axis, if it is independent
        :param device:
        :param value:
        :return:
        """
        if device in self.independent:
            if device in self.statistics:
                minimum, maximum, seen = self.statistics[device]
            else:
                minimum, maximum, seen = np.inf, -np.inf, set()

            minimum, maximum = min(minimum, value), max(maximum, value)
            seen.add(value)
            self.statistics[device] = (minimum, maximum, seen)

    def internal_axes(self):
        coords = {}
        dims = []
        for full_path, name in self.independent.items():
            dims.append(name)
            coords[name] = np.asarray(sorted(list(self.statistics[full_path][2])))

        return coords, dims

    def template(self, peeked_values):
        common_coords, common_dims = self.internal_axes()
        base_shape = [len(common_coords[d]) for d in common_dims]

        built_empty_arrays = {}
        for k, peeked in peeked_values.items():
            current_dims = list(common_dims)
            current_coords = common_coords.copy()
            current_shape = list(base_shape)

            dtype = np.float64
            if isinstance(peeked, np.ndarray):
                dtype = peeked.dtype

                current_shape = current_shape + list(peeked.shape)
                for i, s in enumerate(peeked.shape):
                    current_dims.append(f'{k}-dim_{i}')
                    current_coords[f'{k}-dim_{i}'] = np.arange(s)

            if k in current_dims:
                k = f'{k}-values'
            built_empty_arrays[k] = xr.DataArray(
                np.zeros(shape=current_shape, dtype=dtype),
                coords=current_coords,
                dims=current_dims,
            )

        return xr.Dataset(built_empty_arrays)

    @classmethod
    def iter_single_group(cls, daq_stream, group_key='point'):
        group = 0
        collected = []
        for daq in daq_stream:
            current_group = daq[group_key]

            if current_group == group:
                collected.append(daq['data'])
            else:
                yield collected
                collected = [daq['data']]
                group = current_group

    @classmethod
    def iter_grouped(cls, daq_values, group_key='point'):
        names = list(daq_values.keys())
        single_streams = [cls.iter_single_group(daq_values[n], group_key=group_key) for n in names]

        for point in zip(*single_streams):
            point = [x[0] if len(x) == 1 else x for x in point]
            yield dict(zip(names, point))

    def to_xarray(self, daq_values, group_key='point'):
        all_names = self.independent.copy()
        all_names.update(self.dependent)
        independent_names = {n: f'{n}-values' for n in self.independent.values()}

        namespaced_daq_values = {all_names[k]: v for k, v in daq_values.items()}

        ds = None
        for point in Collation.iter_grouped(namespaced_daq_values, group_key):
            if ds is None:
                ds = self.template(point)

            iter_coords = {k: v for k, v in point.items() if k in independent_names}

            for k, value in point.items():
                kname = independent_names.get(k, k)
                ds[kname].loc[iter_coords] = value

        return ds

@dataclass
class Run:
    # Configuration/Bookkeeping
    number: int # the current run number
    session: str
    user: str

    config: Any
    sequence: Any

    step: int = 0
    point: int = 0

    # UI Configuration
    additional_plots: List[Dict] = field(default_factory=list)

    # DAQ
    metadata: List[Dict[str, Any]] = field(default_factory=list)
    steps_taken: List[Dict[str, Any]] = field(default_factory=list)
    point_started: List[Dict[str, Any]] = field(default_factory=list)
    point_ended: List[Dict[str, Any]] = field(default_factory=list)
    daq_values: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))

    # used for updating UI, represents the accumulated "flat" value
    # or the most recent value for
    streaming_daq_xs: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))
    streaming_daq_ys: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))

    async def save(self, app, extra=None):
        save_directory = Path(str(app.app_root / app.config.data_directory / app.config.data_format).format(
            user=self.user,
            session=self.session,
            run=self.number,
            date=datetime.date.today().isoformat(),
        ))

        if extra is None:
            extra = {}

        if save_directory.exists():
            warnings.warn('Save directory already exists. Postfixing with the current time.')
            save_directory = (
                str(save_directory) + '_' +
                datetime.datetime.now().time().isoformat().replace('.', '-').replace(':', '-')
            )
            save_directory = Path(save_directory)

        save_directory.mkdir(parents=True, exist_ok=True)

        with open(save_directory / 'metadata.json', 'w+') as f:
            json.dump({
                'metadata': self.metadata,
                'point_started': self.point_started,
                'point_ended': self.point_ended,
                'steps_taken': self.steps_taken,
            }, f, cls=RichEncoder, indent=2)

        def daq_to_xarray(stream_name, data_stream):
            """
            Data streams are always lists of dictionaries with a
            point, a step number, and the acquisition time. Here we

            :param data_stream:
            :return:
            """
            step, points, data, time = [
                [p[name] for p in data_stream]
                for name in ['step', 'point', 'data', 'time']
            ]
            time = np.vectorize(np.datetime64)(np.asarray(time))
            time_dim = f'{stream_name}-time'

            peeked = data[0]
            if isinstance(peeked, np.ndarray):
                data = np.stack(data, axis=-1)
                data_coords = {f'dim_{i}': np.arange(s) for i, s in enumerate(peeked.shape)}
                data_coords[time_dim] = time
                data_dims = [f'dim_{i}' for i in range(len(peeked.shape))] + [time_dim]
            else:
                data = np.asarray(data)
                data_coords = {f'{stream_name}-time': time}
                data_dims = [time_dim]

            ds = xr.Dataset({
                f'{stream_name}-step': xr.DataArray(
                    np.asarray(step),
                    coords={f'{stream_name}-time': time},
                    dims=[time_dim],
                ),
                f'{stream_name}-point': xr.DataArray(
                    np.asarray(points),
                    coords={f'{stream_name}-time': time},
                    dims=[time_dim],
                ),
                f'{stream_name}-data': xr.DataArray(
                    data,
                    coords=data_coords,
                    dims=data_dims,
                ),
            })
            return ds

        daq = xr.merge([daq_to_xarray('-'.join(str(k) for k in ks), v)
                        for ks, v in self.daq_values.items()])
        daq.to_zarr(save_directory / 'raw_daq.zarr')

        for k, v in extra.items():
            if v is None:
                continue

            v.to_zarr(save_directory / f'{k}.zarr')


class Experiment(FSM):
    STARTING_STATE = 'STARTUP'
    STATE_TABLE = {
        'STARTUP': [{'match': 'initialize', 'to': 'IDLE'}],
        'IDLE': [
            {'match': 'start', 'to': 'RUNNING'},
            {'match': 'shutdown', 'to': 'SHUTDOWN'},
        ],
        'RUNNING': [
            {'match': 'pause', 'to': 'PAUSED'},
            {'match': 'stop', 'to': 'IDLE'},
            {'match': 'shutdown', 'to': 'SHUTDOWN'},
        ],
        'PAUSED': [
            {'match': 'start', 'to': 'RUNNING',},
            {'match': 'stop', 'to': 'IDLE'},
            {'match': 'shutdown', 'to': 'SHUTDOWN'},
        ],
        'SHUTDOWN': [],
    }

    panel_cls = ExperimentPanel
    scan_methods = []
    interlocks = []

    async def idle_to_running(self, *_):
        """
        Experiment is starting
        :return:
        """
        interlocks_passed = True
        try:
            for interlock in self.interlocks:
                status = await interlock()
                logger.info(status)
        except InterlockException as e:
            interlocks_passed = False
            logger.error(f'Interlock failed: {e}')
            self.messages.put_nowait('stop')

        if interlocks_passed:
            if self.run_number is None:
                self.run_number = 0
            else:
                self.run_number += 1

            config = copy(self.scan_configuration[self.use_method])
            all_scopes = itertools.chain(self.app.actors.keys(), self.app.managed_instruments.keys())
            sequence = config.sequence(self, **{
                s: ScopedAccessRecorder(s) for s in all_scopes if s != 'experiment'})  # TODO fixthis

            self.collation = None
            self.current_run = Run(
                number=self.run_number, user='test_user', session='test_session',
                config=config, sequence=sequence)

    async def enter_running(self, *_):
        self.ui.enter_running()

    def plot(self, dependent: str, independent: List[str], name, **kwargs):
        assert self.current_run is not None
        if isinstance(independent, str):
            independent = [independent]

        self.current_run.additional_plots.append({
            'dependent': tokenize_access_path(dependent),
            'independent': [tokenize_access_path(ind) for ind in independent],
            'name': name,
            **kwargs,
        })

    def collate(self, independent: List[Tuple[AccessRecorder, str]] = None,
                dependent: List[Tuple[AccessRecorder, str]] = None):
        if independent is None:
            independent = []
        if dependent is None:
            dependent = []

        def unwrap(c):
            if isinstance(c, list):
                return tuple(c)

            return c.full_path_()

        self.collation = Collation(
            independent={unwrap(k): v for k, v in independent},
            dependent={unwrap(k): v for k, v in dependent})

        self.comment('Collating with: independent={}, dependent={}'.format(
            {unwrap(k): v for k, v in independent},
            {unwrap(k): v for k, v in dependent},
        ))

    async def enter_paused(self, *_):
        self.comment('Paused')
        self.ui.enter_paused()

    async def leave_paused(self, *_):
        self.comment('Unpaused')

    def comment(self, message):
        self.current_run.metadata.append({'type': 'comment', 'content': message, 'time': datetime.datetime.now()})

    async def running_to_idle(self, *_):
        await self.save()
        self.ui.running_to_idle()

    async def running_to_shutdown(self, *_):
        await self.save()

    # BUSINESS LOGIC
    async def run_running(self, *_):
        try:
            next_step = next(self.current_run.sequence)
            await self.take_step(next_step)
        except StopIteration:
            # We're done! Time to save your data.
            self.messages.put_nowait('stop')

    async def perform_single_daq(self, scope=None, path=None, read=None, write=None, preconditions=None, call=None):
        try:
            if preconditions:
                all_scopes = {k: v for k, v in itertools.chain(self.app.actors.items(), self.app.managed_instruments.items())
                              if k != 'experiment'}
                for precondition in preconditions:
                    await precondition(self, **all_scopes)
        except Exception as e:
            logger.error(f'Failed precondition: {e}.')
            self.messages.put_nowait('stop')

        if scope is None:
            return

        instrument = self.app.managed_instruments[scope]

        for p in path:
            if isinstance(p, int):
                instrument = instrument[p]
            else:
                instrument = getattr(instrument, p)

        qual_name = tuple([scope] + path)

        if call is not None:
            args, kwargs = call
            instrument(*args, **kwargs)

        elif write is None:
            value = await instrument.read()
            time = datetime.datetime.now()
            self.current_run.daq_values[qual_name].append({
                'data': value,
                'time': time,
                'step': self.current_run.step,
                'point': self.current_run.point,
            })
            self.current_run.streaming_daq_xs[qual_name].append(self.current_run.point)
            self.current_run.streaming_daq_ys[qual_name].append(value)
        else:
            if self.collation:
                self.collation.receive(qual_name, write)

            await instrument.write(write)
            time = datetime.datetime.now()
            self.current_run.daq_values[qual_name].append({
                'data': write,
                'time': time,
                'step': self.current_run.step,
                'point': self.current_run.point,
            })
            self.current_run.streaming_daq_xs[qual_name].append(self.current_run.point)
            self.current_run.streaming_daq_ys[qual_name].append(write)

    async def take_step(self, step):
        self.current_run.steps_taken.append({
            'step': step,
            'time': datetime.datetime.now()
        })

        if isinstance(step, dict):
            step = [step]

        await gather(*[self.perform_single_daq(**spec) for spec in step])
        self.current_run.step += 1

    async def run_idle(self, *_):
        return

    async def enter_idle(self, *_):
        self.ui.enter_idle()

    async def run_startup(self, *_):
        # You can do any startup here if needed
        # otherwise we immediately transition to initialized
        await self.messages.put('initialize')

    async def run_shutdown(self, *_):
        return

    async def run_paused(self, *_):
        return

    async def save(self, *_):
        if self.current_run is None:
            return

        collated_data = None
        try:
            if self.collation:
                collated_data = self.collation.to_xarray(self.current_run.daq_values)
        except:
            pass

        await self.current_run.save(self.app, {'collated': collated_data})

        self.current_run = None

    @contextlib.contextmanager
    def point(self):
        self.current_run.point_started.append(datetime.datetime.now())
        yield
        self.current_run.point += 1
        self.current_run.point_ended.append(datetime.datetime.now())

        if self.ui is not None:
            self.ui.soft_update()

    def __init__(self, app):
        super().__init__(app)

        self.run_number = None
        self.current_run = None
        self.collation = None
        self.ui = None # reference to the mounted UI

        self.scan_configuration = {S.__name__: S() for S in self.scan_methods}
        self.use_method = self.scan_methods[0].__name__

    async def handle_message(self, message):
        logger.warning(f'Unhandled message: {message}')

