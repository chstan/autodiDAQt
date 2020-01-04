import asyncio
import functools
import datetime
import inspect
import json
import pyqtgraph as pg
import pandas as pd

from typing import List, Union, Any, Dict

from loguru import logger

from daquiri.instrument.axis import ProxiedAxis, LogicalAxis, TestAxis, Axis, LogicalSubaxis
from daquiri.instrument.method import Method, TestMethod
from daquiri.instrument.property import ChoiceProperty
from daquiri.utils import safe_lookup
from daquiri.ui import grid, tabs, vertical, group, horizontal, label, line_edit, button, CollectUI, submit, \
    layout_dataclass, bind_dataclass, combo_box, layout_function_call, bind_function_call
from daquiri.panel import Panel


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [datetime.datetime.fromtimestamp(value) for value in values]


class MethodView:
    method: Method

    def __init__(self, method):
        self.method = method

    def layout(self):
        ui = {}

        with CollectUI(ui):
            layout = group(
                self.method.name,
                layout_function_call(self.method.signature)
            )

        bind_function_call(self.method.call, '', ui,
                           self.method.signature, values=self.method.last_kwargs)
        return layout


class ChoicePropertyView:
    prop: ChoiceProperty

    def __init__(self, prop):
        self.prop = prop

    def layout(self):
        ui = {}

        inverse_mapping = dict(zip(self.prop.labels.values(), self.prop.choices.values()))
        inverse_values = dict(zip(self.prop.choices.values(), self.prop.choices.keys()))

        with CollectUI(ui):
            layout = group(self.prop.name, combo_box(self.prop.labels.values(), id='combo'))

        def on_change(value):
            self.prop.set(inverse_mapping[value])

        try:
            ui['combo'].subject.on_next(inverse_values[self.prop.value])
        except:
            pass

        ui['combo'].subject.subscribe(on_change)
        return layout


class AxisView:
    axis: Axis

    def __init__(self, axis, path_to_axis: List[Union[str, int]]):
        self.axis = axis
        self.path_to_axis = path_to_axis
        self.id = '.'.join(map(str, path_to_axis))

    @property
    def joggable(self):
        return self.axis.schema in (float,)

    @property
    def live_plottable(self):
        return self.axis.schema in (float, int,)

    def attach(self, ui):
        raise NotImplementedError()

    def layout(self):
        raise NotImplementedError()


class ProxiedAxisView(AxisView):
    def __init__(self, axis, path_to_axis):
        super().__init__(axis, path_to_axis)

        self.raw_jog_speed = None
        self.live_plot = None

    def move(self, raw_value):
        try:
            value = self.axis.schema(raw_value)
        except ValueError:
            return

        async def perform_move():
            await self.axis.write(value)

        asyncio.get_event_loop().create_task(perform_move())

    def jog(self, rel_speed=1):
        try:
            speed = float(self.raw_jog_speed)
            amount = rel_speed * speed

            async def perform_jog():
                current_value = await self.axis.read()
                await self.axis.write(current_value + amount)

            asyncio.get_event_loop().create_task(perform_jog())

        except ValueError:
            logger.error(f'Cannot jog with speed {self.raw_jog_speed}')

    def update_plot(self, value: pd.DataFrame):
        self.live_plot.setData(value['time'], value['value'])

    def attach(self, ui):
        if self.live_plot:
            self.axis.collected_value_stream.subscribe(self.update_plot)

        if self.axis.raw_value_stream:
            label_widget = ui[f'{self.id}-last_value']
            self.axis.raw_value_stream.subscribe(lambda v: label_widget.setText(str(v['value'])))

        if self.joggable:
            neg_fast, neg_slow, pos_slow, pos_fast, jog_speed = [
                ui[f'{self.id}-jog_{k}'] for k in ['neg_fast', 'neg_slow', 'pos_slow', 'pos_fast', 'speed']]

            def set_speed(v):
                self.raw_jog_speed = v
            jog_speed.subject.subscribe(set_speed)

            for axis, relative_speed in zip([neg_fast, neg_slow, pos_slow, pos_fast], [-5, -1, 1, 5]):
                def close_over_jog_info(rel_speed):
                    def jog(_):
                        self.jog(rel_speed=rel_speed)
                    return jog

                axis.subject.subscribe(close_over_jog_info(relative_speed))

        sub_value = submit(f'{self.id}-set', [f'{self.id}-edit'], ui)
        sub_value.subscribe(lambda v: self.move(list(v.values())[0]))

    def layout(self):
        jog_controls = []
        live_plots = []
        if self.live_plottable:
            widget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
            self.live_plot = widget.plot()
            widget.setTitle(self.id)

            live_plots = [widget]

        if self.joggable:
            jog_controls = [
                horizontal('Jog',
                           button('<<-', id=f'{self.id}-jog_neg_fast'), button('<-', id=f'{self.id}-jog_neg_slow'),
                           button('->', id=f'{self.id}-jog_pos_slow'), button('->>', id=f'{self.id}-jog_pos_fast')),
                horizontal('Slow Jog Amt. (Fast = 5x)', line_edit('0', id=f'{self.id}-jog_speed')),
            ]

        return vertical(
            group(
                'Driver',
                horizontal('Read', label('Last Value', id=f'{self.id}-last_value')),
                horizontal('Write', line_edit('', id=f'{self.id}-edit'), button('Set', id=f'{self.id}-set')),
                *jog_controls,
                *live_plots,
            ),
        )


class LogicalAxisView(AxisView):
    axis: LogicalAxis
    sub_axes: List[LogicalSubaxis] = None
    sub_views: List[AxisView] = None

    def attach(self, ui):
        for view in self.sub_views:
            view.attach(ui)

    def layout(self):
        self.sub_axes = [getattr(self.axis, n) for n in self.axis.logical_coordinate_names]
        self.sub_views = [ProxiedAxisView(axis, self.path_to_axis + [n])
                          for axis, n in zip(self.sub_axes, self.axis.logical_coordinate_names)]

        state_panel = []
        if self.axis.internal_state_cls is not None:
            state_panel = [['State', self.layout_state_panel()],]

        return tabs(
            *[[n, sub_view.layout()] for sub_view, n in zip(self.sub_views, self.axis.logical_coordinate_names)],
            *state_panel
        )

    def layout_state_panel(self):
        ui = {}
        with CollectUI(ui):
            layout = group(
                self.axis.internal_state_cls.__name__,
                layout_dataclass(self.axis.internal_state_cls, prefix='state')
            )

        bind_dataclass(self.axis.internal_state, prefix='state.', ui=ui)
        return layout


class TestAxisView(ProxiedAxisView):
    pass


class UIEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)


class BasicInstrumentPanel(Panel):
    SIZE = (600, 300)
    DEFAULT_OPEN = True

    def __init__(self, parent, id, app, instrument_description, instrument_actor):
        """
        Args:
            parent:
            id: The key identifying the window but also the associated Actor for the instrument as managed by DAQuiri
            app:
            instrument_description:
            instrument_actor:
        """
        self.description = instrument_description
        self.actor = instrument_actor
        self.id_to_path = {}
        self.TITLE = f'{id} (Instrument)'

        self.axis_views = []
        self.property_views = []
        self.method_views = []

        self.ui = {}

        super().__init__(parent, id, app)


    def retrieve(self, path: List[Union[str, int]]):
        instrument = self.app.managed_instruments[self.id]
        return functools.reduce(safe_lookup, path, instrument)

    def write_to_instrument(self):
        pass

    def layout_for_single_axis(self, description: Union[ProxiedAxis, LogicalAxis, TestAxis], path_to_axis):
        view_cls = {
            ProxiedAxis: ProxiedAxisView,
            LogicalAxis: LogicalAxisView,
            TestAxis: TestAxisView,
        }.get(type(description))

        view = view_cls(description, path_to_axis)
        self.axis_views.append(view)
        return view.layout()

    def tab_for_axis_group(self, key):
        description = self.description['axes'][key]
        if isinstance(description, list):
            return tabs(
                *[[str(i), self.layout_for_single_axis(d, path_to_axis=[key, i])] for i, d in enumerate(description)]
            )

        return self.layout_for_single_axis(description, path_to_axis=[key])

    def render_property(self, key):
        ins_property = self.description['properties'][key]
        view_cls = {
            ChoiceProperty: ChoicePropertyView,
        }.get(type(ins_property))

        view = view_cls(ins_property)
        self.property_views.append(view)
        return view.layout()

    def render_method(self, key):
        method = self.description['methods'][key]
        view_cls = {
            Method: MethodView,
            TestMethod: MethodView,
        }.get(type(method))

        view = view_cls(method)
        self.method_views.append(view)
        return view.layout()

    def layout(self):
        with CollectUI(self.ui):
            grid(
                tabs(
                    *[[k, self.tab_for_axis_group(k)] for k in self.description['axes']],
                    ['Settings', grid(
                        'Settings',
                        *[self.render_property(k) for k in self.description['properties']],
                    )],
                    ['Methods', grid(
                        'Methods',
                        *[self.render_method(k) for k in self.description['methods']],
                    )],
                    #['Connection', grid('Connection')],
                    #['Statistics', grid('Statistics')],
                    #['Terminal', grid('Terminal')],
                ),
                widget=self)

        for axis_view in self.axis_views:
            axis_view.attach(self.ui)
