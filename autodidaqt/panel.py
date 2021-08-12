from typing import Optional, Tuple, Type

from pathlib import Path

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication, QGridLayout, QLabel, QMainWindow, QPushButton, QWidget

from autodidaqt.state import PanelState
from autodidaqt.utils import default_stylesheet

__all__ = (
    "Panel",
    "open_appless_panel",
)


def figure(figsize=None, toolbar=None) -> Tuple[FigureCanvas, Figure, Optional[NavigationToolbar]]:
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

    TITLE = "Panel"
    CLOSE_TEXT = "Close"
    DEFAULT_OPEN = False
    RESTART = False
    SIZE = (
        600,
        600,
    )

    def collect_state(self) -> PanelState:
        return PanelState(geometry=self.geometry())

    def receive_state(self, state: PanelState):
        if state is None:
            return

        self.setGeometry(state.geometry)

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

        label = QLabel("A label")
        layout.addWidget(label)
        layout.addWidget(self.close_button)

        self.setLayout(layout)


def open_appless_panel(panel_cls: Type[Panel]):  # pragma: no cover
    import asyncio

    app = QApplication([])
    font_db = QFontDatabase()

    for font in (Path(__file__).parent / "resources" / "fonts").glob("*.ttf"):
        font_db.addApplicationFont(str(font))

    app.setStyleSheet(default_stylesheet())

    class FauxParent:
        def client_panel_will_close(self, _):
            app.exit()

    class Hooks:
        qt_app = None

        def __init__(self, qt_app):
            self.qt_app = qt_app

        async def process_events(self):
            while True:
                await asyncio.sleep(0.03)
                self.qt_app.processEvents()

    window_widget = panel_cls(parent=FauxParent(), id="appless", app=None)

    window = QMainWindow()
    window.setCentralWidget(window_widget)

    screen_rect = app.primaryScreen().geometry()
    window.move(screen_rect.left(), screen_rect.top())
    window.resize(*panel_cls.SIZE)

    window.app = None
    window.show()
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(Hooks(app).process_events())
    loop.run_forever()
