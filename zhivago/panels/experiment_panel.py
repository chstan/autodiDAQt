import numpy as np
import pyqtgraph as pg

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from zhivago.panel import Panel
from zhivago.ui import (
    CollectUI, tabs, vertical, horizontal,
    combo_box, button,
    label, bind_dataclass,
    layout_dataclass, splitter)

__all__ = ('ExperimentPanel',)


if False:
    app = None
    QtCore = None

    p = pg.plot()
    p.setWindowTitle('pyqtgraph example: PlotSpeedTest')
    p.setRange(QtCore.QRectF(0, -10, 5000, 20))
    p.setLabel('bottom', 'Index', units='B')
    curve = p.plot()

    data = np.random.normal(size=(50,5000))
    ptr = 0

    def update():
        global curve, data, ptr, p
        curve.setData(data[ptr%10])
        ptr += 1

        app.processEvents()

class ExperimentPanel(Panel):
    SIZE = (900, 450)
    TITLE = 'Experiment'
    DEFAULT_OPEN = True
    RESTART = True

    def layout_scan_methods(self, methods):
        return [[m.__name__ , layout_dataclass(m)] for m in methods]

    @property
    def experiment(self):
        # better to configure things so panels can be associated 1-to-1 with actors
        # at setup time otherwise this will break or require runtime type inspection
        return self.app.actors['experiment']

    def enter_running(self):
        """
        Update the UI elements featuring the UI state.
        :return:
        """
        self.ui['status-box'].setText('Running...')

    def enter_paused(self):
        """
        Update the UI elements featuring the UI state.
        :return:
        """
        self.ui['status-box'].setText('Paused...')

    def enter_idle(self):
        """
        Unmount the data browsing part of the UI. This is because data is now stale and we
        don't know if the same axes will even be present in subsequent scans.
        :return:
        """
        self.ui['status-box'].setText('Waiting...')

    def soft_update(self):
        """
        Here, we update the UI tree so it includes the newly
        published data. This amounts to traversing the UI, taking the newly
        published data, and calling the pyqtgraph `.set_data` function as appropriate.
        :return:
        """
        dynamic_layout_container = self.ui['dynamic-layout']
        dynamic_layout = dynamic_layout_container.layout()

        if not self.dynamic_state_mounted:
            self.dynamic_state_mounted = True

            # clear the layout
            for i in reversed(range(dynamic_layout.count())):
                dynamic_layout.itemAt(i).widget().setParent(None)

            key_sequences = self.experiment.current_run.daq_values.keys()

            # ('a', 0, 'b') -> 'a[0].b'
            display_names = {ks: '.'.join([k if isinstance(k, str) else f' [{k}] '
                                           for k in ks]).replace('. ', '').replace(' .', '').strip()
                             for ks in key_sequences}

            self.built_widgets = {}
            self.pg_widgets = {}
            self.pg_plots = {}
            self.image_like = {
                k: isinstance(self.experiment.current_run.streaming_daq_ys[k][0], np.ndarray)
                for k in display_names
            }

            def build_widget_for(key_name, display_name, image_like=False):
                if image_like:
                    pg_widget = pg.ImageView()
                    img = pg.ImageItem()
                    pg_widget.addItem(img)
                    self.pg_plots[key_name] = img
                else:
                    pg_widget = pg.PlotWidget()
                    self.pg_plots[key_name] = pg_widget.plot()#np.ndarray((0,),dtype=float), np.ndarray((0,),dtype=float))
                    pg_widget.setTitle(display_name)

                widget = vertical(
                    pg_widget,
                )
                self.built_widgets[key_name] = widget
                self.pg_widgets[key_name] = pg_widget
                return widget

            data_stream_views = tabs(
                *[[v, build_widget_for(k, v, self.image_like[k])] for k, v in display_names.items()]
            )
            dynamic_layout.addWidget(data_stream_views)

        for k in self.built_widgets:
            pg_plot = self.pg_plots[k]

            xs, ys = (self.experiment.current_run.streaming_daq_xs[k],
                      self.experiment.current_run.streaming_daq_ys[k])
            if self.image_like[k]:
                pg_plot.setImage(ys[-1])
            else:
                pg_plot.setData(np.asarray(xs), np.asarray(ys))

        # force UI rerender

    def running_to_idle(self):
        self.dynamic_state_mounted = False

    def layout(self):
        experiment = self.experiment
        self.experiment.ui = self
        scan_methods = experiment.scan_methods

        ui = {}
        LEFT_PANEL_SIZE = 200
        with CollectUI(ui):
            vertical(
                horizontal(
                    button('Start', id='start'),
                    button('Pause', id='pause'),
                    button('Stop', id='stop'),
                    label('Waiting...', id='status-box'),
                ),
                splitter(
                    vertical(
                        horizontal(
                            'Use',
                            combo_box([s.__name__ for s in scan_methods], id='selected_scan_method'),
                        ),
                        tabs(
                            ['Status', vertical('Status')],
                            ['Scans', tabs(
                                *self.layout_scan_methods(scan_methods)
                            )],
                        ),
                    ),
                    vertical(
                        '[Data Streams]',
                        id='dynamic-layout',
                    ),
                    direction=splitter.Horizontal,
                    size=[LEFT_PANEL_SIZE, self.SIZE[0] - LEFT_PANEL_SIZE]
                ),
                widget=self,
            )

        for scan_method in scan_methods:
            name = scan_method.__name__
            bind_dataclass(experiment.scan_configuration[name], prefix=name + '.', ui=ui)

        ui['start'].subject.subscribe(self.start)
        ui['stop'].subject.subscribe(self.stop)
        ui['pause'].subject.subscribe(self.pause)

        ui['selected_scan_method'].subject.on_next(experiment.use_method)
        ui['selected_scan_method'].subject.subscribe(self.set_scan_method)

        self.ui = ui
        self.dynamic_state_mounted = False

    def set_scan_method(self, scan_method):
        self.experiment.use_method = scan_method

    def start(self, *_):
        self.experiment.messages.put_nowait('start')

    def stop(self, *_):
        self.experiment.messages.put_nowait('stop')

    def pause(self, *_):
        self.experiment.messages.put_nowait('pause')
