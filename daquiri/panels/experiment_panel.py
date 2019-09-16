import numpy as np
import pyqtgraph as pg

from daquiri.panel import Panel
from daquiri.ui import (
    CollectUI, tabs, vertical, horizontal,
    combo_box, button,
    label, bind_dataclass,
    layout_dataclass, splitter)

__all__ = ('ExperimentPanel',)

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


class ExperimentPanel(Panel):
    SIZE = (900, 450)
    TITLE = 'Experiment'
    DEFAULT_OPEN = True
    RESTART = True
    LEFT_PANEL_SIZE: int = 200

    dynamic_state_mounted: bool = False
    built_widgets = None
    pg_widgets = None
    pg_plots = None
    plot_type = None
    additional_plots = None
    ui = None

    @staticmethod
    def layout_scan_methods(methods):
        return [[m.__name__, layout_dataclass(m)] for m in methods]

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

            # TODO we can clean this up so that there is a common way of collecting and plotting everything
            # currently we special case what happens for user plots in order to avoid computational expense at the
            # expense of memory and code length
            self.built_widgets = {}
            self.pg_widgets = {}
            self.pg_plots = {}
            self.user_pg_widgets = {}
            self.user_pg_plots = {}

            self.plot_type = {
                k: 'image' if isinstance(self.experiment.current_run.streaming_daq_ys[k][0], np.ndarray) else 'line'
                for k in display_names
            }
            self.additional_plots = self.experiment.current_run.additional_plots

            for additional_plot in self.additional_plots:
                dependent_is_image_like = isinstance(self.experiment.current_run.streaming_daq_ys[additional_plot['dependent']][0], np.ndarray)
                assert not dependent_is_image_like and 'Cannot plot 1D/2D vs 2D data currently'
                independent_is_image_like = len(additional_plot['independent']) >= 2

                if dependent_is_image_like:
                    self.plot_type[additional_plot['name']] = 'image'
                elif independent_is_image_like:
                    self.plot_type[additional_plot['name']] = '2d-scatter'
                else:
                    self.plot_type[additional_plot['name']] = 'line'

            def build_widget_for(display_name, plot_type: str = 'line'):
                if plot_type == 'image':
                    pg_widget = pg.ImageView()
                    pg_plt = pg.ImageItem()
                    pg_widget.addItem(pg_plt)
                elif plot_type == 'line':
                    pg_widget = pg.PlotWidget()
                    pg_plt = pg_widget.plot()
                    pg_widget.setTitle(display_name)
                else:
                    assert plot_type == '2d-scatter'
                    pg_widget = pg.PlotWidget()
                    pg_plt = pg.ScatterPlotItem()
                    pg_widget.addItem(pg_plt)

                return vertical(pg_widget), pg_widget, pg_plt

            tab_widgets = []

            for additional_plot in self.additional_plots:
                name, ind, dep = [additional_plot[k] for k in ['name', 'independent', 'dependent']]
                widget, pg_widget, pg_plt = build_widget_for(name, self.plot_type[name])
                self.built_widgets[name] = widget
                self.user_pg_widgets[name] = pg_widget
                self.user_pg_plots[name] = pg_plt
                tab_widgets.append((name, widget,))

            for k, display_name in display_names.items():
                widget, pg_widget, pg_plt = build_widget_for(display_name, self.plot_type[k])
                self.built_widgets[k] = widget
                self.pg_widgets[k] = pg_widget
                self.pg_plots[k] = pg_plt
                tab_widgets.append((display_name, widget,))

            data_stream_views = tabs(*tab_widgets)
            dynamic_layout.addWidget(data_stream_views)

        for k in self.pg_plots:
            pg_plot = self.pg_plots[k]

            xs, ys = (self.experiment.current_run.streaming_daq_xs[k],
                      self.experiment.current_run.streaming_daq_ys[k])
            if self.plot_type[k] == 'image':
                pg_plot.setImage(ys[-1])
            else:
                assert self.plot_type[k] == 'line'
                pg_plot.setData(np.asarray(xs), np.asarray(ys))

        for additional_plot in self.additional_plots:
            name, ind, dep = [additional_plot[k] for k in ['name', 'independent', 'dependent']]
            pg_plot = self.user_pg_plots[name]
            if len(ind) > 1:
                last_index = additional_plot.get('last_index', 0)
                color = additional_plot.get('color')
                size = additional_plot.get('size', np.abs)

                xss = np.stack([self.experiment.current_run.streaming_daq_ys[indi][last_index:] for indi in ind])
                ys = self.experiment.current_run.streaming_daq_ys[dep][last_index:]

                additional_plot['last_index'] = last_index + len(ys)

                def make_spot(index, y):
                    s = {'pos': xss[:, index], 'data': y, 'size': size(y)}
                    if color:
                        s['color'] = color(y)
                    return s

                pg_plot.addPoints([make_spot(i, y) for i, y in enumerate(ys)])
            else:
                xs, ys = (self.experiment.current_run.streaming_daq_ys[ind[0]],
                          self.experiment.current_run.streaming_daq_ys[dep])
                pg_plot.setData(np.asarray(xs), np.asarray(ys))

    def running_to_idle(self):
        self.dynamic_state_mounted = False

    def layout(self):
        experiment = self.experiment
        self.experiment.ui = self
        scan_methods = experiment.scan_methods

        ui = {}
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
                    size=[self.LEFT_PANEL_SIZE, self.SIZE[0] - self.LEFT_PANEL_SIZE]
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
