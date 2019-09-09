import json

from zhivago.ui import grid, tabs, vertical, group, horizontal, label, line_edit, button
from zhivago.panel import Panel

class UIEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)

class BasicInstrumentPanel(Panel):
    SIZE = (600, 300)

    def __init__(self, parent, id, app, instrument_description, instrument_actor):
        self.description = instrument_description
        self.actor = instrument_actor

        super().__init__(parent, id, app)

    def tab_for_single_axis(self, description):
        return vertical(
            group(
                'Driver',
                horizontal('Read', label('Last Value')),
                horizontal('Write', line_edit(''), button('Set')),
                horizontal('Status: ', label('IDLE')),
            ),
            *[x + ',' for x in json.dumps(description, cls=UIEncoder).split(',')],
        )

    def tab_for_axis_group(self, key):
        description = self.description['axis_root'][key]
        if isinstance(description, list):
            return tabs(
                *[[str(i), self.tab_for_single_axis(d)] for i, d in enumerate(description)]
            )

        return self.tab_for_single_axis(description)

    def layout(self):
        grid(
            tabs(
                *[[k, self.tab_for_axis_group(k)] for k in self.description['axis_root']],
                ['General', grid('Readout', *[x + ',' for x in json.dumps(self.description['properties'], cls=UIEncoder).split(',')])],
                ['Settings', grid('Settings')],
                ['Connection', grid('Connection')],
                ['Statistics', grid('Statistics')],
                ['Terminal', grid('Terminal')],
            ),
            widget=self,
        )