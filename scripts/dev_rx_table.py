import pyrsistent as pr
import rx.operators as ops

from autodidaqt.panel import Panel, open_appless_panel
from autodidaqt.reactive_utils import RxTablePattern, Transaction
from autodidaqt.ui import CollectUI, button, label, table_view, vertical


class TestPanel(Panel):
    SIZE = (1200, 800)

    def layout(self):
        ui = {}

        with CollectUI(ui):
            vertical(
                label("Test"),
                table_view(id="table"),
                button("Add Row", id="submit"),
                widget=self,
            )

        tx_add = ui["submit"].subject.pipe(
            ops.map(lambda x: Transaction.add(new_value=pr.v(1, 2, 3)))
        )
        table_pattern = RxTablePattern(columns=["A", "B", "C"], add_row=tx_add)
        table_pattern.values_with_history.subscribe(print)
        model = table_pattern.bind_to_model()
        model.bind_to_ui(ui["table"])


def main():
    open_appless_panel(TestPanel)
