import pickle
import asyncio
import sys
import warnings
import itertools
import signal
import appdirs
from copy import deepcopy
from typing import Dict, Optional, Type

from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pyqt_led import Led
from rx.subject import Subject
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5 import QtCore
from asyncqt import QEventLoop

from daquiri.config import Config, MetaData, default_config_for_platform
from daquiri.panel import Panel

from daquiri.actor import Actor
from daquiri.instrument import ManagedInstrument
from daquiri.panels import InstrumentManager
from daquiri.state import DaquiriStateAtRest, generate_state_filename, find_newest_state_filename, SerializationSchema, \
    AppState
from daquiri.ui import led, button, vertical, horizontal, CollectUI
from daquiri.version import VERSION

__all__ = ('Daquiri',)


USE_QUAMASH = False

class DaquiriMainWindow(QMainWindow):
    """
    Internal, the PyQt main window
    """
    def client_panel_will_close(self, name):
        self._panels[name]['indicator'].set_status(False)
        self._panels[name]['indicator'].update()

    @property
    def open_panels(self) -> Dict[str, Panel]:
        return {name: self._panels[name]['panel']
                for name in self._panels if self._panels[name]['panel']}

    def launch_panel(self, name):
        logger.info(f'Opening panel {name}')
        if self._panels[name]['panel'] is None:
            panel_cls = self.app.panel_definitions[name]
            w = panel_cls(parent=self, id=name, app=self.app)
            self._panels[name]['panel'] = w
            w.show()
        else:
            # for now, focus the panel
            w = self._panels[name]['panel']
            w.setWindowState(
                w.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive | QtCore.Qt.WindowStaysOnTopHint)
            w.activateWindow()
            w.show()
            w.setWindowFlags(w.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
            w.show()

        indicator = self._panels[name]['indicator']
        indicator.turn_on()
        indicator.update()

    def __init__(self, loop, app):
        super(DaquiriMainWindow, self).__init__()
        self.app = app

        self._panels = {
            k: {
                'panel': None,
                'running': False,
                'indicator': None,
                'restart': None,
            }
            for k in self.app.panel_definitions.keys()
        }

        self.panel_order = sorted(list(self._panels.keys()))

        # set layout
        self.win = QWidget()
        self.win.resize(50, 50) # smaller than minimum size, so will resize appropriately

        ui = {}
        with CollectUI(ui):
            horizontal(
                vertical(
                    *[button('Restart {}'.format(self.app.panel_definitions[panel_name].TITLE),
                             id=f'restart-{panel_name}') for panel_name in self.panel_order]
                ),
                vertical(
                    *[led(None, shape=Led.circle, id='indicator-{}'.format(panel_name))
                      for panel_name in self.panel_order]
                ),
                widget=self.win,
            )

        for k in self.panel_order:
            def bind_panel(name):
                return lambda _: self.launch_panel(name=name)

            ui[f'restart-{k}'].subject.subscribe(bind_panel(k))
            self._panels[k]['indicator'] = ui[f'indicator-{k}']
            self._panels[k]['restart'] = ui[f'restart-{k}']

        self.win.show()
        self.win.setWindowTitle('DAQuiri')

        for panel_name, panel_cls in self.app.panel_definitions.items():
            if panel_cls.DEFAULT_OPEN:
                self.launch_panel(panel_name)

        self.loop = loop


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

    def __init__(self, import_name, panel_definitions: Optional[Dict[str, Type[Panel]]] = None,
                 actors: Optional[Dict[str, Type[Actor]]] = None,
                 managed_instruments: Optional[Dict[str, Type[ManagedInstrument]]] = None,
                 DEBUG: Optional[bool] = None):
        import daquiri.globals
        daquiri.globals.APP = self

        if panel_definitions is None:
            panel_definitions = {}

        if actors is None:
            actors = {}

        if managed_instruments is None:
            managed_instruments = {}

        if managed_instruments:
            if not any(issubclass(panel_def, InstrumentManager) for panel_def in panel_definitions.values()):
                panel_definitions['_instrument_manager'] = InstrumentManager

        for actor_name, actor in actors.items():
            if actor.panel_cls is not None:
                assert actor_name not in  panel_definitions
                panel_definitions[actor_name] = actor.panel_cls

        self.events = Subject()

        self.config = None
        self.import_name = import_name
        self.extract_from_dotenv()
        self.load_config()
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
                'driver_init': {
                    'args': self.config.instruments.nested_get([instrument_key, 'initialize', 'args'], []),
                    'kwargs': self.config.instruments.nested_get([instrument_key, 'initialize', 'kwargs'], {}),
                },
            }

        self.actors: Dict[str, Actor] = {k: A(app=self) for k, A in actors.items()}
        self.managed_instruments: Dict[str, ManagedInstrument] = {
            k: A(app=self, **lookup_managed_instrument_args(k)) for k, A in managed_instruments.items()}
        self.managed_instrument_classes = managed_instruments

        if DEBUG is not None and self.config.DEBUG != DEBUG:
            warnings.warn(f'Overwriting the value of DEBUG from configuration, using {DEBUG}')
            self.config.DEBUG = DEBUG

    def handle_exception(self, loop, context):
        """
        Attempts to recover from, log, or otherwise deal with an exception inside the
        async portions of Daquiri.
        """
        print(loop)
        message = context.get('exception', context['message'])
        logger.error(f"Caught Unhandled: {message}")

        if self._is_shutdown:
            return

        try:
            other_loop = asyncio.get_running_loop()
            print(loop, other_loop)
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

        if signal:
            logger.info(f'Received exit signal {signal.name}.')
        else:
            logger.info('Shutting down due to exception.')

        logger.info('Saving...')

        tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
        for task in tasks: task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    def setup_logging(self):
        logger.add(sys.stderr, format="{time} {level} {message}", level="WARNING")
        self.log_file = self.app_root / self.config.logging_directory / self.config.log_format.format(
            user='global-log',
            time=self.meta.datetime_started,
            session='global-session',
        )
        self._log_handler = logger.add(self.log_file)

    @property
    def app_root(self):
        return Path(self.file).parent.parent.absolute()

    @property
    def name(self):
        if self.import_name == '__main__':
            print('here')
            module_file = getattr(sys.modules['__main__'], '__file__', None)
            if module_file is None:
                return self.import_name
            return Path(module_file).stem
        return self.import_name

    @property
    def file(self):
        return getattr(sys.modules[self.import_name], '__file__',
                       appdirs.user_config_dir())

    @property
    def search_paths(self):
        p = Path(self.file)
        return [p.parent.absolute(),
                p.parent.parent.absolute(),
                p.parent.parent.absolute() / 'config']

    def extract_from_dotenv(self):
        dotenv_files = list(itertools.chain(*[p.glob('.env') for p in self.search_paths]))
        if dotenv_files:
            load_dotenv(str(dotenv_files[0]))

    def load_config(self):
        default = default_config_for_platform()
        config_files = list(itertools.chain(*[p.glob('config.json') for p in self.search_paths])) + []
        self.config = Config(config_files[0], defaults=default)

    async def process_events(self):
        while True:
            await asyncio.sleep(0)
            self.qt_app.processEvents()

    async def master(self):
        logger.info('Started async loop.')
        self.messages = asyncio.Queue()

        # Start user Actors
        await asyncio.gather(*[actor.prepare() for actor in self.actors.values()])
        for actor in self.actors.values(): asyncio.ensure_future(actor.run())

        # Start managed instruments
        await asyncio.gather(*[instrument.prepare() for instrument in self.managed_instruments.values()])
        for instrument in self.managed_instruments.values(): asyncio.ensure_future(instrument.run())

        if not USE_QUAMASH:
            asyncio.ensure_future(self.process_events())

        self.load_state()

        while True:
            message = await self.messages.get()
            logger.info(message)

    def collect_state(self) -> DaquiriStateAtRest:
        ser_schema = SerializationSchema(
            daquiri_version=VERSION, user_version=self.config.version,
            app_root=self.app_root, commit='')

        return deepcopy(DaquiriStateAtRest(
            daquiri_state=self.app_state,
            schema=ser_schema,
            panels={k: p.collect_state() for k, p in self.main_window.open_panels.items()},
            actors={k: a.collect_state() for k, a in self.actors.items()},
            managed_instruments={k: ins.collect_state() for k, ins in self.managed_instruments.items()},
        ))

    def receive_state(self, state: DaquiriStateAtRest):
        self.app_state = state.daquiri_state

        for k, p in self.main_window.open_panels.items():
            if k in state.panels:
                p.receive_state(state.panels[k])

        for k, a in self.actors.items():
            if k in state.panels:
                a.receive_state(state.actors[k])

        for k, ins in self.managed_instruments.items():
            if k in state.panels:
                ins.receive_state(state.managed_instruments[k])

    def load_state(self):
        state_filename = find_newest_state_filename(self)
        if not state_filename:
            state = self.collect_state()
            self.receive_state(state)
            return

        with open(str(state_filename), 'rb') as state_f:
            state: DaquiriStateAtRest = pickle.load(state_f)

        self.receive_state(state)

    def save_state(self):
        state_filename = generate_state_filename(self)
        state = self.collect_state()
        with open(str(state_filename), 'wb') as state_f:
            pickle.dump(state, state_f)

    def start(self):
        self.qt_app = QApplication(sys.argv)
        if USE_QUAMASH:
            loop = QEventLoop(self.qt_app)
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()

        signal_set = {
            'win32': lambda: (), # windows has no signals, but will raise exceptions
        }.get(sys.platform, lambda: (signal.SIGHUP, signal.SIGTERM, signal.SIGINT))()
        for s in signal_set:
            loop.add_signal_handler(s, lambda s=s: loop.create_task(self.shutdown(loop, s)))

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
            logger.info('Closed DAQuiri successfully.')
