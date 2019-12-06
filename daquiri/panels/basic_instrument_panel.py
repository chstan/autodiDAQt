import asyncio
import functools
import datetime
import json
import numpy as np
import pyqtgraph as pg
import pandas as pd

from typing import List, Union

from loguru import logger

from daquiri.instrument.property import AxisSpecification
from daquiri.utils import safe_lookup
from daquiri.ui import grid, tabs, vertical, group, horizontal, label, line_edit, button, CollectUI, submit
from daquiri.panel import Panel


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [datetime.datetime.fromtimestamp(value) for value in values]


class AxisSpecificationView:
    def __init__(self, spec: AxisSpecification, path_to_axis: List[Union[str, int]]):
        self.spec = spec
        self.path_to_axis = path_to_axis
        self.id = '.'.join(map(str, path_to_axis))
        self.raw_jog_speed = None
        self.live_plot = None

    @property
    def joggable(self):
        return self.spec.schema in (float,)

    @property
    def live_plottable(self):
        return self.spec.schema in (float, int,)

    def move(self, owner, raw_value):
        try:
            value = self.spec.schema(raw_value)
        except ValueError:
            return

        true_axis = owner.retrieve(self.path_to_axis)

        async def perform_move():
            await true_axis.write(value)

        asyncio.get_event_loop().create_task(perform_move())

    def jog(self, owner, rel_speed=1):
        try:
            speed = float(self.raw_jog_speed)
            amount = rel_speed * speed

            true_axis = owner.retrieve(self.path_to_axis)

            async def perform_jog():
                current_value = await true_axis.read()
                await true_axis.write(current_value + amount)

            asyncio.get_event_loop().create_task(perform_jog())

        except ValueError:
            logger.error(f'Cannot jog with speed {self.raw_jog_speed}')

    def update_plot(self, value: pd.DataFrame):
        self.live_plot.setData(value['time'], value['value'])

    def attach(self, owner, ui):
        true_axis = owner.retrieve(self.path_to_axis)
        if self.live_plot:
            true_axis.collected_value_stream.subscribe(self.update_plot)

        if true_axis.raw_value_stream:
            label_widget = ui[f'{self.id}-last_value']
            true_axis.raw_value_stream.subscribe(lambda v: label_widget.setText(str(v['value'])))

        if self.joggable:
            neg_fast, neg_slow, pos_slow, pos_fast, jog_speed = [
                ui[f'{self.id}-jog_{k}'] for k in ['neg_fast', 'neg_slow', 'pos_slow', 'pos_fast', 'speed']]

            def set_speed(v):
                self.raw_jog_speed = v
            jog_speed.subject.subscribe(set_speed)

            for axis, relative_speed in zip([neg_fast, neg_slow, pos_slow, pos_fast], [-5, -1, 1, 5]):
                def close_over_jog_info(rel_speed):
                    def jog(_):
                        self.jog(owner=owner, rel_speed=rel_speed)
                    return jog

                axis.subject.subscribe(close_over_jog_info(relative_speed))

        sub_value = submit(f'{self.id}-set', [f'{self.id}-edit'], ui)
        sub_value.subscribe(lambda v: self.move(owner, list(v.values())[0]))

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


class UIEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)


class BasicInstrumentPanel(Panel):
    SIZE = (600, 300)

    def __init__(self, parent, id, app, instrument_description, instrument_actor):
        """
        :param parent:
        :param id: The key identifying the window but also the associated Actor for the instrument as managed by DAQuiri
        :param app:
        :param instrument_description:
        :param instrument_actor:
        """
        self.description = instrument_description
        self.actor = instrument_actor
        self.id_to_path = {}
        self.axis_views = []
        self.ui = {}

        super().__init__(parent, id, app)

    def retrieve(self, path: List[Union[str, int]]):
        instrument = self.app.managed_instruments[self.id]
        return functools.reduce(safe_lookup, path, instrument)

    def write_to_instrument(self):
        pass

    def layout_for_single_axis(self, description: AxisSpecification, path_to_axis):
        view = AxisSpecificationView(description, path_to_axis)
        self.axis_views.append(view)
        return view.layout()

    def tab_for_axis_group(self, key):
        description = self.description['axis_root'][key]
        if isinstance(description, list):
            return tabs(
                *[[str(i), self.layout_for_single_axis(d, path_to_axis=[key, i])] for i, d in enumerate(description)]
            )

        return self.layout_for_single_axis(description, path_to_axis=[key])

    def layout(self):
        with CollectUI(self.ui):
            grid(
                tabs(
                    *[[k, self.tab_for_axis_group(k)] for k in self.description['axis_root']],
                    ['Settings', grid('Settings', *[x + ',' for x in
                                                     json.dumps(self.description['properties'], cls=UIEncoder).split(
                                                         ',')])],
                    ['Functions', grid('Functions', 'Stuff here eventually.')],
                    #['Settings', grid('Settings')],
                    #['Connection', grid('Connection')],
                    #['Statistics', grid('Statistics')],
                    #['Terminal', grid('Terminal')],
                ),
                widget=self)

        for axis_view in self.axis_views:
            axis_view.attach(self, self.ui)
