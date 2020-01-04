import asyncio
import sys
import warnings
import itertools
import signal
import appdirs
from typing import Dict, Optional, Type

from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pyqt_led import Led
from rx.subject import Subject
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5 import QtCore
from quamash import QEventLoop

from daquiri.config import Config, MetaData
from daquiri.panel import Panel

from daquiri.actor import Actor
from daquiri.instrument import ManagedInstrument
from daquiri.panels import InstrumentManager
from daquiri.ui import led, button, vertical, horizontal, CollectUI


__all__ = ('Daquiri',)


class DaquiriMainWindow(QMainWindow):
    """
    Internal, the PyQt main window
    """
    def client_panel_will_close(self, name):
        self._panels[name]['indicator'].set_status(False)
        self._panels[name]['indicator'].update()

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

        self._log_handler = None
        self.log_file = None
        self.setup_logging()

        self.panel_definitions = panel_definitions
        self.main_window = None
        self.qt_app = None
        self.messages = Subject()
        self.actors = {k: A(app=self) for k, A in actors.items()}
        self.managed_instruments = {k: A(app=self) for k, A in managed_instruments.items()}
        self.managed_instrument_classes = managed_instruments

        if DEBUG is not None and self.config.DEBUG != DEBUG:
            warnings.warn(f'Overwriting the value of DEBUG from configuration, using {DEBUG}')
            self.config.DEBUG = DEBUG

    def handle_exception(self, loop, context, old):
        """
        Attempts to recover from, log, or otherwise deal with an exception inside the
        async portions of Daquiri.
        """

        print('Handling.')
        message = context.get('exception', context['message'])
        logger.error(f"Caught: {message}")
        loop.create_task(self.shutdown(loop, signal=None))
        old(context)

    async def shutdown(self, loop, signal=None):
        """
        Args:
            loop: The running event loop.
            signal: The signal received which triggered application shutdown.

        Returns:
            None
        """
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
        from daquiri.utils import DAQUIRI_LIB_ROOT

        configs = {'win32': 'default_config_windows.json',}
        cfile = configs.get(sys.platform, 'default_config.json')
        defaults_path = DAQUIRI_LIB_ROOT / 'resources' / cfile
        config_files = list(itertools.chain(*[p.glob('config.json') for p in self.search_paths])) + [defaults_path]
        self.config = Config(config_files[0])

    async def master(self):
        logger.info('Started async loop.')
        self.messages = asyncio.Queue()

        # Start user Actors
        await asyncio.gather(*[actor.prepare() for actor in self.actors.values()])
        for actor in self.actors.values(): asyncio.ensure_future(actor.run())

        # Start managed instruments
        await asyncio.gather(*[instrument.prepare() for instrument in self.managed_instruments.values()])
        for instrument in self.managed_instruments.values(): asyncio.ensure_future(instrument.run())

        while True:
            message = await self.messages.get()
            logger.info(message)

    def start(self):
        self.qt_app = QApplication(sys.argv)
        loop = QEventLoop(self.qt_app)

        asyncio.set_event_loop(loop)

        signal_set = {
            'win32': lambda: tuple(), # windows has no signals, but will raise exceptions
        }.get(sys.platform, lambda: (signal.SIGHUP, signal.SIGTERM, signal.SIGINT))()
        for s in signal_set:
            loop.add_signal_handler(s, lambda s=s: loop.create_task(self.shutdown(loop, s)))

        self.main_window = DaquiriMainWindow(loop=loop, app=self)

        asyncio.ensure_future(self.master())

        with loop:
            loop.run_forever()

        self.main_window.show()