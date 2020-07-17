from dataclasses import dataclass, field
from daquiri.panel import open_appless_panel, Panel
from daquiri.ui import vertical, label, layout_dataclass, RenderAs, tabs, horizontal, CollectUI, bind_dataclass, button


@dataclass
class TestDataclass:
    _field_annotations = {
        'start': {'range': (-10., 10.,),},
        'end': {'range': (-10., 10.,),
                'render_as': RenderAs.INPUT},
        'n_points': {'range': (1, 1e5)},
        'comment': {'render_as': RenderAs.TEXTAREA, },
    }

    n_points: int = 1
    start: float = 0.
    end: float = 5.

    name: str = ''
    comment: str = ''


class TestPanel(Panel):
    SIZE = (1200, 900)
    a = TestDataclass()
    b = TestDataclass()

    def echo(self, *_):
        print(self.a)
        print(self.b)

    def layout(self):
        ui = {}
        with CollectUI(ui):
            vertical(
                label('Test'),
                horizontal(
                    layout_dataclass(TestDataclass, prefix='a'),
                    layout_dataclass(TestDataclass, prefix='b', submit='Submit'),
                ),
                tabs(
                    ['A', label('A')],
                    ['B', label('B')],
                ),
                button('Echo', id='echo'),
                widget=self,
            )

        bind_dataclass(self.a, 'a', ui)
        bind_dataclass(self.b, 'b', ui)

        ui['echo'].subscribe(self.echo)


def main():
    open_appless_panel(TestPanel)