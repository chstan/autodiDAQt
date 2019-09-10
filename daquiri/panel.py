from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure

from PyQt5.QtWidgets import QWidget, QPushButton, QGridLayout, QLabel

__all__ = ('Panel',)


def figure(figsize=None, toolbar=None):
    built_figure = Figure(figsize=figsize)
    canvas = FigureCanvas(built_figure)

    bar = None
    if toolbar:
        bar = NavigationToolbar(canvas, toolbar)

    return canvas, built_figure, bar

class Panel(QWidget):
    """
    A base class for windows that attach to the main application.
    """
    TITLE = 'Panel'
    CLOSE_TEXT = 'Close'
    DEFAULT_OPEN = False
    RESTART = False
    SIZE = (50,50,)

    def register_figure(self, name, toolbar=None, layout=None, *args, **kwargs):
        assert name not in self.canvases
        if toolbar is not None:
            toolbar = self

        canvas, fig, bar = figure(*args, toolbar=toolbar, **kwargs)
        self.canvases[name] = canvas
        self.figures[name] = fig
        self.toolbars[name] = bar

        if layout:
            if bar is not None:
                layout.addWidget(bar)
            layout.addWidget(canvas)

        return fig

    def before_close(self):
        self.parent.client_panel_will_close(self.id)

    def do_close(self):
        self.before_close()
        self.close()

    def closeEvent(self, event):
        self.before_close()
        super().closeEvent(event)

    def __init__(self, parent, id, app, defer_layout=False):
        super().__init__()

        self.canvases = {}
        self.figures = {}
        self.toolbars = {}
        self.app = app

        self.setWindowTitle(self.TITLE)

        self.parent = parent
        self.id = id

        self.close_button = QPushButton(self.CLOSE_TEXT)
        self.close_button.clicked.connect(self.do_close)

        if not defer_layout:
            self.layout()
            self.resize(*self.SIZE)

    def layout(self):
        layout = QGridLayout()

        label = QLabel('A label')
        layout.addWidget(label)
        layout.addWidget(self.close_button)

        self.setLayout(layout)

