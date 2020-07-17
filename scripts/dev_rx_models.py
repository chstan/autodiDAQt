from daquiri.panel import open_appless_panel, Panel
from daquiri.reactive_utils import Transaction, RxListPattern
from daquiri.ui import vertical, label, horizontal, CollectUI, list_view, scroll_area, text_edit, button, submit
import rx.operators as ops


class TestPanel(Panel):
    SIZE = (1200, 800)

    def layout(self):
        ui = {}

        with CollectUI(ui):
            vertical(
                label('Test'),
                scroll_area(list_view(id='items')),
                text_edit(id='edit'),
                button('Submit', id='submit'),
                widget=self,
            )

        add_note = submit('submit', ['edit'], ui).pipe(
            ops.map(lambda n: n['edit'])
        )
        tx_add = add_note.pipe(ops.map(lambda v: Transaction.add(new_value=v)))
        notes_pattern = RxListPattern(add=tx_add)
        notes_pattern.values_with_history.subscribe(print)
        model = notes_pattern.bind_to_model()
        model.bind_to_ui(ui['items'])


def main():
    open_appless_panel(TestPanel)