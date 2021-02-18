from dataclasses import dataclass
from enum import Enum

from daquiri import Daquiri, Panel
from daquiri.ui import CollectUI, bind_dataclass, layout_dataclass, vertical


class AOrB(Enum):
    A = 0
    B = 1


@dataclass
class CompositeType:
    a: float = 0.0
    b: int = 5
    s: str = "Some text"
    choice: AOrB = AOrB.A


class Custom(Panel):
    TITLE = "Dataclass Example"
    DEFAULT_OPEN = True

    def layout(self):
        self.value = CompositeType()
        ui = {}
        with CollectUI(ui):
            vertical(layout_dataclass(CompositeType, prefix="value"), widget=self)

        bind_dataclass(self.value, prefix="value", ui=ui)


app = Daquiri(__name__, dict(Custom=Custom))

if __name__ == "__main__":
    app.start()
