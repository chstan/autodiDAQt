from typing import Any, Dict

import pytest

from autodidaqt.collections import *


def inc(x):
    return x + 1


def catcat(x):
    return [x, x]


@pytest.mark.parametrize(
    ("input", "output", "mapping"),
    [
        ({"a": {"b": 5}, "c": -1}, {"a": {"b": 6}, "c": 0}, inc),
        ({"a": {"b": 5}}, {"a": {"b": [5, 5]}}, catcat),
    ],
)
def test_map_tree_leaves(input, output, mapping):
    assert map_tree_leaves(input, mapping) == output


def uppercase_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k.upper(): v for k, v in d.items()}


doubles_lists = {
    dict: lambda x: x,
    list: lambda x: x + x,
}


@pytest.mark.parametrize(
    ("input", "output", "mapping"),
    [
        ({"a": {"b": 5}, "c": -1}, {"A": {"B": 5}, "C": -1}, uppercase_keys),
        ({"a": [{"a": 5}, {"d": 4}]}, {"A": [{"A": 5}, {"D": 4}]}, uppercase_keys),
        (
            {"a": {"b": 4}, "d": [2, {"a": 1}]},
            {"a": {"b": 4}, "d": [2, {"a": 1}, 2, {"a": 1}]},
            doubles_lists,
        ),
    ],
)
def test_map_treelike_nodes(input, output, mapping):
    assert map_treelike_nodes(input, mapping) == output


def test_attrdict():
    a = AttrDict({"a": {"b": {"c": 1}}})

    # gets the right values
    assert a.nested_get(["a", "b", "c"], -1) == 1

    # early KeyError propagates
    with pytest.raises(KeyError) as exc:
        v = a.nested_get(["a", "f", "c"], -1)

    assert exc

    # allow early KeyError to return default
    assert a.nested_get(["a", "f", "c"], -1, safe_early_terminate=True) == -1

    # allow early exit if we reach a leaf
    assert a.nested_get(["a", "b", "c", "c"], -1, safe_early_terminate=True) == -1


def test_deep_update():
    src = {"a": {"b": {"c": 5}}}
    dst = {"a": {"b": {"d": 6}}}

    assert deep_update(src, dst) == {"a": {"b": {"c": 5, "d": 6}}}
