from daquiri.panel import open_appless_panel, Panel
from daquiri.reactive_utils import Transaction, RxTablePattern
from daquiri.ui import vertical, label, CollectUI, button, table_view
import rx.operators as ops
import pyrsistent as pr


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
