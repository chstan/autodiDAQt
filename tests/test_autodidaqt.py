import pytest

from autodidaqt.core import AutodiDAQtMainWindow
from autodidaqt.panels import InstrumentManager
from autodidaqt.state import AppState

from .conftest import Mockautodidaqt


def test_autodidaqt_state_loading(app: Mockautodidaqt):
    state = app.collect_state()

    state.autodidaqt_state = AppState(user="a", session_name="b", profile="c")

    app.receive_state(state)

    assert app.user.user == "a"
    assert app.user.session_name == "b"


def test_autodidaqt_main_window_opens(qtbot, app: Mockautodidaqt):
    app.init_with(panels={"_instrument_manager": InstrumentManager})
    main_window = AutodiDAQtMainWindow(loop=None, app=app)
    main_window.show()
    qtbot.add_widget(main_window)

    assert set(main_window.open_panels.keys()) == {"_instrument_manager"}
