import enum
import inspect
from dataclasses import dataclass

import pytest
from PyQt5 import QtCore
from pytestqt.qtbot import QtBot

from autodidaqt.ui import *
from autodidaqt.widgets import ComboBox, DoubleSpinBox, LineEdit, SpinBox


def test_ui_collection(qtbot: QtBot):
    ui = {}
    with CollectUI(ui):
        splitter(
            button("Button", id="b1"),
            label("Label", id="l1"),
        )

    assert set(ui.keys()) == {"b1", "l1"}


def test_nested_ui_collection(qtbot: QtBot):
    ui_parent = {}
    ui_child = {}

    with CollectUI(ui_parent):
        # build an internal layout
        b = button("Button", id="bp")

        with CollectUI(ui_child):
            child_layout = scroll_area(
                sized_grid(
                    {
                        (0, 0): button("Button-Child", id="bc"),
                        (1, 0): label("Child label"),
                    }
                )
            )

        horizontal(
            b,
            child_layout,
            button("Another parent button", id="bp2"),
        )

    assert set(ui_parent.keys()) == {"bp", "bp2"}
    assert set(ui_child.keys()) == {"bc"}


def test_reactive_button(qtbot: QtBot):
    b = button("My Button Text")
    events = []
    b.subscribe(events.append)

    qtbot.add_widget(b)
    qtbot.mouseClick(b, QtCore.Qt.LeftButton)
    qtbot.mouseClick(b, QtCore.Qt.LeftButton)
    assert events == [True, True]

    qtbot.mouseClick(b, QtCore.Qt.LeftButton)
    assert events == [True, True, True]


def test_reactive_check_box(qtbot: QtBot):
    cb = check_box("Checkbox")

    events = []
    cb.subscribe(events.append)

    qtbot.add_widget(cb)
    cb.setCheckState(False)
    cb.setCheckState(False)
    cb.setCheckState(True)
    cb.setCheckState(False)
    cb.setCheckState(True)
    cb.setCheckState(True)

    assert events == [0, 1, 0, 1]


def test_reactive_combo_box(qtbot: QtBot):
    combo = combo_box(["A", "B", "C"])
    qtbot.add_widget(combo)

    events = []
    combo.subscribe(events.append)

    combo.setCurrentIndex(0)
    combo.setCurrentIndex(1)
    combo.setCurrentIndex(2)
    combo.setCurrentIndex(2)
    combo.setCurrentIndex(0)

    assert events == ["A", "B", "C", "A"]


def test_reactive_line_edit(qtbot: QtBot):
    start_text = "Start."
    edit = line_edit(start_text)
    qtbot.add_widget(edit)

    events = []
    edit.subscribe(events.append)

    will_type = "Test."
    qtbot.keyClicks(edit, will_type)

    assert events == [start_text + will_type[:i] for i in range(len(will_type) + 1)]


def test_reactive_slider(qtbot: QtBot):
    w = slider()
    qtbot.add_widget(w)

    events = []
    w.subscribe(events.append)

    w.setValue(5)
    w.setValue(-1)  # below minimum
    w.setValue(11)  # above maximum
    w.setValue(6.6)  # should be coerced to int and rounded down

    assert events == [0, 5, 0, 10, 6]


def test_reactive_spinbox(qtbot: QtBot):
    sb = spin_box()
    qtbot.add_widget(sb)

    # by default we get an integer spinbox
    events = []
    sb.subscribe(events.append)

    for v in [-1, 3, 3.5, 4, 9, 12]:
        sb.setValue(v)

    assert events == [0, 3, 4, 9, 10]

    # check floats
    dsb = spin_box(kind=float)
    qtbot.add_widget(dsb)
    events = []
    dsb.subscribe(events.append)

    for v in [-1, 3, 3.5, 4, 9, 12]:
        dsb.setValue(v)

    assert events == [0, 3, 3.5, 4, 9, 10]


def test_group_label_assignment(qtbot):
    label_text = "This is actually the label"
    g = group(label_text, button("A button"))

    qtbot.add_widget(g)
    assert g.title() == label_text

    g2 = group(button("Another button"), label=label_text)
    qtbot.add_widget(g2)
    assert g2.title() == label_text


def test_submit_gating(qtbot: QtBot):
    ui = {}
    with CollectUI(ui):
        top_level = vertical(
            "Some reactive inputs",
            radio_button("Radio button", id="radio"),
            line_edit("!", id="edit"),
            button("Submit", id="submit"),
        )

    qtbot.add_widget(top_level)

    edit_events = []
    radio_events = []
    ui["radio"].subscribe(radio_events.append)
    ui["edit"].subscribe(edit_events.append)

    # collect into a small form
    form_events = []
    submit("submit", ["radio", "edit"], ui=ui).subscribe(form_events.append)

    ui["radio"].setChecked(True)
    ui["radio"].setChecked(True)
    ui["radio"].setChecked(False)
    qtbot.keyClicks(ui["edit"], "Text")

    qtbot.mouseClick(ui["submit"], QtCore.Qt.LeftButton)

    ui["radio"].setChecked(True)
    qtbot.keyClicks(ui["edit"], "B")

    qtbot.mouseClick(ui["submit"], QtCore.Qt.LeftButton)

    assert edit_events == [f"!{'TextB'[:i]}" for i in range(len("TextB") + 1)]
    assert radio_events == [False, True, False, True]

    assert form_events == [
        {"edit": "!Text", "radio": False},
        {"edit": "!TextB", "radio": True},
    ]


class AorB(str, enum.Enum):
    A = "A"
    B = "B"


@dataclass
class Data:
    x: float = 0.5
    y: int = 5
    z: str = "abc"
    choice: AorB = AorB.A


def test_dataclass_bindings(qtbot: QtBot):
    data = Data()
    gated = Data()
    ui = {}

    with CollectUI(ui):
        g = group(
            "Dataclass Binding",
            layout_dataclass(Data, prefix="data"),
            layout_dataclass(Data, prefix="gated", submit="Submit"),
        )

        bind_dataclass(data, prefix="data", ui=ui)
        bind_dataclass(gated, prefix="gated", ui=ui)

    qtbot.add_widget(g)

    # check keys are generated appropriately
    assert set(ui.keys()).issuperset({("data", k) for k in ["x", "y", "z", "choice"]})

    # this only gives one way binding
    assert data == Data()

    # directly plug into the observables
    ui[("data", "x")].on_next(5)
    assert data == Data(x=5)

    ui[("data", "choice")].on_next(AorB.B)
    assert data == Data(x=5, choice=AorB.B)

    # check that the gated option does not update until submitted
    ui[("gated", "x")].on_next(5)
    assert gated == Data()

    ui[("gated", "y")].on_next(-1)
    assert gated == Data()

    qtbot.mouseClick(ui[("gated", "submit!")], QtCore.Qt.LeftButton)
    assert gated == Data(x=5, y=-1)

    # check field types
    with pytest.raises(TypeError) as exc:
        ui[("data", "z")].on_next(10)

    assert "unexpected type 'int'" in str(exc.value)

    expected_classes = [
        DoubleSpinBox,
        SpinBox,
        LineEdit,
        ComboBox,
    ]

    for partial_id, cls in zip(["x", "y", "z", "choice"], expected_classes):
        assert isinstance(ui[("data", partial_id)], cls)


def test_update_ui_from_dataclass_instance(qtbot):
    data = Data()
    ui = {}

    with CollectUI(ui):
        w = layout_dataclass(Data, prefix="data")
        bind_dataclass(data, prefix="data", ui=ui)

    qtbot.add_widget(w)
    assert data == Data()

    other = Data(x=-1, y=4, z="hello")
    update_dataclass(other, "data", ui=ui)

    assert data == other


def test_class_name_assignment(qtbot):
    """
    CSS in Qt is pretty much garbage because, for one, it isn't
    actually CSS. There's also not much we can actually test here,
    but we can verify it doesn't explode.
    """
    b = button("Test", class_name="my-button")
    qtbot.add_widget(b)

    assert True


def test_numeric_input(qtbot):
    float_input = numeric_input(0, input_type=float)
    int_input = numeric_input(0, input_type=int)

    qtbot.add_widget(float_input)
    qtbot.add_widget(int_input)

    float_events, int_events, follower_events = [], [], []
    float_input.subscribe(float_events.append)
    int_input.subscribe(int_events.append)

    float_input.setText("5.5")
    float_input.setText("5.5")
    float_input.setText("-1")
    assert float_events == ["0", "5.5", "-1"]

    int_input.setText("2")
    int_input.setText("8")
    int_input.setText("8")
    int_input.setText("382")
    assert int_events == ["0", "2", "8", "382"]


def test_bind_function_call(qtbot, mocker):
    def adds_two_numbers(x: int, y: int) -> int:
        return x + y

    signature = inspect.signature(adds_two_numbers)
    ui = {}
    prefix = ""

    with CollectUI(ui):
        l = layout_function_call(signature, prefix=prefix)

    qtbot.add_widget(l)

    stub = mocker.stub("adds_two_numbers")
    bind_function_call(stub, prefix=prefix, ui=ui, signature=signature)

    # sanity check
    assert set(ui.keys()) == {(prefix, "x"), (prefix, "y"), (prefix, "submit")}

    qtbot.mouseClick(ui[(prefix, "submit")], QtCore.Qt.LeftButton)
    stub.assert_called_once_with(x=0, y=0)

    stub.reset_mock()
    ui[(prefix, "x")].setText("1")
    ui[(prefix, "y")].setText("2")
    qtbot.mouseClick(ui[(prefix, "submit")], QtCore.Qt.LeftButton)
    stub.assert_called_once_with(x=1, y=2)
