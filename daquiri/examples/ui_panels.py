"""
A simple, reactive two panel (window) application.
"""
from daquiri import Daquiri, Panel
from daquiri.ui import CollectUI, vertical, button, text_edit, radio_button, line_edit, submit

class Monitor(Panel):
    DEFAULT_OPEN = True
    TITLE = 'Monitor'

    def layout(self):
        ui = {}
        with CollectUI(ui):
            vertical(
                'Some reactive (RxPy) inputs.',
                radio_button('Radio button', id='radio'),
                line_edit('Editable line', id='edit'),
                button('Submit', id='submit'),
                widget=self,
            )

        ui['radio'].subject.subscribe(print) # -> All changes to the radio button
        ui['edit'].subject.subscribe(print) # -> All text changes

        # -> Current value {'edit': str, 'radio': bool} whenever the submit
        # button is pressed
        submit('submit',['radio', 'edit'], ui).subscribe(print)

class Log(Panel):
    DEFAULT_OPEN = True
    TITLE = 'Logs'

    def layout(self):
        vertical(
            'Some logging information',
            text_edit('Initial log text.'),
            widget=self,
        )

app = Daquiri(__name__, {
    'Monitor': Monitor,
    'Log': Log,
})

if __name__ == '__main__':
    app.start()
