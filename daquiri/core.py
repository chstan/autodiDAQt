import asyncio
import itertools
import multiprocessing
import pickle
import signal
import sys
import traceback
import warnings
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field, make_dataclass
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import appdirs
from asyncqt import QEventLoop
from dotenv import load_dotenv
from loguru import logger
from PyQt5 import QtCore
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from pyqt_led import Led
from rx.subject import Subject

from daquiri.actor import Actor
from daquiri.config import Config, MetaData, default_config_for_platform
from daquiri.instrument import ManagedInstrument
from daquiri.panel import Panel
from daquiri.panels import InstrumentManager
from daquiri.state import (AppState, DaquiriStateAtRest, SerializationSchema,
                           find_newest_state_filename, generate_state_filename)
from daquiri.ui import (CollectUI, bind_dataclass, button, horizontal,
                        layout_dataclass, led, update_dataclass, vertical)
from daquiri.utils import default_stylesheet
from daquiri.version import VERSION

__all__ = (
    "Daquiri",
)

USE_QUAMASH = False


class DaquiriMainWindow(QMainWindow):
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
        super(DaquiriMainWindow, self).__init__()
        self.app = app

        self._panels = {
            k: {"panel": None, "running": False, "indicator": None, "restart": None,}
            for k in self.app.panel_definitions.keys()
        }

        self.panel_order = sorted(list(self._panels.keys()))

        # set layout
        self.win = QWidget()
        self.win.resize(
            50, 50
        )  # smaller than minimum size, so will resize appropriately

        self.ui = {}
        with CollectUI(self.ui):
            vertical(
                horizontal(
                    vertical(
                        *[
                            button(
                                "Restart {}".format(
                                    self.app.panel_definitions[panel_name].TITLE
                                ),
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
        self.win.setWindowTitle("DAQuiri")

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

class Daquiri:
    """
    The main application instance for your Daquiri apps.

    Lifecycle hooks. Daquiri does not explicitly provide lifecycle hooks.
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

    def __init__(
        self,
        import_name,
        panel_definitions: Optional[Dict[str, Type[Panel]]] = None,
        actors: Optional[Dict[str, Type[Actor]]] = None,
        managed_instruments: Optional[Dict[str, Type[ManagedInstrument]]] = None,
        DEBUG: Optional[bool] = None,
    ):
        import daquiri.globals

        daquiri.globals.APP = self

        if panel_definitions is None:
            panel_definitions = {}

        if actors is None:
            actors = {}

        if managed_instruments is None:
            managed_instruments = {}

        if managed_instruments:
            if not any(
                issubclass(panel_def, InstrumentManager)
                for panel_def in panel_definitions.values()
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
            warnings.warn(
                f"Overwriting the value of DEBUG from configuration, using {DEBUG}"
            )
            self.config.DEBUG = DEBUG

    def handle_exception(self, loop, context):
        """
        Attempts to recover from, log, or otherwise deal with an exception inside the
        async portions of Daquiri.
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

    async def shutdown(self, loop, signal=None):
        """
        Args:
            loop: The running event loop.
            signal: The signal received which triggered application shutdown.

        Returns:
            None
        """
        self._is_shutdown = True
        self.process_pool.shutdown(wait=True)

        if signal:
            logger.info(f"Received exit signal {signal.name}.")
        else:
            logger.info("Shutting down due to exception.")

        logger.info("Saving...")

        self.save_state()

        tasks = [
            t
            for t in asyncio.all_tasks(loop=loop)
            if t is not asyncio.current_task(loop=loop)
        ]
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

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
        return getattr(
            sys.modules[self.import_name], "__file__", appdirs.user_config_dir()
        )

    @property
    def search_paths(self):
        p = Path(self.file)
        return [
            p.parent.absolute(),
            p.parent.parent.absolute(),
            p.parent.parent.absolute() / "config",
        ]

    def extract_from_dotenv(self):
        dotenv_files = list(
            itertools.chain(*[p.glob(".env") for p in self.search_paths])
        )
        if dotenv_files:
            load_dotenv(str(dotenv_files[0]))

    def load_config(self):
        default = default_config_for_platform()
        config_files = list(
            itertools.chain(*[p.glob("config.json") for p in self.search_paths])
        ) + [default]
        self.config = Config(config_files[0], defaults=default)

    async def process_events(self):
        while True:
            # Only really need 30ish FPS UI update rate
            await asyncio.sleep(0.03)
            self.qt_app.processEvents()

    async def master(self):
        logger.info("Started async loop.")
        self.messages = asyncio.Queue()

        # Start user Actors
        await asyncio.gather(*[actor.prepare() for actor in self.actors.values()])
        for actor in self.actors.values():
            asyncio.ensure_future(actor.run())

        # Start managed instruments
        await asyncio.gather(
            *[instrument.prepare() for instrument in self.managed_instruments.values()]
        )
        for instrument in self.managed_instruments.values():
            asyncio.ensure_future(instrument.run())

        if not USE_QUAMASH:
            asyncio.ensure_future(self.process_events())

        self.load_state()

        while True:
            message = await self.messages.get()
            logger.info(message)

    def collect_state(self) -> DaquiriStateAtRest:
        ser_schema = SerializationSchema(
            daquiri_version=VERSION,
            user_version=self.config.version,
            app_root=self.app_root,
            commit="",
        )

        try:
            profile = self.user.profile.value
        except:
            profile = None

        return deepcopy(
            DaquiriStateAtRest(
                daquiri_state=AppState(
                    user=self.user.user,
                    session_name=self.user.session_name,
                    profile=profile,
                ),
                schema=ser_schema,
                panels={
                    k: p.collect_state()
                    for k, p in self.main_window.open_panels.items()
                },
                actors={k: a.collect_state() for k, a in self.actors.items()},
                managed_instruments={
                    k: ins.collect_state()
                    for k, ins in self.managed_instruments.items()
                },
            )
        )

    def receive_state(self, state: DaquiriStateAtRest):
        self.app_state = state.daquiri_state
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

    def load_state(self): # pragma: no cover
        logger.info("Loading application state.")
        state_filename = find_newest_state_filename(self)
        if not state_filename:
            state = self.collect_state()
            self.receive_state(state)
            return

        with open(str(state_filename), "rb") as state_f:
            state: DaquiriStateAtRest = pickle.load(state_f)

        self.receive_state(state)
        update_dataclass(self.user, prefix="app_user", ui=self.main_window.ui)

    def save_state(self): # pragma: no cover
        logger.info("Saving application state.")
        state_filename = generate_state_filename(self)
        state_filename.parent.mkdir(parents=True, exist_ok=True)

        state = self.collect_state()
        with open(str(state_filename), "wb") as state_f:
            pickle.dump(state, state_f)

    def start(self): # pragma: no cover
        logger.info("Application in startup.")
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateCombo, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateMenu, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateToolBox, False)
        self.qt_app.setEffectEnabled(QtCore.Qt.UI_AnimateTooltip, False)
        self.font_db = QFontDatabase()

        for font in (Path(__file__).parent / "resources" / "fonts").glob("*.ttf"):
            self.font_db.addApplicationFont(str(font))

        self.qt_app.setStyleSheet(default_stylesheet())

        if USE_QUAMASH:
            loop = QEventLoop(self.qt_app)
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()

        signal_set = {
            "win32": lambda: (),  # windows has no signals, but will raise exceptions
        }.get(sys.platform, lambda: (signal.SIGHUP, signal.SIGTERM, signal.SIGINT))()
        for s in signal_set:
            loop.add_signal_handler(
                s, lambda s=s: loop.create_task(self.shutdown(loop, s))
            )

        self.main_window = DaquiriMainWindow(loop=loop, app=self)
        main_task = asyncio.ensure_future(self.master())

        loop.set_exception_handler(self.handle_exception)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            if not self._is_shutdown:
                loop.run_until_complete(self.shutdown(loop, signal=None))
        finally:
            loop.close()
            logger.info("Closed DAQuiri successfully.")
