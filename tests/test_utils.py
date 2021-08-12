import datetime
import enum
import json

import pytest
from autodidaqt_common.enum import enum_mapping, enum_option_names
from autodidaqt_common.json import RichEncoder

from autodidaqt.collections import AttrDict
from autodidaqt.utils import (
    AccessRecorder,
    ScanAccessRecorder,
    find_conflict_free_matches,
    temporary_attrs,
)


def test_temporary_attrs():
    a = AttrDict({"a": 3, "b": 4, "c": 5})

    with temporary_attrs(a, b=-2, c=None):
        assert a.b == -2
        assert a.c is None

    assert a.b == 4
    assert a.c == 5


class E1(str, enum.Enum):
    First = "first"
    Second = "second"


def test_enum_option_names():
    assert enum_option_names(E1) == ["First", "Second"]


def test_enum_mapping():
    # names to values
    assert enum_mapping(E1) == {
        "First": "first",
        "Second": "second",
    }

    # values to names
    assert enum_mapping(E1, invert=True) == {
        "first": "First",
        "second": "Second",
    }


def test_find_conflict_free_matches():
    constraints = {
        "a": [1, 2, 3],
        "b": [2],
        "c": [1],
    }

    assert find_conflict_free_matches(constraints) == {"a": 3, "b": 2, "c": 1}


def test_rich_json_encoding():
    def my_fn():
        pass

    iso_date = "2021-02-14T23:41:47.423835"
    start_data = {
        "date": datetime.datetime.fromisoformat(iso_date),
        "delta": datetime.timedelta(hours=1, seconds=5),
        "callable": my_fn,
        "standard": "standard",
    }
    intermediate = json.dumps(start_data, cls=RichEncoder)

    assert json.loads(intermediate) == {
        "date": iso_date,
        "delta": "01:00:05",
        "callable": "my_fn",
        "standard": "standard",
    }


def test_access_recorder():
    recorder = AccessRecorder()
    x = recorder.x.y.z[0].w

    assert recorder.path == ["x", "y", "z", 0, "w"]


def test_scan_access_recorder():
    recorder = ScanAccessRecorder()
    v = recorder.x[0].write(5)

    assert v == {
        "write": 5,
        "scope": None,
        "path": ["x", 0],
    }
