import pytest
from matplotlib.figure import Figure
from pytestqt.qtbot import QtBot

from autodidaqt.panel import Panel

from .conftest import Mockautodidaqt


class FauxParent:
    def client_panel_will_close(self, _):
        pass


def test_panel_creation(app: Mockautodidaqt, qtbot: QtBot):
    panel = Panel(FauxParent(), "test", app)
    qtbot.add_widget(panel)

    assert panel


def test_figure_registration(app: Mockautodidaqt, qtbot: QtBot):
    panel = Panel(FauxParent(), "test", app)
    qtbot.add_widget(panel)

    fig = panel.register_figure("plot")

    assert len(panel.canvases) == 1
    assert len(panel.figures) == 1
    assert isinstance(fig, Figure)
