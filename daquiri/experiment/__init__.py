import contextlib
import datetime
import inspect
import itertools
from asyncio import QueueEmpty, gather, get_running_loop, sleep
from collections import deque
from copy import copy
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Union

import numpy as np
import xarray as xr
from daquiri.actor import Actor
from daquiri.core import registrar
from daquiri.interlock import InterlockException
from daquiri.panels import ExperimentPanel
from daquiri.utils import ScanAccessRecorder, tokenize_access_path
from loguru import logger

from .collation import Collation
from .fsm import FSM
from .run import Run


class ScopedAccessRecorder:
    def __init__(self, scope):
        self.scope = scope

    def __getattr__(self, item):
        return getattr(ScanAccessRecorder(self.scope), item)

    def __getitem__(self, item):
        return ScanAccessRecorder(self.scope)[item]


def _save_on_separate_thread(run, directory, collation, extra_attrs=None, save_format="zarr"):
    if collation:
        try:
            collated = collation.to_xarray(run.daq_values)
        except:
            collated = None

    run.save(directory, {"collated": collated}, extra_attrs=extra_attrs, save_format=save_format)

class Experiment(FSM):
    STARTING_STATE = "STARTUP"
    STATE_TABLE = {
        "STARTUP": [{"match": "initialize", "to": "IDLE"}],
        "IDLE": [
            {"match": "start", "to": "RUNNING"},
            {"match": "shutdown", "to": "SHUTDOWN"},
        ],
        "RUNNING": [
            {"match": "pause", "to": "PAUSED"},
            {"match": "stop", "to": "IDLE"},
            {"match": "shutdown", "to": "SHUTDOWN"},
        ],
        "PAUSED": [
            {"match": "start", "to": "RUNNING",},
            {"match": "stop", "to": "IDLE"},
            {"match": "shutdown", "to": "SHUTDOWN"},
        ],
        "SHUTDOWN": [],
    }

    panel_cls = ExperimentPanel
    scan_methods = []
    interlocks = []
    save_on_main: bool = False

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
            logger.error(f"Interlock failed: {e}")
            self.messages.put_nowait("stop")

        if interlocks_passed:
            if self.run_number is None:
                self.run_number = 0
            else:
                self.run_number += 1

            # use the queue if it is not empty
            if self.scan_deque:
                self.autoplay = True

                config = self.scan_deque.popleft()
            else:
                config = copy(self.scan_configuration)

            if not inspect.isasyncgenfunction(config.sequence):
                is_inverted = True
                # run the experiment in inverted control as is standard
                all_scopes = itertools.chain(
                    self.app.actors.keys(), self.app.managed_instruments.keys()
                )

                # TODO fix this to be safer
                sequence = config.sequence(
                    self,
                    **{
                        s: ScopedAccessRecorder(s)
                        for s in all_scopes
                        if s != "experiment"
                    },
                )
            else:
                is_inverted = False
                all_scopes = {}
                all_scopes.update(self.app.actors)
                all_scopes.update(self.app.managed_instruments)
                del all_scopes["experiment"]
                sequence = config.sequence(self, **all_scopes)

            self.collation = None
            self.current_run = Run(
                number=self.run_number,
                user=self.app.user.user,
                session=self.app.user.session_name,
                config=config,
                sequence=sequence,
                is_inverted=is_inverted,
            )

    async def enter_running(self, *_):
        self.ui.enter_running()

    def plot(self, dependent: str, independent: List[str], name, **kwargs):
        assert self.current_run is not None
        if isinstance(independent, str):
            independent = [independent]

        self.current_run.additional_plots.append(
            {
                "dependent": tokenize_access_path(dependent),
                "independent": [tokenize_access_path(ind) for ind in independent],
                "name": name,
                **kwargs,
            }
        )

    def collate(
        self,
        independent: List[Tuple[Union[ScanAccessRecorder, str], str]] = None,
        dependent: List[Tuple[Union[ScanAccessRecorder, str], str]] = None,
    ):
        if independent is None:
            independent = []
        if dependent is None:
            dependent = []

        def unwrap(c):
            if isinstance(c, (list, tuple,)):
                return tuple(c)

            if isinstance(c, str):
                return tokenize_access_path(c)

            return c.full_path_()

        self.collation = Collation(
            independent={unwrap(k): v for k, v in independent},
            dependent={unwrap(k): v for k, v in dependent},
        )

        self.comment(
            "Collating with: independent={}, dependent={}".format(
                {unwrap(k): v for k, v in independent},
                {unwrap(k): v for k, v in dependent},
            )
        )

    async def enter_paused(self, *_):
        self.comment("Paused")
        self.ui.enter_paused()

    async def leave_paused(self, *_):
        self.comment("Unpaused")

    def comment(self, message):
        self.current_run.metadata.append(
            {"type": "comment", "content": message, "time": datetime.datetime.now()}
        )

    async def running_to_idle(self, *_):
        await self.save()
        self.ui.running_to_idle()
        if self.autoplay:
            if self.scan_deque:
                self.messages.put_nowait("start")
            else:
                self.autoplay = False

    async def running_to_shutdown(self, *_):
        await self.save()

    # BUSINESS LOGIC
    async def run_running(self, *_):
        if self.current_run.is_inverted:
            try:
                next_step = next(self.current_run.sequence)
                await self.take_step(next_step)
            except StopIteration:
                # We're done! Time to save your data.
                self.ui.soft_update(force=True, render_all=True)
                self.messages.put_nowait("stop")
        else:
            async for data in self.current_run.sequence:
                self.current_run.steps_taken.append(
                    {"step": self.current_run.step, "time": datetime.datetime.now()}
                )
                self.current_run.step += 1
                for qual_name, value in data.items():
                    self.record_data(tokenize_access_path(qual_name), value)

            self.ui.soft_update(force=True, render_all=True)
            self.messages.put_nowait("stop")

    def record_data(self, qual_name: Tuple, value: any):
        self.current_run.daq_values[qual_name].append(
            {
                "data": value,
                "time": datetime.datetime.now(),
                "step": self.current_run.step,
                "point": self.current_run.point,
            }
        )

        self.current_run.streaming_daq_xs[qual_name].append(self.current_run.point)
        self.current_run.streaming_daq_ys[qual_name].append(value)

    async def perform_single_daq(
        self,
        scope=None,
        path=None,
        read=None,
        write=None,
        set=None,
        preconditions=None,
        is_property=False,
        call=None,
    ):
        try:
            if preconditions:
                all_scopes = {
                    k: v
                    for k, v in itertools.chain(
                        self.app.actors.items(), self.app.managed_instruments.items()
                    )
                    if k != "experiment"
                }
                for precondition in preconditions:
                    await precondition(self, **all_scopes)
        except Exception as e:
            logger.error(f"Failed precondition: {e}.")
            self.messages.put_nowait("stop")

        if scope is None:
            return

        instrument = self.app.managed_instruments[scope]
        for p in path[:-1] if is_property else path:
            if isinstance(p, int):
                instrument = instrument[p]
            else:
                instrument = getattr(instrument, p)

        qual_name = tuple([scope] + list(path))

        if call is not None:
            args, kwargs = call
            instrument(*args, **kwargs)
        elif write is None and set is None:
            value = await instrument.read()
            self.record_data(qual_name, value)
        else:
            if self.collation:
                self.collation.receive(qual_name, write if set is None else set)

            if set is not None:
                instrument.set(set)
            else:
                await instrument.write(write)

            self.record_data(qual_name, write if set is None else set)

    async def take_step(self, step):
        self.current_run.steps_taken.append(
            {"step": step, "time": datetime.datetime.now()}
        )

        if isinstance(step, dict):
            step = [step]

        await gather(*[self.perform_single_daq(**spec) for spec in step])
        self.current_run.step += 1

    @property
    def current_progress(self):
        try:
            if self.current_run is not None:
                n_points = self.current_run.config.n_points
            else:
                n_points = self.scan_configuration.n_points
        except AttributeError:
            n_points = None

        if self.current_run is None:
            return None, n_points

        return self.current_run.point, n_points

    async def run_idle(self, *_):
        # this is kind of a kludge, instead we should be
        await sleep(0.1)
        self.ui.update_timing_ui()

    async def enter_idle(self, *_):
        self.ui.enter_idle()

    async def run_startup(self, *_):
        # You can do any startup here if needed
        # otherwise we immediately transition to initialized
        await self.messages.put("initialize")

    async def run_shutdown(self, *_):
        return

    async def run_paused(self, *_):
        # this is kind of a kludge
        await sleep(0.1)
        self.ui.update_timing_ui()

    async def save(self, *_):
        if self.current_run is None:
            return

        finished_run = self.current_run
        directory = self.current_run.save_directory(self.app)
        logger.info(f"Saving to {directory}")
        finished_run.finalize()

        metadata_from_registrar = registrar.collect_metadata()

        if self.save_on_main:
            _save_on_separate_thread(
                finished_run,
                directory,
                self.collation,
                extra_attrs=metadata_from_registrar,
                save_format=self.app.config.save_format,
            )
        else:
            loop = get_running_loop()
            task = loop.run_in_executor(
                self.app.process_pool,
                _save_on_separate_thread,
                finished_run,
                directory,
                self.collation,
                metadata_from_registrar,
                self.app.config.save_format,
            )

        self.current_run = None

    @property
    def scan_configuration(self):
        return self.scan_configurations[self.use_method]

    @contextlib.contextmanager
    def point(self):
        self.current_run.point_started.append(datetime.datetime.now())
        yield
        self.current_run.point += 1
        self.current_run.point_ended.append(datetime.datetime.now())

        if self.ui is not None:
            self.ui.soft_update()

    # QUEUE MANAGEMENT
    def enqueue(self, index=None):
        configuration = copy(self.scan_configuration)

        if index is not None:
            self.scan_deque.insert(index, configuration)
        else:
            self.scan_deque.append(configuration)

    def __init__(self, app):
        super().__init__(app)

        self.run_number = None
        self.current_run = None
        self.collation = None

        self.autoplay = False  # autoplay next item from queue
        self.scan_deque = deque([])

        self.ui = None  # reference to the mounted UI

        self.scan_configurations = {S.__name__: S() for S in self.scan_methods}
        self.use_method = self.scan_methods[0].__name__

    async def handle_message(self, message):
        logger.warning(f"Unhandled message: {message}")


class AutoExperiment(Experiment):
    run_with = None
    exit_after_finish: bool = False
    discard_data: bool = False

    def __init__(self, app):
        super().__init__(app)

        self.scan_deque = deque(self.run_with)

    async def running_to_idle(self, *_):
        await self.save()
        self.ui.running_to_idle()
        if self.autoplay:
            if self.scan_deque:
                self.messages.put_nowait("start")
            else:
                self.autoplay = False
                if self.exit_after_finish:
                    # not a perfect way to shut things down, but should work well for now.
                    raise KeyboardInterrupt("Stopping.")

    async def startup_to_idle(self, *_):
        self.messages.put_nowait("start")

    async def save(self, *_):
        if self.discard_data:
            return

        await super().save(*_)
