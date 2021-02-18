from daquiri.ui.lens import Lens, LensSubject
import pytest


def test_lenses_basic():
    subj = LensSubject(
        {
            "a": {"b": {"d": 5}, "c": [4]},
            "f": -1,
            "g": [0, 1, 2],
        }
    )

    l1 = Lens(subj, lambda x: x["a"], lambda fv, sv: {**fv, "a": sv})
    l2 = l1.view(lambda x: x["b"], lambda fv, sv: {**fv, "b": sv})
    l3 = l2.view_index("d")

    l4 = subj.view(lambda x: x["f"], lambda fv, sv: {**fv, "f": sv})

    l5 = l1.view_index("c").view_index(0)

    l1_events = []
    l2_events = []
    l3_events = []
    l4_events = []
    l5_events = []

    l1.subscribe(l1_events.append)
    l2.subscribe(l2_events.append)
    l3.subscribe(l3_events.append)
    l4.subscribe(l4_events.append)
    l5.subscribe(l5_events.append)

    l4.on_next(2)

    assert l4_events == [-1, 2]

    l3.on_next(3)
    assert l4_events == [-1, 2, 2]

    assert l3_events == [5, 5, 3]
    assert l2_events == [
        {"d": 5},
        {"d": 5},
        {"d": 3},
    ]

    l5.on_next(0)
    assert l5_events == [4, 4, 4, 0]
