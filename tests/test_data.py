import pytest
import random

from daquiri.data import ReactivePlot, reactive_frame
from .common.experiments import Sink


def test_reactive_frame():
    subj, frame = reactive_frame()

    class Box:
        value = None

        def set(self, value):
            self.value = value

    b = Box()
    frame.subscribe(b.set)

    subj.on_next({"x": 0, "y": 1})
    subj.on_next({"x": 5, "y": 2})
    subj.on_next({"x": 3, "y": 8})

    assert b.value.x.values.tolist() == [0, 5, 3]
    assert b.value.y.values.tolist() == [1, 2, 8]


class MockAx:
    figure = Sink()

    # lets
    xlim = None

    def __init__(self) -> None:
        self.x = []
        self.y = []

    def get_xlim(self):
        self.xlim = random.random()
        return self.xlim

    def set_xlim(self, xlim):
        # this functions as a test that we do not adjust the axis range
        assert xlim == self.xlim

    def scatter(self, x, y, **kwargs):
        self.x.extend(x)
        self.y.extend(y)


def test_link_plot_to_reactive_frame():
    ax = MockAx()
    subj, frame = reactive_frame()
    plot = ReactivePlot.link_scatter(ax, frame)

    subj.on_next({"y": 0})
    subj.on_next({"y": -2})
    subj.on_next({"y": 4})
    subj.on_next({"y": 3})

    assert ax.x == [0, 1, 2, 3]
    assert ax.y == [0, -2, 4, 3]
