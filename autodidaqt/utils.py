from typing import Any, Dict, List, Tuple, TypeVar, Union

import asyncio
import contextlib
import os
from contextlib import contextmanager
from pathlib import Path

from autodidaqt_common.path import AccessRecorder

__all__ = (
    "autodidaqt_LIB_ROOT",
    "run_on_loop",
    "gather_dict",
    "find_conflict_free_matches",
    "temporary_attrs",
    "safe_lookup",
    "ScanAccessRecorder",
    "InstrumentScanAccessRecorder",
)

autodidaqt_LIB_ROOT = Path(__file__).parent.absolute()

PathFragmentType = Union[str, int]
PathType = Union[List[PathFragmentType], Tuple[PathFragmentType]]
PathlikeType = Union[PathFragmentType, Path]


@contextmanager
def temporary_attrs(owner, **kwargs):
    previous_values = {k: getattr(owner, k) for k in kwargs}

    for k, v in kwargs.items():
        setattr(owner, k, v)

    try:
        yield
    finally:
        for k, v in previous_values.items():
            setattr(owner, k, v)


def default_stylesheet() -> str:
    with open(str(autodidaqt_LIB_ROOT / "resources" / "default_styles.scss")) as f:
        styles = f.read()

    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            import qtsass  # <- why is this printing on import?

            compiled = qtsass.compile(
                styles, include_paths=[str(autodidaqt_LIB_ROOT / "resources")]
            )

    return compiled


def safe_lookup(d: Any, s: PathlikeType):
    if isinstance(s, (tuple, list)):
        if len(s) == 0:
            return d
        if len(s) == 1:
            return safe_lookup(d, s[0])

        first, rst = s[0], s[1:]
        return safe_lookup(safe_lookup(d, first), rst)

    elif isinstance(s, str):
        return getattr(d, s)
    return d[s]


def run_on_loop(coroutine_fn, *args, **kwargs):
    loop = asyncio.new_event_loop()
    with loop:
        coroutine = coroutine_fn(*args, **kwargs)
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)


async def gather_dict(tasks, **ktasks):
    all = tasks
    all.update(ktasks)

    values = await asyncio.gather(*list(all.values()))
    return dict(zip(all.keys(), values))


T = TypeVar("T")


def find_conflict_free_matches(constraints: Dict[str, List[T]]) -> Dict[str, T]:
    """
    Given allowable matches between keys and lists of values, finds a pairing such that every
    key is paired to a single value uniquely, satisfying the constraints.

    As an example, if given constraints
    constraints = {
        'a': [1, 2, 3],
        'b': [2],
        'c': [1],
    }

    returns {
        'a': 3,
        'b': 2,
        'c': 1
    }

    Guaranteeed slow, but no need to optimize now.
    """

    results = {}
    current = constraints
    while len(current):
        found_key, found_options = None, None

        for key, options in current.items():
            if len(options) == 1:
                found_key, found_options = key, options
                break

        if found_key is None:
            raise ValueError("Matches not consistent.")
        else:
            results[found_key] = options[0]
            current = {
                k: [v for v in vs if v != options[0]] for k, vs in current.items() if k != found_key
            }

    return results


class ScanAccessRecorder(AccessRecorder):
    def write(self, value):
        return {"write": value, "path": self.path, "scope": self.scope}

    def read(self):
        return {
            "read": None,
            "path": self.path,
            "scope": self.scope,
        }

    def __call__(self, *args, **kwargs):
        return {
            "call": (args, kwargs),
            "path": self.path,
            "scope": self.scope,
        }


class InstrumentScanAccessRecorder(AccessRecorder):
    def __init__(self, instrument, axis_specifications, properties):
        self.axis_spec_ = axis_specifications
        self.properties_ = properties

        super().__init__(instrument)

    def values_(self):
        from autodidaqt.instrument.property import ChoiceProperty

        first = self.path[0]
        if first in self.properties_:
            prop = self.properties_[first]
            assert (
                len(self.path) == 1
                and "You can scan a property, but properties have no sub-attributes or items"
            )

            if isinstance(prop, ChoiceProperty):
                labels, choices = prop.labels, prop.choices
                if isinstance(labels, list):
                    return dict(zip(labels, choices))
                elif callable(labels):
                    return dict(zip(map(labels, choices), choices))
                elif labels is None:
                    return dict(zip(map(str, choices), choices))

            return None

    def limits_(self):
        return None

    def is_property_(self):
        return len(self.path) == 1 and self.path[0] in self.properties_
