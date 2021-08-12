from typing import List, Optional, Tuple, Union

import asyncio
import contextlib
import datetime
import inspect
import itertools
from asyncio import gather, get_running_loop, sleep
from collections import deque
from copy import copy
from functools import lru_cache

from autodidaqt_common.collation import Collation, CollationInfo
from autodidaqt_common.path import AxisPath
from autodidaqt_common.remote import schema
from autodidaqt_common.remote.command import (
    PauseRunCommand,
    ReadAxisCommand,
    RecordData,
    RequestShutdown,
    SetScanConfigCommand,
    StartRunCommand,
    StopRunCommand,
    WriteAxisCommand,
)
from loguru import logger

from autodidaqt.actor import StopException
from autodidaqt.experiment.save import save_on_separate_thread
from autodidaqt.interlock import InterlockException
from autodidaqt.panels import ExperimentPanel
from autodidaqt.registrar import registrar
from autodidaqt.utils import ScanAccessRecorder

from .fsm import FSM
from .run import Run


class HeadlessExperimentUI:
    def update_timing_ui(self):
        pass

    def running_to_idle(self):
        pass

    def soft_update(self, *_, **__):
        pass

    def enter_idle(self):
        pass

    def enter_running(self):
        pass

    def enter_paused(self):
        pass

    def update_queue_ui(self):
        pass


class ScopedAccessRecorder:
    def __init__(self, scope):
        self.scope = scope

    def __getattr__(self, item):
        return getattr(ScanAccessRecorder(self.scope), item)

    def __getitem__(self, item):
        return ScanAccessRecorder(self.scope)[item]


ES = schema.ExperimentStates
T = schema.ExperimentTransitions


class Experiment(FSM):
    STARTING_STATE = ES.Startup
    STATE_TABLE = {
        ES.Startup: [{"match": T.Initialize, "to": ES.Idle}],
        ES.Idle: [
            {"match": T.Start, "to": ES.Running},
            {"match": T.StartManual, "to": ES.Running},
            {"match": T.Shutdown, "to": ES.Shutdown},
        ],
        ES.Running: [
            {"match": T.Pause, "to": ES.Paused},
            {"match": T.Stop, "to": ES.Idle},
            {"match": T.Shutdown, "to": ES.Shutdown},
        ],
        ES.Paused: [
            {"match": T.Start, "to": ES.Running},
            {"match": T.Stop, "to": ES.Idle},
            {"match": T.Shutdown, "to": ES.Shutdown},
        ],
        ES.Shutdown: [],
    }

    panel_cls = ExperimentPanel
    scan_methods = []
    interlocks = []
    save_on_main: bool = True
    collation: Optional[Collation] = None

    # related to remoting
    running_manually: bool = False
    remote_commands: asyncio.Queue

    def collect_remote_state(self) -> schema.RemoteExperimentState:
        return schema.RemoteExperimentState(
            scan_methods=[schema.TypeDefinition.from_type(s).id for s in self.scan_methods],
            fsm_state=self.state,
        )

    def build_manual_run(self, config) -> Run:
        return Run(
            number=self.run_number,
            user=self.app.user.user,
            session=self.app.user.session_name,
            is_manual=True,
            config=None,
            sequence=None,
            is_inverted=None,
        )

    def build_run_from_config(self, config) -> Run:
        if not inspect.isasyncgenfunction(config.sequence):
            is_inverted = True
            # run the experiment in inverted control as is standard
            all_scopes = itertools.chain(
                self.app.actors.keys(), self.app.managed_instruments.keys()
            )

            # TODO fix this to be safer
            sequence = config.sequence(
                self,
                **{s: ScopedAccessRecorder(s) for s in all_scopes if s != "experiment"},
            )
        else:
            is_inverted = False
            all_scopes = {}
            all_scopes.update(self.app.actors)
            all_scopes.update(self.app.managed_instruments)
            all_scopes.pop("experiment", None)
            sequence = config.sequence(self, **all_scopes)

        return Run(
            number=self.run_number,
            user=self.app.user.user,
            session=self.app.user.session_name,
            config=config,
            sequence=sequence,
            is_inverted=is_inverted,
        )

    async def idle_to_running(self, _, trigger):
        """Experiment is starting."""

        if trigger == T.StartManual:
            self.running_manually = True
            self.clear_command_queue()

        interlocks_passed = True
        try:
            for interlock in self.interlocks:
                status = await interlock()
                logger.info(status)
        except InterlockException as e:
            interlocks_passed = False
            logger.error(f"Interlock failed: {e}")
            self.messages.put_nowait(T.Stop)

        if interlocks_passed:
            if self.run_number is None:
                self.run_number = 0
            else:
                self.run_number += 1

            if not self.running_manually:
                # use the queue if it is not empty
                if self.scan_deque:
                    self.autoplay = True

                    config = self.scan_deque.popleft()
                else:
                    config = copy(self.scan_configuration)

                self.collation = None
                self.current_run = self.build_run_from_config(config)
            else:
                self.current_run = self.build_manual_run()

    async def enter_running(self, *_):
        self.ui.enter_running()

    def plot(self, dependent: str, independent: List[str], name, **kwargs):
        assert self.current_run is not None
        if isinstance(independent, str):
            independent = [independent]

        self.current_run.additional_plots.append(
            {
                "dependent": AxisPath.to_tuple(dependent),
                "independent": [AxisPath.to_tuple(ind) for ind in independent],
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

        independent = {AxisPath.to_tokenized_string(k): v for k, v in independent}
        dependent = {AxisPath.to_tokenized_string(k): v for k, v in dependent}
        collation_info = CollationInfo(
            independent=independent,
            dependent=dependent,
        )
        self.collation = collation_info.to_collation()
        self.app.send_to_remote(collation_info)

        self.comment(
            "Collating with: independent={}, dependent={}".format(
                collation_info.independent, collation_info.dependent
            )
        )

    async def enter_paused(self, *_):
        self.comment("Paused")
        self.ui.enter_paused()

    async def leave_paused(self, *_):
        self.comment("Unpaused")

    def comment(self, message):
        self.current_run.metadata.append(
            {
                "type": "comment",
                "content": message,
                "time": datetime.datetime.now(),
            }
        )

    def clear_command_queue(self):
        while True:
            try:
                m = self.remote_commands.get_nowait()
                logger.warning(f"Unhandled remote command: {m}. Experiment triggered stop early.")
                self.remote_commands.task_done()
            except asyncio.QueueEmpty:
                return

    async def running_to_idle(self, *_):
        # if we were performing a manual scan, return to "standard" form
        # and use prebaked scans instead
        self.running_manually = False
        self.clear_command_queue()

        await self.save()
        self.ui.running_to_idle()
        if self.autoplay:
            if self.scan_deque:
                self.messages.put_nowait(T.Start)
            else:
                self.autoplay = False

    async def running_to_shutdown(self, *_):
        await self.save()

    async def take_remote_command_step(self):
        remote_command = None
        try:
            remote_command = self.remote_commands.get_nowait()
        except asyncio.QueueEmpty:
            return

        logger.info("Received remote command {}.")
        if isinstance(remote_command, ReadAxisCommand):
            # format into the step format and then use that
            path = AxisPath.to_tuple(remote_command.axis_path)
            await self.take_step(
                [
                    {
                        "read": None,
                        "path": path[1:],
                        "scope": path[0],
                    }
                ]
            )
        elif isinstance(remote_command, WriteAxisCommand):
            path = AxisPath.to_tuple(remote_command.axis_path)
            await self.take_step(
                [
                    {
                        "write": remote_command.value.to_instance(),
                        "path": path[1:],
                        "scope": path[0],
                    }
                ]
            )
        else:
            logger.error(f"Unknown remote command: {remote_command}. Skipping...")

    async def run_running(self, *_):
        if self.running_manually:
            await self.take_remote_command_step()
            return

        if self.current_run.is_inverted:
            try:
                next_step = next(self.current_run.sequence)
                await self.take_step(next_step)
            except StopIteration:
                # We're done! Time to save your data.
                self.ui.soft_update(force=True, render_all=True)
                self.messages.put_nowait(T.Stop)
        else:
            async for data in self.current_run.sequence:
                self.current_run.steps_taken.append(
                    {
                        "step": self.current_run.step,
                        "time": datetime.datetime.now(),
                    }
                )
                self.current_run.step += 1
                for qual_name, value in data.items():
                    self.record_data(AxisPath.to_tuple(qual_name), value)

            self.ui.soft_update(force=True, render_all=True)
            self.messages.put_nowait(T.Stop)

    @lru_cache()
    def type_def_for_qual_name(self, qual_name):
        instrument = self.app.managed_instruments[qual_name[0]]
        axis = instrument.lookup_axis(qual_name[1:])
        return axis.type_def

    def record_data(self, qual_name: Tuple, value: any):
        now = datetime.datetime.now()
        self.current_run.daq_values[qual_name].append(
            {
                "data": value,
                "time": now,
                "step": self.current_run.step,
                "point": self.current_run.point,
            }
        )

        self.current_run.streaming_daq_xs[qual_name].append(self.current_run.point)
        self.current_run.streaming_daq_ys[qual_name].append(value)

        # also, forward data to the remote
        # currently, for large arrays this is the most inefficient
        # thing we do by far, but this can be considered using
        # memmap or another process at a later time
        self.app.send_to_remote(
            RecordData(
                point=self.current_run.point,
                step=self.current_run.step,
                path=qual_name,
                time=now.isoformat(),
                value=self.type_def_for_qual_name(qual_name).to_value(value),
            )
        )

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
                        self.app.actors.items(),
                        self.app.managed_instruments.items(),
                    )
                    if k != "experiment"
                }
                for precondition in preconditions:
                    await precondition(self, **all_scopes)
        except Exception as e:
            logger.error(f"Failed precondition: {e}.")
            self.messages.put_nowait(T.Stop)

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
        self.current_run.steps_taken.append({"step": step, "time": datetime.datetime.now()})

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
        await self.messages.put(T.Initialize)

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
            save_on_separate_thread(
                finished_run,
                directory,
                self.collation,
                extra_attrs=metadata_from_registrar,
                save_format=self.app.config.save_format,
            )
            logger.info(f"Finished saving")
        else:
            logger.info(f"Data will save on separate thread")
            loop = get_running_loop()
            task = loop.run_in_executor(
                self.app.process_pool,
                save_on_separate_thread,
                finished_run,
                directory,
                self.collation,
                metadata_from_registrar,
                self.app.config.save_format,
            )

        self.app.send_to_remote(self.current_run.to_summary())
        self.current_run = None

    @property
    def scan_configuration(self):
        return self.scan_configurations[self.use_method]

    @contextlib.contextmanager
    def point(self):
        logger.trace(f"Start point {self.current_run.point}")
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

        self.ui = HeadlessExperimentUI()  # reference to the mounted UI

        for s in self.scan_methods:
            _ = schema.TypeDefinition.from_type(s)

        self.scan_configurations = {S.__name__: S() for S in self.scan_methods}

        if len(self.scan_methods) > 0:
            self.use_method = self.scan_methods[0].__name__

    async def handle_message(self, message):
        if isinstance(message, RequestShutdown):
            self.save_on_main = True
            await self.save()
            await message.respond_did_shutdown(self.app)
            raise StopException()
        elif isinstance(message, PauseRunCommand):
            await self.messages.put(T.Pause)
        elif isinstance(message, StopRunCommand):
            await self.messages.put(T.Stop)
        elif isinstance(message, StartRunCommand):
            await self.messages.put(T.Start)
        elif isinstance(message, SetScanConfigCommand):
            scan_config = message.scan_config.to_instance()
            self.scan_configurations[type(scan_config).__name__] = scan_config
            self.use_method = type(scan_config).__name__
        elif isinstance(message, (WriteAxisCommand, ReadAxisCommand)):
            await self.remote_commands.put(message)
        else:
            logger.info(f"Unhandled message: {message}")

    async def prepare(self):
        await super().prepare()
        self.remote_commands = asyncio.Queue()


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
                self.messages.put_nowait(T.Start)
            else:
                self.autoplay = False
                if self.exit_after_finish:
                    # not a perfect way to shut things down, but should work well for now.
                    raise KeyboardInterrupt("Stopping.")

    async def startup_to_idle(self, *_):
        self.messages.put_nowait(T.Start)

    async def save(self, *_):
        if self.discard_data:
            return

        await super().save(*_)
