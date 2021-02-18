"""
Easily composable and reactive UI utilities using RxPy and PyQt5. This makes UI prototyping *MUCH* faster.
In order to log IDs so that you can attach subscriptions after the fact, you will need to use the CollectUI
context manager.

An example is as follows, showing the currently available widgets. If you don't need to attach callbacks,
you can get away without using the context manager.

```
ui = {}
with CollectUI(ui):
    test_widget = grid(
        group(
            text_edit('starting text', id='text'),
            line_edit('starting line', id='line'),
            combo_box(['A', 'B', 'C'], id='combo'),
            spin_box(5, id='spinbox'),
            radio_button('A Radio', id='radio'),
            check_box('Checkbox', id='check'),
            slider(id='slider'),
            file_dialog(id='file'),
            button('Send Text', id='submit')
        ),
        widget=self,
    )
```

"Forms" can effectively be built by building an observable out of the subjects in the UI. We have a `submit`
function that makes creating such an observable simple.

```
submit('submit', ['check', 'slider', 'file'], ui).subscribe(lambda item: print(item))
```

With the line above, whenever the button with id='submit' is pressed, we will log a dictionary with
the most recent values of the inputs {'check','slider','file'} as a dictionary with these keys. This
allows building PyQt5 "forms" without effort.
"""
import enum
import functools
from enum import Enum
from inspect import Parameter, Signature
from typing import Any, Dict, Hashable, List, Optional, Type, Union

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import rx
import rx.operators as ops
from daquiri.ui.lens import Lens
from daquiri.utils import enum_mapping, enum_option_names
from daquiri.widgets import *
from pyqt_led import Led

__all__ = (
    "CollectUI",
    # layouts
    "layout",
    "grid",
    "sized_grid",
    "vertical",
    "horizontal",
    "splitter",
    # widgets
    "group",
    "label",
    "tabs",
    "button",
    "check_box",
    "combo_box",
    "file_dialog",
    "line_edit",
    "radio_button",
    "slider",
    "spin_box",
    "text_edit",
    "led",
    "numeric_input",
    "scroll_area",
    # Observable tools
    "submit",
    # @dataclass utils
    "layout_dataclass",
    "bind_dataclass",
    "update_dataclass",
    # Functions and methods
    "layout_function_call",
    "bind_function_call",
)

ACTIVE_UI_STACK = []
ACTIVE_UI = None


def ui_builder(f):
    @functools.wraps(f)
    def wrapped_ui_builder(*args, id=None, class_name=None, **kwargs):
        global ACTIVE_UI
        if id is not None:
            # we allow passing tuples as an
            # ID because they are hashable and
            # simple to composite.
            if isinstance(id, str):
                ui = ACTIVE_UI
            else:
                if isinstance(id[-1], dict):
                    id, ui = id
                else:
                    ui = ACTIVE_UI

        ui_element = f(*args, **kwargs)

        if id and ui is not None:
            ui[id] = ui_element

        if class_name is not None:
            # CSS equivalent of classes
            ui_element.setProperty("cssClass", class_name)
            ui_element.style().unpolish(ui_element)
            ui_element.style().polish(ui_element)

        return ui_element

    return wrapped_ui_builder


class CollectUI:
    def __init__(self, target_ui=None):
        global ACTIVE_UI, ACTIVE_UI_STACK

        if ACTIVE_UI is not None:
            ACTIVE_UI_STACK.append(ACTIVE_UI)

        self.ui = {} if target_ui is None else target_ui
        ACTIVE_UI = self.ui

    def __enter__(self):
        return self.ui

    def __exit__(self, exc_type, exc_val, exc_tb):
        global ACTIVE_UI, ACTIVE_UI_STACK
        if ACTIVE_UI_STACK:
            ACTIVE_UI = ACTIVE_UI_STACK[-1]
            ACTIVE_UI_STACK = ACTIVE_UI_STACK[:-1]
        else:
            ACTIVE_UI = None


@ui_builder
def scroll_area(single_child):
    scroll = QScrollArea()
    scroll.setWidget(single_child)
    scroll.setWidgetResizable(True)
    return scroll


@ui_builder
def layout(
    *children,
    layout_cls=None,
    widget=None,
    min_width=None,
    min_height=None,
    margin=0,
    content_margin=0,
    spacing=0,
    alignment=None,
):
    if layout_cls is None:
        layout_cls = QGridLayout

    if widget is None:
        widget = QWidget()

    internal_layout = layout_cls()

    if layout_cls not in {QVBoxLayout, QHBoxLayout}:
        internal_layout.setMargin(margin)

    if layout_cls not in {}:
        if isinstance(content_margin, (int, float, str)):
            content_margin = [content_margin] * 4

        internal_layout.setContentsMargins(*content_margin)

    if layout_cls not in {}:
        internal_layout.setSpacing(spacing)

    for child in children:
        internal_layout.addWidget(_wrap_text(child))

    if alignment is not None:
        internal_layout.setAlignment(alignment)

    widget.setLayout(internal_layout)
    if min_width:
        widget.setMinimumWidth(min_width)
    if min_height:
        widget.setMinimumHeight(min_height)

    return widget


grid = functools.partial(layout, layout_cls=QGridLayout)
vertical = functools.partial(layout, layout_cls=QVBoxLayout)
horizontal = functools.partial(layout, layout_cls=QHBoxLayout)
for fn in [grid, vertical, horizontal]:
    functools.update_wrapper(fn, layout)


@ui_builder
def sized_grid(
    children,
    column_stretch=None,
    row_stretch=None,
    margin=0,
    content_margin=0,
    spacing=0,
    widget=None,
):
    if row_stretch:
        n_rows = len(row_stretch)
    else:
        n_rows = max(*[k[0] for k in children.keys()]) + 1
        row_stretch = [1] * n_rows

    if column_stretch:
        n_columns = len(column_stretch)
    else:
        n_columns = max(*[k[1] for k in children.keys()]) + 1
        column_stretch = [1 / n_columns] * n_columns

    layout = QGridLayout()
    layout.setMargin(margin)
    if isinstance(content_margin, (int, float, str)):
        content_margin = [content_margin] * 4

    layout.setContentsMargins(*content_margin)

    for row_i, stretch in enumerate(row_stretch):
        layout.setRowStretch(row_i, stretch)

    for col_i, stretch in enumerate(column_stretch):
        layout.setColumnStretch(col_i, stretch)

    for (row, column), child in children.items():
        layout.addWidget(child, row, column)

    if widget is None:
        widget = QWidget()

    widget.setLayout(layout)
    return widget


@ui_builder
def list_view():
    lv = QListView()
    return lv


@ui_builder
def table_view():
    tv = QTableView()
    return tv


@ui_builder
def splitter(first, second, direction=Qt.Vertical, size=None, handle_width=12):
    split_widget = QSplitter(direction)
    split_widget.setHandleWidth(handle_width)

    split_widget.addWidget(first)
    split_widget.addWidget(second)

    if size is not None:
        split_widget.setSizes(size)

    return split_widget


splitter.Vertical = Qt.Vertical
splitter.Horizontal = Qt.Horizontal


@ui_builder
def group(*args, label=None, layout_cls=None):
    if args:
        if isinstance(args[0], str):
            label = args[0]
            args = args[1:]

    if layout_cls is None:
        layout_cls = QVBoxLayout

    groupbox = QGroupBox(label)

    layout = layout_cls()

    for arg in args:
        layout.addWidget(arg)

    groupbox.setLayout(layout)
    return groupbox


@ui_builder
def label(text, *args):
    return QLabel(text, *args)


@ui_builder
def table(columns):
    table_widget = QTableWidget()


@ui_builder
def tabs(*children, document_mode=True):
    widget = QTabWidget()
    for name, child in children:
        widget.addTab(child, name)

    widget.setDocumentMode(document_mode)

    return widget


@ui_builder
def button(text, horiz_expand=False, *args):
    button = PushButton(text, *args)

    if horiz_expand:
        pass
    else:
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    return button


@ui_builder
def check_box(text, *args, **kwargs):
    return CheckBox(text, *args, **kwargs)


@ui_builder
def combo_box(items: List[str], content_margin=8, *args, **kwargs):
    widget = ComboBox(*args, **kwargs)
    widget.addItems(items)

    if isinstance(content_margin, (int, float, str)):
        content_margin = [content_margin] * 4

    if content_margin is not None:
        widget.setContentsMargins(*content_margin)

    return widget


@ui_builder
def file_dialog(*args, **kwargs):
    return FileDialog(*args, **kwargs)


@ui_builder
def line_edit(value, text_margin=8, *args):
    edit = LineEdit(value, *args)

    if isinstance(text_margin, (int, float, str)):
        text_margin = [text_margin] * 4

    if text_margin is not None:
        edit.setTextMargins(*text_margin)

    return edit


@ui_builder
def radio_button(text, *args, **kwargs):
    return RadioButton(text, *args, **kwargs)


@ui_builder
def slider(minimum=0, maximum=10, interval=None, horizontal=True, **kwargs):
    widget = Slider(orientation=Qt.Horizontal if horizontal else Qt.Vertical, **kwargs)
    widget.setMinimum(minimum)
    widget.setMaximum(maximum)

    if interval:
        widget.setTickInterval(interval)

    return widget


class RenderAs(Enum):
    INPUT = 0
    SPINBOX = 1
    TEXTAREA = 2
    LINE_EDIT = 3


@ui_builder
def spin_box(
    minimum=0,
    maximum=10,
    step=1,
    content_margin=8,
    adaptive=True,
    value=None,
    kind: type = int,
    **kwargs,
):
    if kind == int:
        widget = SpinBox(**kwargs)
    else:
        widget = DoubleSpinBox(**kwargs)

    widget.setRange(minimum, maximum)

    if value is not None:
        widget.subject.on_next(value)

    if adaptive:
        widget.setStepType(SpinBox.AdaptiveDecimalStepType)
    else:
        widget.setSingleStep(step)

    if isinstance(content_margin, (int, float, str)):
        content_margin = [content_margin] * 4

    if content_margin is not None:
        widget.setContentsMargins(*content_margin)

    return widget


@ui_builder
def text_edit(text="", *args, **kwargs):
    return TextEdit(text, *args, **kwargs)


@ui_builder
def led(*args, **kwargs):
    return Led(*args, **kwargs)


@ui_builder
def numeric_input(
    value=0,
    input_type: type = float,
    *args,
    subject=None,
    validator_settings=None,
    **kwargs,
):
    validators = {
        int: QtGui.QIntValidator,
        float: QtGui.QDoubleValidator,
    }
    default_settings = {
        int: {"bottom": -1e6, "top": 1e6},
        float: {"bottom": -1e6, "top": 1e6, "decimals": 3},
    }

    if validator_settings is None:
        validator_settings = default_settings.get(input_type)

    if isinstance(value, (Lens, rx.Observable)):
        subject = value
        value = subject.value

    widget = LineEdit(str(value), *args, subject=subject, process_on_next=str, **kwargs)
    widget.setValidator(validators.get(input_type, QtGui.QIntValidator)(**validator_settings))

    return widget


def _wrap_text(str_or_widget):
    return label(str_or_widget) if isinstance(str_or_widget, str) else str_or_widget


def _unwrap_subject(subject_or_widget):
    try:
        return subject_or_widget.subject
    except AttributeError:
        return subject_or_widget


def submit(gate: Hashable, keys: List[Hashable], ui: Dict[Hashable, QWidget]) -> rx.Observable:
    try:
        gate = ui[gate]
    except (ValueError, TypeError):
        pass

    gate = _unwrap_subject(gate)
    items = [_unwrap_subject(ui[k]) for k in keys]

    combined = items[0].pipe(
        ops.combine_latest(*items[1:]), ops.map(lambda vs: dict(zip(keys, vs)))
    )

    return gate.pipe(
        ops.filter(lambda x: x),
        ops.with_latest_from(combined),
        ops.map(lambda x: x[1]),
    )


def _layout_dataclass_field(
    field, field_name: str, prefix: str, annotation: Dict[str, Any]
) -> QWidget:
    id_for_field = (
        prefix,
        field_name,
    )

    allowable_range = annotation.get("range", (-1e5, 1e5))
    label = annotation.get("label", field_name)
    label_transform = annotation.get("label_transform", lambda x: x.replace("_", " ").title())
    label = label_transform(label)

    if field.type in [
        int,
        float,
    ]:
        render_as = annotation.get("render_as", RenderAs.SPINBOX)
        if render_as == RenderAs.SPINBOX:
            field_input = spin_box(
                value=0,
                kind=field.type,
                id=id_for_field,
                minimum=allowable_range[0],
                maximum=allowable_range[1],
            )
        else:
            field_input = numeric_input(value=0, input_type=field.type, id=id_for_field)

    elif field.type == str:
        render_as = annotation.get("render_as", RenderAs.LINE_EDIT)
        if render_as == RenderAs.LINE_EDIT:
            field_input = line_edit("", id=id_for_field)
        else:
            field_input = text_edit("", id=id_for_field)
    elif issubclass(field.type, enum.Enum):
        enum_options = enum_option_names(field.type)
        field_input = combo_box(enum_options, id=id_for_field)
    elif field.type == bool:
        field_input = check_box(field_name, id=id_for_field)
    else:
        raise Exception("Could not render field: {}".format(field))

    return group(label, field_input)


def _layout_function_parameter(parameter: Parameter, prefix: str):
    parameter_type = parameter.annotation
    widget_cls = {
        float: lambda id: numeric_input(0, float, id=id),
        int: lambda id: numeric_input(0, int, id=id),
        str: lambda id: line_edit("", id=id),
    }[parameter_type]

    return group(
        f"{parameter.name} : {parameter_type.__name__}",
        widget_cls(id=(prefix, parameter.name)),
    )


def layout_function_call(signature: Signature, prefix: Optional[str] = None):
    """
    Renders fields and a call button for a Python method. This allows "RPC" from the UI to
    driver methods or other functions.

    Args:
        signature (Signature): The call signature for the function we are rendering UI for.
        prefix (:obj:`str`, optional): UI ID prefix

    Returns:
        Rendered Qt widgets, without any callbacks/subscriptions in place.
    """
    if prefix is None:
        prefix = ""

    return vertical(
        *[
            _layout_function_parameter(parameter, prefix)
            for parameter in signature.parameters.values()
        ],
        button("Call", id=(prefix, "submit")),
    )


def bind_function_call(
    function,
    prefix: str,
    ui: Dict[str, QWidget],
    signature: Signature = None,
    values: Dict[Any, Any] = None,
):
    def translate(kind: Union[Parameter, Type]):
        if isinstance(kind, Parameter):
            if not kind.annotation == kind.empty:
                kind = kind.annotation
            else:
                kind = type(kind.default)

        return {
            int: (lambda x: str(x), lambda x: int(x)),
            float: (lambda x: str(x), lambda x: float(x)),
        }.get(kind, (lambda x: x, lambda x: x))

    if values is None:
        values = {}

    translations = {k: translate(signature.parameters[k]) for k in signature.parameters.keys()}

    for k, v in values.items():
        ui[
            (
                prefix,
                k,
            )
        ].subject.on_next(translations[k][0](v))

    def perform_call(call_kwargs):
        call_kwargs = {k[1]: v for k, v in call_kwargs.items()}
        safe_call_kwargs = {k: translations[k][1](v) for k, v in call_kwargs.items()}
        function(**safe_call_kwargs)

    submit(
        (prefix, "submit"),
        [(prefix, k) for k in signature.parameters.keys()],
        ui,
    ).subscribe(perform_call)


def layout_dataclass(
    dataclass_cls, prefix: Optional[str] = None, submit: Optional[str] = None
) -> QWidget:
    """
    Renders a dataclass instance to QtWidgets. See also `bind_dataclass` below
    to get one way data binding to the instance

    Args:
        dataclass_cls (type): The class definition for the field under layout.
        prefix (:obj:`str`, optional): UI ID prefix

    Returns:
        Qt.Widget corresponding to the fields of a dataclass, without any subscriptions or callbacks.
    """
    if prefix is None:
        prefix = dataclass_cls.__name__

    annotations = getattr(dataclass_cls, "_field_annotations", {})

    contents = []
    for field_name, field in dataclass_cls.__dataclass_fields__.items():
        contents.append(
            _layout_dataclass_field(field, field_name, prefix, annotations.get(field_name, {}))
        )

    if submit:
        contents.append(button(submit, id=(prefix, "submit!")))

    return vertical(*contents, alignment=Qt.AlignTop, content_margin=8)


def update_dataclass(dataclass_instance, prefix: str, ui: Dict[Hashable, QWidget]):
    """
    Because we do not support two way data binding here at the moment, we need to have a utility
    that lets us manually push updates to the UI. This is a kludge.

    Args:
        dataclass_instance: The instance to pull data from, it should typically be but does not have to be
        the one originally bound to the UI. If it is a different one, then the originally bound instance will be
        updated
        prefix: Prefix for the widgets, see also `layout_dataclass` and `bind_dataclass`
        ui: Collected UI Elements
    """

    instance_widgets = {k[1]: v for k, v in ui.items() if k[0] == prefix}
    for field_name, field in dataclass_instance.__dataclass_fields__.items():
        translate_from_field, translate_to_field = transforms_for_field(field)
        current_value = translate_from_field(getattr(dataclass_instance, field_name))
        instance_widgets[field_name].on_next(current_value)


def bind_dataclass(dataclass_instance, prefix: str, ui: Dict[Hashable, QWidget]):
    """
    One-way data binding between a dataclass instance and a collection of widgets in the UI.

    Sets the current UI state to the value of the Python dataclass instance, and sets up
    subscriptions to value changes on the UI so that any future changes are propagated to
    the dataclass instance.

    Args:
        dataclass_instance: Instance to link
        prefix: Prefix for widget IDs in the UI
        ui: Collected UI elements
    """
    instance_widgets = {k[1]: v for k, v in ui.items() if k[0] == prefix}
    submit_button = instance_widgets.pop("submit!", None)

    setters = {}
    for field_name, field in dataclass_instance.__dataclass_fields__.items():
        translate_from_field, translate_to_field = transforms_for_field(field)
        current_value = translate_from_field(getattr(dataclass_instance, field_name))
        instance_widgets[field_name].on_next(current_value)

        # close over the translation function
        def build_setter(translate, name):
            def setter(value):
                try:
                    value = translate(value)
                except ValueError:
                    return

                setattr(dataclass_instance, name, value)

            return setter

        setter = build_setter(translate_to_field, field_name)
        setters[field_name] = setter

        if submit_button is None:
            instance_widgets[field_name].subscribe(setter)

    def write_all(values):
        values = {k[1]: v for k, v in values.items()}
        for k, v in values.items():
            setters[k](v)

    if submit_button:
        submit(
            gate=(prefix, "submit!"),
            keys=[(prefix, k) for k in instance_widgets],
            ui=ui,
        ).subscribe(write_all)


def transforms_for_field(field):
    MAP_TYPES = {
        int: (lambda x: str(x), lambda x: int(x)),
        float: (lambda x: str(x), lambda x: float(x)),
    }

    translate_from_field, translate_to_field = MAP_TYPES.get(field.type, (lambda x: x, lambda x: x))

    if issubclass(field.type, Enum):
        enum_type = type(list(field.type.__members__.values())[0].value)

        forward_mapping = dict(
            sorted(enum_mapping(field.type).items(), key=lambda x: enum_type(x[1]))
        )
        inverse_mapping = {v: k for k, v in forward_mapping.items()}

        def extract_field(v):
            try:
                return v.value
            except AttributeError:
                return v

        translate_to_field = lambda x: field.type(forward_mapping[x])
        translate_from_field = lambda x: inverse_mapping[extract_field(x)]

    return translate_from_field, translate_to_field
