from PyQt5 import QtCore

from loguru import logger
from pyqt_led import Led

from daquiri.panel import Panel
from daquiri.ui import grid, CollectUI, horizontal, vertical, button, led

__all__ = ('InstrumentManager',)


class InstrumentManager(Panel):
    TITLE = 'Instruments'
    SIZE = (50, 50)
    DEFAULT_OPEN = True

    def client_panel_will_close(self, name):
        self._panels[name]['indicator'].set_status(False)
        self._panels[name]['indicator'].update()

    def launch_panel(self, name):
        logger.info(f'Instrument Manager: Opening panel {name}')

        if self._panels[name]['panel'] is None:
            # Open
            panel_cls = self.app.managed_instruments[name].panel_cls
            w = panel_cls(parent=self, id=name, app=self.app,
                          instrument_actor=self.app.managed_instruments[name],
                          instrument_description=self.app.managed_instruments[name].ui_specification)
            self.app.managed_instruments[name].panel = w
            self._panels[name]['panel'] = w
            w.show()
        else:
            # Focus
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, defer_layout=True, **kwargs)

        self._panels = {
            k: {
                'panel': None,
                'running': False,
                'indicator': None,
                'restart': None,
            } for k, C in self.app.managed_instrument_classes.items()
        }
        self.panel_order = sorted(list(self._panels.keys()))

        self.layout()
        self.resize(*self.SIZE)
        self.open_default_panels()

    def open_default_panels(self):
        for panel_name in self._panels.keys():
            panel_cls = self.app.managed_instruments[panel_name].panel_cls
            if panel_cls.DEFAULT_OPEN:
                self.launch_panel(panel_name)

    def layout(self):
        ui = {}
        with CollectUI(ui):
            grid(
                'Instrument Manager',
                horizontal(
                    vertical(*[button(f'Restart {panel_name}', id=f'restart-{panel_name}')
                               for panel_name in self.panel_order]),
                    vertical(*[led(None, shape=Led.circle, id='indicator-{}'.format(panel_name))
                               for panel_name in self.panel_order]),
                ),
                widget=self,
            )

        for k in self.panel_order:
            def bind_panel(name):
                return lambda _: self.launch_panel(name=name)

            ui[f'restart-{k}'].subject.subscribe(bind_panel(k))
            self._panels[k]['indicator'] = ui[f'indicator-{k}']
            self._panels[k]['restart'] = ui[f'restart-{k}']