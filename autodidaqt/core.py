from typing import Any, Dict, Optional, Type

import argparse
import asyncio
import itertools
import multiprocessing
import pickle
import pprint
import signal
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, make_dataclass
from enum import Enum
from pathlib import Path
from uuid import UUID

import appdirs
from asyncqt import QEventLoop
from autodidaqt_common.path import AxisPath
from autodidaqt_common.remote.command import (
    FORWARD_TO_EXPERIMENT_MESSAGE_CLASSES,
    AcknowledgeShutdown,
    AllState,
    GetAllStateCommand,
    HeartbeatCommand,
    ReadAxisCommand,
    RemoteCommand,
    RequestShutdown,
    ShutdownCommand,
    ShutdownEta,
    WriteAxisCommand,
)
from autodidaqt_common.remote.config import RemoteConfiguration
from autodidaqt_common.remote.middleware import TranslateCommandsMiddleware, WireMiddleware
from autodidaqt_common.remote.schema import RemoteApplicationState, TypeDefinition
from dotenv import load_dotenv
from loguru import logger
from PyQt5 import QtCore
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from pyqt_led import Led
from rx.subject import Subject

from autodidaqt.version import VERSION
from autodidaqt.actor import Actor
from autodidaqt.config import Config, MetaData, default_config_for_platform
from autodidaqt.instrument import ManagedInstrument
from autodidaqt.panel import Panel
from autodidaqt.panels import InstrumentManager
from autodidaqt.remote.link import RemoteLink
from autodidaqt.state import (
    AppState,
    AutodiDAQtStateAtRest,
    SerializationSchema,
    find_newest_state_filename,
    generate_state_filename,
)
from autodidaqt.ui import (
    CollectUI,
    bind_dataclass,
    button,
    horizontal,
    layout_dataclass,
    led,
    update_dataclass,
    vertical,
)
from autodidaqt.utils import default_stylesheet

__all__ = ("autodidaqt",)

USE_QUAMASH = False


@dataclass
class CommandLineConfig:
    headless: bool = False
    remote_config: Optional[RemoteConfiguration] = None


def parse_args() -> CommandLineConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nanomessage-uri", type=str, required=False)
    parser.add_argument("--headless", action="store_true")
    parser.set_defaults(headless=False)

    if "pytest" in "".join(sys.argv) or "ui" in "".join(sys.argv):
        # we're in a test harness, run in standard configuration
        return CommandLineConfig()

    try:
        parsed = parser.parse_args(sys.argv[1:])
        config = CommandLineConfig(headless=parsed.headless)

        if parsed.nanomessage_uri is not None:
            config.remote_config = RemoteConfiguration(ui_address=parsed.nanomessage_uri)
    except IndexError:
        config = CommandLineConfig()

    return config


class AutodiDAQtMainWindowHeadless:
    open_panels = {}

    def __init__(self, loop, app):
        pass


class AutodiDAQtMainWindow(QMainWindow):
    """
    Internal, the PyQt main window
    """

    def client_panel_will_close(self, name):
        self._panels[name]["indicator"].set_status(False)
        self._panels[name]["indicator"].update()

    @property
    def open_panels(self) -> Dict[str, Panel]:
        return {
            name: self._panels[name]["panel"]
            for name in self._panels
            if self._panels[name]["panel"]
        }

    def launch_panel(self, name):
        logger.info(f"Opening panel {name}")
        if self._panels[name]["panel"] is None:
            panel_cls = self.app.panel_definitions[name]
            w = panel_cls(parent=self, id=name, app=self.app)
            self._panels[name]["panel"] = w
            w.show()
        else:
            # for now, focus the panel
            w = self._panels[name]["panel"]
            w.setWindowState(
                w.windowState() & ~QtCore.Qt.WindowMinimized
                | QtCore.Qt.WindowActive
                | QtCore.Qt.WindowStaysOnTopHint
            )
            w.show()
            w.setWindowFlags(w.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
            w.show()

        indicator = self._panels[name]["indicator"]
        indicator.turn_on()
        indicator.update()

    def __init__(self, loop, app):
        super(AutodiDAQtMainWindow, self).__init__()
        self.app = app

        self._panels = {
            k: {"panel": None, "running": False, "indicator": None, "restart": None}
            for k in self.app.panel_definitions.keys()
        }

        self.panel_order = sorted(list(self._panels.keys()))

        # set layout
        self.win = QWidget()
        self.win.resize(50, 50)  # smaller than minimum size, so will resize appropriately

        self.ui = {}
        with CollectUI(self.ui):
            vertical(
                horizontal(
                    vertical(
                        *[
                            button(
                                "Restart {}".format(self.app.panel_definitions[panel_name].TITLE),
                                id=f"restart-{panel_name}",
                            )
                            for panel_name in self.panel_order
                        ],
                        spacing=8,
                    ),
                    vertical(
                        *[
                            led(
                                None,
                                shape=Led.circle,
                                id="indicator-{}".format(panel_name),
                            )
                            for panel_name in self.panel_order
                        ],
                        spacing=8,
                    ),
                    spacing=8,
                ),
                layout_dataclass(self.app.user, prefix="app_user"),
                content_margin=8,
                spacing=8,
                widget=self.win,
            )

        bind_dataclass(self.app.user, prefix="app_user", ui=self.ui)

        for k in self.panel_order:

            def bind_panel(name):
                return lambda _: self.launch_panel(name=name)

            self.ui[f"restart-{k}"].subject.subscribe(bind_panel(k))
            self._panels[k]["indicator"] = self.ui[f"indicator-{k}"]
            self._panels[k]["restart"] = self.ui[f"restart-{k}"]

        self.win.show()
        self.win.setWindowTitle("autodidaqt")

        for panel_name, panel_cls in self.app.panel_definitions.items():
            if panel_cls.DEFAULT_OPEN:
                self.launch_panel(panel_name)

        self.loop = loop


def make_user_data_dataclass(profile_field: Optional[Any]) -> type:
    if profile_field:
        profile_fields = [profile_field]
    else:
        profile_fields = []

    return make_dataclass(
        "UserData",
        [
            *profile_fields,
            ("user", str, "global-user"),
            ("session_name", str, "global-session"),
        ],
    )


class AutodiDAQt:
    """
    The main application instance for your autodidaqt apps.

    Lifecycle hooks. autodidaqt does not explicitly provide lifecycle hooks.
    Instead, there observable streams that you can filter and subscribe on
    various events as you need them.

    The structure of these events is

    ```
    {
        'time' :: datetime.datetime : The origination time of the event
        'type' :: str : Scoped event type
        'value' :: Optional[Any] : Any message paylaod if applicable
    }
    ```
    """

    _is_shutdown = False
    cli_config: CommandLineConfig = None
    remote: Optional[RemoteLink] = None
    message_read_task: Optional[asyncio.Future] = None

    def __init__(
        self,
        import_name,
        panel_definitions: Optional[Dict[str, Type[Panel]]] = None,
        actors: Optional[Dict[str, Type[Actor]]] = None,
        managed_instruments: Optional[Dict[str, Type[ManagedInstrument]]] = None,
        DEBUG: Optional[bool] = None,
    ):
        import autodidaqt.globals

        autodidaqt.globals.APP = self

        if panel_definitions is None:
            panel_definitions = {}

        if actors is None:
            actors = {}

        if managed_instruments is None:
            managed_instruments = {}

        self.cli_config = CommandLineConfig()
        command_line_config = parse_args()
        if command_line_config.headless:
            self.configure_as_headless(command_line_config)

        if managed_instruments:
            if not any(
                issubclass(panel_def, InstrumentManager) for panel_def in panel_definitions.values()
            ):
                panel_definitions["_instrument_manager"] = InstrumentManager

        for actor_name, actor in actors.items():
            if actor.panel_cls is not None:
                assert actor_name not in panel_definitions
                panel_definitions[actor_name] = actor.panel_cls

        self.events = Subject()
        self.process_pool = ProcessPoolExecutor(max_workers=multiprocessing.cpu_count())

        self.config = None
        self.import_name = import_name
        self.extract_from_dotenv()
        self.load_config()
        self.profile_enum = Enum(
            "UserProfile", dict(zip(self.config.profiles, self.config.profiles))
        )

        # generate a dataclass for storing info about the user
        profile_field = None
        if self.config.use_profiles:
            profile_field = (
                "profile",
                self.profile_enum,
                self.profile_enum(list(self.config.profiles)[0]),
            )
        self.user_cls = make_user_data_dataclass(profile_field)
        self.user = self.user_cls()

        self.meta = MetaData()
        self.app_state = AppState()

        self._log_handler = None
        self.log_file = None
        self.setup_logging()

        self.panel_definitions = panel_definitions
        self.main_window = None
        self.qt_app = None
        self.messages = Subject()

        def lookup_managed_instrument_args(instrument_key):
            return {
                "driver_init": {
                    "args": self.config.instruments.nested_get(
                        [instrument_key, "initialize", "args"],
                        [],
                        safe_early_terminate=True,
                    ),
                    "kwargs": self.config.instruments.nested_get(
                        [instrument_key, "initialize", "kwargs"],
                        {},
                        safe_early_terminate=True,
                    ),
                },
            }

        self.actors: Dict[str, Actor] = {k: A(app=self) for k, A in actors.items()}
        self.managed_instruments: Dict[str, ManagedInstrument] = {
            k: A(app=self, **lookup_managed_instrument_args(k))
            for k, A in managed_instruments.items()
        }
        self.managed_instrument_classes = managed_instruments

        if DEBUG is not None and self.config.DEBUG != DEBUG:
            logger.warning(f"Overwriting the value of DEBUG from configuration, using {DEBUG}")
            self.config.DEBUG = DEBUG

    def configure_as_headless(self, config: CommandLineConfig):
        self.cli_config = config

    @property
    def experiment(self):
        from autodidaqt.experiment import Experiment

        candidates = [actor for actor in self.actors.values() if isinstance(actor, Experiment)]
        assert len(candidates) == 1
        return candidates[0]

    def handle_exception(self, loop, context):
        """
        Attempts to recover from, log, or otherwise deal with an exception inside the
        async portions of autodidaqt.
        """
        try:
            e = context["exception"]
            traceback.print_exception(type(e), e, e.__traceback__)
        except:
            print(context)

        message = context.get("exception", context["message"])
        logger.error(f"Caught Unhandled: {message}")

        if self._is_shutdown:
            return

        try:
            asyncio.create_task(self.shutdown(loop, signal=None))
        except RuntimeError:
            pass

    async def wait_for_graceful_shutdown(self, sent_messages: Dict[UUID, str]):
        while len(sent_messages):
            msg = await self.messages.get()

            if isinstance(msg, AcknowledgeShutdown):
                sent_messages.pop(msg.parent_id)
            else:
                logger.error(f"Dropping message {msg}. In shutdown.")

    async def shutdown(self, loop, signal=None):
        """
        Args:
            loop: The running event loop.
            signal: The signal received which triggered application shutdown.
        """
        self._is_shutdown = True

        if signal:
            try:
                name = signal.name
            except AttributeError:
                name = signal

            logger.info(f"Received exit signal {name}.")
        else:
            logger.warning("Shutting down due to exception.")

        logger.info("Shutting down process pool.")
        self.process_pool.shutdown(wait=True)
        logger.info("Finished shutting down process pool.")

        logger.info("Saving...")
        self.save_state()

        if self.message_read_task is not None:
            logger.info("Application is still reading messages. Stopping...")
            self.message_read_task.cancel()
            self.message_read_task = None

        logger.info("Sending graceful shutdown requests.")
        all_actors = dict(**self.actors, **self.managed_instruments)

        expected_acknowledgments = {}
        for actor_name, actor in all_actors.items():
            req = RequestShutdown()
            await actor.messages.put(req)
            expected_acknowledgments[req.id] = actor_name

        wait_duration = 3.0
        logger.info("Waiting graceful shutdown requests.")
        try:
            await asyncio.wait_for(
                self.wait_for_graceful_shutdown(expected_acknowledgments), wait_duration
            )
            logger.info("Graceful shutdown complete.")
        except asyncio.TimeoutError:
            bad_actors = list(expected_acknowledgments.values())
            logger.error(
                f"Not all actors have shut down after {wait_duration} seconds. Bad actors are {bad_actors}"
            )

        n_tasks_to_cancel = len(asyncio.all_tasks(loop=loop)) - 1
        if n_tasks_to_cancel > 1:
            logger.warning(f"Cancelling tasks... {n_tasks_to_cancel} tasks remaining expected 1.")
        else:
            logger.info("Cancelling tasks...")

        tasks = [
            t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)
        ]

        cancellable = []
        for task in tasks:
            if task.cancel():
                cancellable.append(task)
            else:
                logger.warning(f"Could not cancel task {task}")

        logger.info("Waiting on finished tasks...")
        asyncio.gather(*cancellable, return_exceptions=True)

        if self.cli_config.remote_config:
            logger.info("Sending shutdown acknowledgment to remote.")
            await self.remote.middleware_socket.asend(ShutdownEta(0.5))

        async def stop_loop():
            owner = asyncio.get_event_loop()
            owner.stop()

        logger.info("Stopping loop")
        asyncio.ensure_future(stop_loop())

    def setup_logging(self):
        logger.add(sys.stderr, format="{time} {level} {message}", level="WARNING")
        self.log_file = (
            self.app_root
            / self.config.logging_directory
            / self.config.log_format.format(
                user="global-log",
                time=self.meta.datetime_started,
                session="global-session",
            )
        )
        self._log_handler = logger.add(self.log_file)

    @property
    def app_root(self):
        return Path(self.file).parent.parent.absolute()

    @property
    def name(self):
        if self.import_name == "__main__":
            module_file = getattr(sys.modules["__main__"], "__file__", None)
            if module_file is None:
                return self.import_name
            return Path(module_file).stem
        return self.import_name

    @property
    def file(self):
        return getattr(sys.modules[self.import_name], "__file__", appdirs.user_config_dir())

    @property
    def search_paths(self):
        p = Path(self.file)
        return [
            p.parent.absolute(),
            p.parent.parent.absolute(),
            p.parent.parent.absolute() / "config",
        ]

    def extract_from_dotenv(self):
        dotenv_files = list(itertools.chain(*[p.glob(".env") for p in self.search_paths]))
        if dotenv_files:
            logger.info(f"Found dotenv files {dotenv_files}. Loading...")
            load_dotenv(str(dotenv_files[0]))

    def load_config(self):
        default = default_config_for_platform()
        logger.info(f"Platform default configuration file: {default}")
        config_files = list(
            itertools.chain(*[p.glob("config.json") for p in self.search_paths])
        ) + [default]
        logger.info(
            f"Using default config search paths: {[str(p.resolve().absolute()) for p in self.search_paths]}"
        )
        logger.info(f"Found: {[str(p.resolve().absolute()) for p in config_files]}")
        self.config = Config(config_files[0], defaults=default)

    async def process_events(self):
        while True:
            # Only really need 30ish FPS UI update rate
            await asyncio.sleep(0.03)
            self.qt_app.processEvents()

    async def master(self):
        logger.info("Started async loop.")
        self.messages = asyncio.Queue()

        if self.cli_config.remote_config:
            logger.info("Running in headless or remoted configuration. Setting up remote")
            self.remote = RemoteLink(
                self,
                self.cli_config.remote_config,
                middleware=[
                    TranslateCommandsMiddleware(),
                    WireMiddleware(),
                ],
            )
            logger.info("Running remote .prepare")
            await self.remote.prepare()
            logger.trace("Starting remote task")
            asyncio.ensure_future(self.remote.run())

        # Start user Actors
        logger.info("Running actor .prepare")
        await asyncio.gather(*[actor.prepare() for actor in self.actors.values()])
        logger.trace("Starting actor tasks")
        for actor in self.actors.values():
            asyncio.ensure_future(actor.run())

        # Start managed instruments
        logger.trace("Running instrument .prepare")
        await asyncio.gather(
            *[instrument.prepare() for instrument in self.managed_instruments.values()]
        )

        logger.trace("Starting instrument tasks")
        for instrument in self.managed_instruments.values():
            asyncio.ensure_future(instrument.run())

        if not USE_QUAMASH and not self.cli_config.headless:
            logger.info("Installing Qt event processing on the standard event loop")
            asyncio.ensure_future(self.process_events())

        self.load_state()

        logger.info("Main task is dropping into event loop")
        self.message_read_task = asyncio.ensure_future(self.read_messages())

    async def read_messages(self):
        while True:
            message = await self.messages.get()
            await self.handle_message(message)
            self.messages.task_done()

    def send_to_remote(self, message):
        if self.remote:
            self.remote.messages.put_nowait(message)
        else:
            logger.trace(f"Dropping outbound: {message}")

    async def handle_message(self, message):
        if not isinstance(message, RemoteCommand):
            logger.warning(f"Unknown message: {message}")
            return

        if isinstance(message, ShutdownCommand):
            await self.shutdown(loop=asyncio.get_event_loop(), signal=message)
        elif isinstance(message, HeartbeatCommand):
            self.send_to_remote(message)
        elif isinstance(message, (ReadAxisCommand, WriteAxisCommand)):
            if self.experiment.current_run is not None:
                await self.experiment.messages.put(message)
            else:
                instrument_name = AxisPath.to_tuple(message.axis_path)[0]
                destination_instrument = self.managed_instruments[instrument_name]
                await destination_instrument.messages.put(message)

        elif isinstance(message, FORWARD_TO_EXPERIMENT_MESSAGE_CLASSES):
            await self.experiment.messages.put(message)
        elif isinstance(message, GetAllStateCommand):
            ins_state = {
                k: ins.collect_remote_state() for k, ins in self.managed_instruments.items()
            }

            extra_types = TypeDefinition.all_types()

            app_state = RemoteApplicationState(
                instruments=ins_state,
                extra_types=extra_types,
                experiment_state=self.experiment.collect_remote_state(),
            )
            self.send_to_remote(AllState(app_state))

    def collect_state(self) -> AutodiDAQtStateAtRest:
        ser_schema = SerializationSchema(
            autodidaqt_version=VERSION,
            user_version=self.config.version,
            app_root=self.app_root,
            commit="",
        )

        try:
            profile = self.user.profile.value
        except:
            profile = None

        return deepcopy(
            AutodiDAQtStateAtRest(
                autodidaqt_state=AppState(
                    user=self.user.user,
                    session_name=self.user.session_name,
                    profile=profile,
                ),
                schema=ser_schema,
                panels={k: p.collect_state() for k, p in self.main_window.open_panels.items()},
                actors={k: a.collect_state() for k, a in self.actors.items()},
                managed_instruments={
                    k: ins.collect_state() for k, ins in self.managed_instruments.items()
                },
            )
        )

    def receive_state(self, state: AutodiDAQtStateAtRest):
        self.app_state = state.autodidaqt_state
        self.user.user = self.app_state.user
        self.user.session_name = self.app_state.session_name

        if self.app_state.profile:
            try:
                self.user.profile = self.profile_enum(self.app_state.profile)
            except (ValueError, AttributeError):
                pass

        for k, p in self.main_window.open_panels.items():
            if k in state.panels:
                p.receive_state(state.panels[k])

        for k, a in self.actors.items():
            if k in state.actors:
                a.receive_state(state.actors[k])

        for k, ins in self.managed_instruments.items():
            if k in state.managed_instruments:
                ins.receive_state(state.managed_instruments[k])

    def load_state(self):  # pragma: no cover
        logger.info("Loading application state.")

        while True:
            state_filename = find_newest_state_filename(self)
            logger.info(f"Found candidate application state: {state_filename}... loading.")
            if not state_filename:
                state = self.collect_state()
                self.receive_state(state)
                return

            with open(str(state_filename), "rb") as state_f:
                try:
                    state: AutodiDAQtStateAtRest = pickle.load(state_f)
                    # successfully found experiment state, we can move on
                    break
                except AttributeError as e:
                    backup_state_location = state_filename.parent / (
                        state_filename.stem + ".pickle.bak"
                    )
                    logger.error(
                        f"Could not load application state, due to {e}. Retaining bad state at {backup_state_location}. Trying older..."
                    )
                    state_filename.rename(backup_state_location)

        self.receive_state(state)

        if not self.cli_config.headless:
            update_dataclass(self.user, prefix="app_user", ui=self.main_window.ui)

        logger.info("Finished loading application state.")

    def save_state(self):  # pragma: no cover
        logger.info("Saving application state.")
        state_filename = generate_state_filename(self)
        state_filename.parent.mkdir(parents=True, exist_ok=True)

        state = self.collect_state()
        with open(str(state_filename), "wb") as state_f:
            pickle.dump(state, state_f)

        logger.info("Finished saving application state.")

    def configure_qt_app(self):  # pragma: no cover
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateCombo, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateMenu, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateToolBox, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateTooltip, False)
        self.font_db = QFontDatabase()

        for font in (Path(__file__).parent / "resources" / "fonts").glob("*.ttf"):
            self.font_db.addApplicationFont(str(font))

        self.qt_app.setStyleSheet(default_stylesheet())

    def configure_event_loop(self):  # pragma: no cover
        logger.info("Configuring async runtime")

        if USE_QUAMASH and not self.cli_config.headless:
            logger.info("Using Quamash for async support.")
            loop = QEventLoop(self.qt_app)
            asyncio.set_event_loop(loop)
        else:
            logger.info("Using asyncio for async support.")
            loop = asyncio.get_event_loop()

        signal_set = {
            "win32": lambda: (),  # windows has no signals, but will raise exceptions
        }.get(sys.platform, lambda: (signal.SIGHUP, signal.SIGTERM, signal.SIGINT))()
        for s in signal_set:
            logger.info("Installing shutdown signal handler for signal {s}")
            loop.add_signal_handler(s, lambda s=s: loop.create_task(self.shutdown(loop, s)))

        logger.info("Setting custom exception handler on async loop")
        loop.set_exception_handler(self.handle_exception)
        return loop

    def start(self):  # pragma: no cover
        logger.info("Application in startup.")
        logger.info(pprint.pformat(self.cli_config))
        logger.info(self.config)
        if self.config.instruments.simulate_instruments:
            logger.warning("AUTOMATICALLY SIMULATING ALL INSTRUMENTS")

        if not self.cli_config.headless:
            logger.info("Configuring Qt application and styles")
            self.configure_qt_app()

        loop = self.configure_event_loop()

        main_window_cls = (
            AutodiDAQtMainWindowHeadless if self.cli_config.headless else AutodiDAQtMainWindow
        )
        self.main_window = main_window_cls(loop=loop, app=self)

        asyncio.ensure_future(self.master())

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            if not self._is_shutdown:
                loop.run_until_complete(self.shutdown(loop, signal=None))
        finally:
            loop.close()
            logger.info("Closed autodidaqt successfully.")
            sys.exit(0)
