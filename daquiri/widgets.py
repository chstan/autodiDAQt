import os

from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLineEdit,
    QPushButton, QRadioButton, QSlider, QSpinBox, QTextEdit, QWidget)
from rx.subject import BehaviorSubject, Subject

__all__ = (
    "PushButton",
    "CheckBox",
    "ComboBox",
    "FileDialog",
    "LineEdit",
    "RadioButton",
    "Slider",
    "SpinBox",
    "DoubleSpinBox",
    "TextEdit",
)


class Subjective:
    subject = None

    def subscribe(self, *args, **kwargs):
        self.subject.subscribe(*args, **kwargs)

    def on_next(self, *args, **kwargs):
        self.subject.on_next(*args, **kwargs)


class ComboBox(QComboBox, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.currentData())

        self.currentIndexChanged.connect(
            lambda: self.subject.on_next(self.currentText())
        )
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        if self.currentText() != value:
            self.setCurrentText(value)


class SpinBox(QSpinBox, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.value())

        self.valueChanged.connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setValue(value)


class TextEdit(QTextEdit, Subjective):
    def __init__(self, *args, subject=None):
        super().__init__(*args)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.toPlainText())

        self.textChanged.connect(lambda: self.subject.on_next(self.toPlainText()))
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        if self.toPlainText() != value:
            self.setPlainText(value)


class Slider(QSlider, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.value())

        self.valueChanged.connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setValue(value)


class LineEdit(QLineEdit, Subjective):
    def __init__(self, *args, subject=None, process_on_next=None):
        super().__init__(*args)

        self.subject = subject
        self.process_on_next = process_on_next
        if self.subject is None:
            self.subject = BehaviorSubject(self.text())

        self.textChanged[str].connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        if self.process_on_next:
            value = self.process_on_next(value)

        if value != self.text():
            self.setText(value)


class RadioButton(QRadioButton, Subjective):
    def __init__(self, *args, subject=None):
        super().__init__(*args)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.isChecked())

        self.toggled.connect(lambda: self.subject.on_next(self.isChecked()))
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setChecked(value)


class FileDialog(QWidget, Subjective):
    def __init__(self, *args, subject=None, single=True, dialog_root=None):
        if dialog_root is None:
            dialog_root = os.getcwd()

        super().__init__(*args)

        self.dialog_root = dialog_root

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(None)

        layout = QHBoxLayout()
        self.btn = PushButton("Open")
        if single:
            self.btn.subject.subscribe(on_next=lambda _: self.get_file())
        else:
            self.btn.subject.subscribe(on_next=lambda _: self.get_files())

        layout.addWidget(self.btn)
        self.setLayout(layout)

    def get_file(self):
        filename = QFileDialog.getOpenFileName(self, "Open File", self.dialog_root)

        self.subject.on_next(filename[0])

    def get_files(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)

        if dialog.exec_():
            filenames = dialog.selectedFiles()
            self.subject.on_next(filenames)


class PushButton(QPushButton, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args)

        self.subject = subject
        if self.subject is None:
            self.subject = Subject()
        self.clicked.connect(lambda: self.subject.on_next(True))


class CheckBox(QCheckBox, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.checkState())

        self.stateChanged.connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setCheckState(value)


class SpinBox(QSpinBox, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.value())

        self.valueChanged.connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setValue(int(value))


class DoubleSpinBox(QDoubleSpinBox, Subjective):
    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject
        if self.subject is None:
            self.subject = BehaviorSubject(self.value())

        self.valueChanged.connect(self.subject.on_next)
        self.subject.subscribe(self.update_ui)

    def update_ui(self, value):
        self.setValue(float(value))
