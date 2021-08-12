import pytest

from autodidaqt.mock import MockMotionController
from autodidaqt.scan import forwards_and_backwards, only, randomly, staircase_product, step_together


def test_randomly():
    # technically stochastic, but I'm a betting man with these odds
    xs = list(range(400))
    vs = list(randomly(xs))
    assert xs != vs
    assert xs == sorted(vs)


def test_only():
    xs = range(500)
    assert list(only(5)(xs)) == [0, 1, 2, 3, 4]


def test_forwards_and_backwards():
    xs = [0, 1, 2]
    assert list(forwards_and_backwards(xs)) == [0, 1, 2, 2, 1, 0]


def test_simple_scan_contents():
    dx = MockMotionController.scan("mc").stages[0]()
    assert sorted(name for name, _, __ in dx.to_fields("x")) == ["n_x", "start_x", "stop_x"]

    class HoldsData:
        n_x: int = 4
        start_x: int = 0
        stop_x: int = 3

    data = HoldsData()
    assert list(dx.iterate(data, "x")) == [0, 1, 2, 3]
    data.n_x = 7
    assert list(dx.iterate(data, "x")) == [0, 0.5, 1, 1.5, 2, 2.5, 3]


def test_staircase_product(mocker):
    dx, dy = [MockMotionController.scan("mc").stages[i]() for i in [0, 1]]
    prod = staircase_product(dx, dy)

    class HoldsData:
        n_inner_xy = 3
        start_inner_xy = 0
        stop_inner_xy = 2

        n_outer_xy = 3
        start_outer_xy = 10
        stop_outer_xy = 12

    data = HoldsData()

    assert list(prod.iterate(data, "xy")) == [
        (10, 0),
        (10, 1),
        (10, 2),
        (11, 2),
        (11, 1),
        (11, 0),
        (12, 0),
        (12, 1),
        (12, 2),
    ]

    spy_dx = mocker.spy(dx, "write")
    spy_dy = mocker.spy(dy, "write")
    written = prod.write((5, 6))
    assert written == [
        {"path": ["stages", 0], "write": 5, "scope": "mc"},
        {"path": ["stages", 1], "write": 6, "scope": "mc"},
    ]
    spy_dx.assert_called_once_with(5)
    spy_dy.assert_called_once_with(6)


def test_step_together():
    dx, dy, dz = [MockMotionController.scan("mc").stages[i]() for i in [0, 1, 2]]
    together = step_together(dx, dy, dz)

    class HoldsData:
        n_0_xyz = 3
        start_0_xyz = 0
        stop_0_xyz = 2

        n_1_xyz = 3
        start_1_xyz = 0
        stop_1_xyz = 4

        n_2_xyz = 3
        start_2_xyz = 0
        stop_2_xyz = -2

    data = HoldsData()

    assert list(together.iterate(data, "xyz")) == [(0, 0, 0), (1, 2, -1), (2, 4, -2)]
