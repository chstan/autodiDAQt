import dataclasses
import datetime
import math
from typing import Tuple
from copy import copy

import numpy as np
import pyqtgraph as pg

from daquiri.panel import Panel
from daquiri.ui import (
    CollectUI, tabs, vertical, horizontal,
    combo_box, button,
    label, bind_dataclass,
    layout_dataclass, splitter, group)

__all__ = ('ExperimentPanel',)

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


def timedelta_to_tuple(delta: datetime.timedelta) -> Tuple[int, int, float]:
    secs = delta.total_seconds()
    secs, rest = int(math.floor(secs)), secs - math.floor(secs)
    hours, remainder = divmod(secs, 3600)
    minutes, remainder = divmod(remainder, 60)
    return hours, minutes, remainder + rest


def format_delta(h, m, s):
    return f'{h}:{m}:{s:.1f}' if h else (f'{m}:{s:.1f}' if m else f'{s:.1f}')


class ExperimentPanel(Panel):
    """
    Responsible for drawing the UI for an "Experiment".

    You can extend this by subclassing the UI and changing `extra_panels` or by redefining the behavior of
    the layout function, as is appropriate for your application. If you find yourself needing to make serious
    modifications you can make a feature request or suggest a reorg of the code.
    """
    SIZE = (1400, 450)
    TITLE = 'Experiment'
    DEFAULT_OPEN = True
    RESTART = True
    LEFT_PANEL_SIZE: int = 400

    extra_panels = []
    dynamic_state_mounted: bool = False
    built_widgets = None
    pg_widgets = None
    pg_plots = None
    plot_type = None
    additional_plots = None

    ui = None
    timing_ui = None
    queue_ui = None

    pause_stack = None
    frame_times = []

    @staticmethod
    def layout_scan_methods(methods):
        return [[m.__name__, layout_dataclass(m)] for m in methods]

    @property
    def experiment(self):
        # better to configure things so panels can be associated 1-to-1 with actors
        # at setup time otherwise this will break or require runtime type inspection
        return self.app.actors['experiment']

    @property
    def efficiency(self):
        pause_time, running_time = datetime.timedelta(0), datetime.timedelta(0)

        state, current_time = self.pause_stack[0]
        for new_state, transition_time in self.pause_stack[1:]:
            if state == 'Start':
                running_time += (transition_time - current_time)
            else:
                pause_time += (transition_time - current_time)

            state, current_time = new_state, transition_time

        if state == 'Start':
            running_time += datetime.datetime.now() - current_time
        else:
            pause_time += datetime.datetime.now() - current_time

        try:
            eff = running_time.total_seconds() / (
                    running_time.total_seconds() + pause_time.total_seconds())
        except ZeroDivisionError:
            eff = 0

        return eff, running_time, pause_time

    def enter_running(self):
        """
        Update the UI elements featuring the UI state.
        """
        self.pause_stack.append(['Start', datetime.datetime.now()])
        self.update_timing_ui()
        self.update_queue_ui()
        self.ui['status-box'].setText('Running...')

    def enter_paused(self):
        """
        Update the UI elements featuring the UI state.
        """
        self.frame_times = []
        self.pause_stack.append(['Paused', datetime.datetime.now()])
        self.update_timing_ui()
        self.ui['status-box'].setText('Paused...')

    def enter_idle(self):
        """
        Unmount the data browsing part of the UI. This is because data is now stale and we
        don't know if the same axes will even be present in subsequent scans.
        """
        self.pause_stack = []
        self.frame_times = []
        self.update_timing_ui()
        self.ui['status-box'].setText('Waiting...')

    def update_timing_ui(self):
        completed_points, n_points = self.experiment.current_progress

        if not self.pause_stack:
            if n_points is None:
                n_points = '[UNKNOWN]'

            self.timing_ui['timing-label'].setText(f'{n_points} Points')
            return

        efficiency, total_runtime, total_pausetime = self.efficiency
        if self.pause_stack[-1][0] == 'Start':
            # running...
            runtime = format_delta(*timedelta_to_tuple(total_runtime))
            pointrate = 0.
            points_progress = ''
            time_remaining = ''

            if n_points is not None:
                points_progress = f'{completed_points}/{n_points}'
                try:
                    n_frames = min(len(self.frame_times), 10)
                    start_frame = self.frame_times[-n_frames]
                    per_frame_time = (datetime.datetime.now() - start_frame) / n_frames

                    remaining = (n_points - completed_points) * per_frame_time
                    time_remaining = format_delta(*timedelta_to_tuple(remaining))
                    pointrate = 1 / (per_frame_time.total_seconds() + 0.0001)
                except:
                    time_remaining = ''

            self.timing_ui['timing-label'].setText(
                f'Running: {runtime}\nRemaining: {points_progress}  {time_remaining} EST {pointrate:.1f} PPS'
            )
        else:
            self.timing_ui['timing-label'].setText(
                f'Paused: {format_delta(*timedelta_to_tuple(total_pausetime))}'
            )

    def widget_for_scan_config(self, item, index):
        def remove_this_item(*_):
            self.experiment.scan_deque.remove(item)
            self.update_queue_ui()

        def copy_this_item(*_):
            self.experiment.scan_deque.insert(index, copy(item))
            self.update_queue_ui()

        def move_item_up(*_):
            if index > 0:
                self.experiment.scan_deque.remove(item)
                self.experiment.scan_deque.insert(index - 1, item)

            self.update_queue_ui()

        def move_item_down(*_):
            if index + 1 < len(self.experiment.scan_deque):
                self.experiment.scan_deque.remove(item)
                self.experiment.scan_deque.insert(index + 1, item)

            self.update_queue_ui()

        remove_button = button('Remove')
        remove_button.subject.subscribe(remove_this_item)
        copy_button = button('Copy')
        copy_button.subject.subscribe(copy_this_item)
        up_button = button('↑')
        up_button.subject.subscribe(move_item_up)
        down_button = button('↓')
        down_button.subject.subscribe(move_item_down)

        rest = None
        try:
            fields = dataclasses.asdict(item)
            if len(fields) < 3:
                rest = vertical(*[label(f'{f}: {str(getattr(item, f))}') for f, v in fields.items()])
            else:
                split = len(fields) // 2
                rest = horizontal(
                    vertical(*[label(f'{f}: {str(getattr(item, f))}') for f, _ in list(fields.items())[:split]]),
                    vertical(*[label(f'{f}: {str(getattr(item, f))}') for f, _ in list(fields.items())[split:]]),
                )
        except TypeError:
            rest = label(str(item))

        return horizontal(
            group(
                label(type(item).__name__),
                rest,
                label=f'Queue Item {index + 1}',
            ),
            vertical(
                remove_button,
                copy_button,
            ),
            vertical(
                up_button,
                down_button,
            )
        )

    def update_queue_ui(self):
        queue_main_widget = self.queue_ui['queue-layout']

        # for now clear and rerender since this operation isn't performed often
        for i in reversed(range(queue_main_widget.layout().count())):
            queue_main_widget.layout().itemAt(i).widget().setParent(None)

        for i, config in enumerate(self.experiment.scan_deque):
            queue_main_widget.layout().addWidget(
                self.widget_for_scan_config(config, i))

    def soft_update(self):
        """
        Here, we update the UI tree so it includes the newly
        published data. This amounts to traversing the UI, taking the newly
        published data, and calling the pyqtgraph `.set_data` function as appropriate.
        """
        self.frame_times.append(datetime.datetime.now())
        self.update_timing_ui()

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

    def layout_queue_content(self):
        self.queue_ui = {}

        with CollectUI(self.queue_ui):
            queue_page = splitter(
                vertical(
                    button('Clear Queue', id='clear-queue'),
                ),
                vertical(
                    id='queue-layout',
                ),
                direction=splitter.Horizontal,
                size=[self.LEFT_PANEL_SIZE, self.SIZE[0] - self.LEFT_PANEL_SIZE],
            )

        self.queue_ui['clear-queue'].subject.subscribe(self.clear_queue)
        return queue_page

    def layout_timing_group(self):
        self.timing_ui = {}

        with CollectUI(self.timing_ui):
            timing_group = group(
                label('N Points: {}'.format(0), id='timing-label'),
                label='Timing',
            )

        return timing_group

    def layout(self):
        experiment = self.experiment
        self.experiment.ui = self
        scan_methods = experiment.scan_methods

        ui = {}
        with CollectUI(ui):
            vertical(
                horizontal(
                    button('Start', id='start'),
                    button('Add to Q', id='enqueue'),
                    button('Pause', id='pause'),
                    button('Stop', id='stop'),
                    label('Waiting...', id='status-box'),
                    self.layout_timing_group(),
                    min_height=120,
                ),
                tabs(*[
                    ['Scan', splitter(
                        vertical(
                            horizontal(
                                'Use',
                                combo_box([s.__name__ for s in scan_methods], id='selected_scan_method'),
                            ),
                            tabs(
                                ['Scans', tabs(
                                    *self.layout_scan_methods(scan_methods)
                                )],
                                *self.extra_panels,
                            ),
                        ),
                        vertical(
                            '[Data Streams]',
                            id='dynamic-layout',
                        ),
                        direction=splitter.Horizontal,
                        size=[self.LEFT_PANEL_SIZE, self.SIZE[0] - self.LEFT_PANEL_SIZE]
                    )],
                    ['Queue', self.layout_queue_content()],
                ]),
                widget=self,
            )

        for scan_method in scan_methods:
            name = scan_method.__name__
            bind_dataclass(experiment.scan_configurations[name], prefix=name + '.', ui=ui)

        ui['start'].subject.subscribe(self.start)
        ui['enqueue'].subject.subscribe(self.add_to_queue)
        ui['stop'].subject.subscribe(self.stop)
        ui['pause'].subject.subscribe(self.pause)

        ui['selected_scan_method'].subject.on_next(experiment.use_method)
        ui['selected_scan_method'].subject.subscribe(self.set_scan_method)

        self.ui = ui
        self.dynamic_state_mounted = False

    def add_to_queue(self, *_):
        self.experiment.enqueue()
        self.update_queue_ui()

    def clear_queue(self, *_):
        self.experiment.scan_deque.clear()
        self.update_queue_ui()

    def update_n_points(self):
        print('update n_points')

    def set_scan_method(self, scan_method):
        self.experiment.use_method = scan_method

    def start(self, *_):
        self.experiment.messages.put_nowait('start')

    def stop(self, *_):
        self.experiment.messages.put_nowait('stop')

    def pause(self, *_):
        self.experiment.messages.put_nowait('pause')
