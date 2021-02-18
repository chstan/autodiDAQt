from daquiri.core import DaquiriMainWindow
import pytest

from daquiri.panels import InstrumentManager

from .conftest import MockDaquiri
from daquiri.state import AppState


def test_daquiri_state_loading(app: MockDaquiri):
    state = app.collect_state()

    state.daquiri_state = AppState(user="a", session_name="b", profile="c")

    app.receive_state(state)

    assert app.user.user == "a"
    assert app.user.session_name == "b"


def test_daquiri_main_window_opens(qtbot, app: MockDaquiri):
    app.init_with(panels={"_instrument_manager": InstrumentManager})
    main_window = DaquiriMainWindow(loop=None, app=app)
    main_window.show()
    qtbot.add_widget(main_window)

    assert set(main_window.open_panels.keys()) == {"_instrument_manager"}
