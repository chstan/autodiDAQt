import asyncio
import contextlib
import datetime
import enum
import functools
import os
from contextlib import contextmanager
from json import JSONEncoder
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type, TypeVar, Union

__all__ = (
    "DAQUIRI_LIB_ROOT",
    "run_on_loop",
    "gather_dict",
    "find_conflict_free_matches",
    "enum_option_names",
    "enum_mapping",
    "temporary_attrs",
    "tokenize_access_path",
    "safe_lookup",
    "AccessRecorder",
    "ScanAccessRecorder",
    "InstrumentScanAccessRecorder",
    "RichEncoder",
)

DAQUIRI_LIB_ROOT = Path(__file__).parent.absolute()

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
    with open(str(DAQUIRI_LIB_ROOT / "resources" / "default_styles.scss")) as f:
        styles = f.read()

    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            import qtsass  # <- why is this printing on import?

            compiled = qtsass.compile(styles, include_paths=[str(DAQUIRI_LIB_ROOT / "resources")])

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


@functools.lru_cache(maxsize=256)
def tokenize_string_path(s: str):
    def safe_unwrap_int(value):
        try:
            return int(value)
        except ValueError:
            return str(value)

    return tuple(safe_unwrap_int(x) for x in s.replace("[", ".").replace("]", "").split(".") if x)


def tokenize_access_path(str_or_list) -> Tuple[Union[str, int]]:
    """
    Turns a string-like accessor into a list of tokens

    Examples:
        a.b[0].c -> ['a', 'b', 0, 'c']

    Args:
        str_or_list:

    Returns:
        The tokenize path as a tuple of ints and strings
    """
    if isinstance(str_or_list, (tuple, list)):
        return str_or_list

    return tokenize_string_path(str_or_list)


def _try_unwrap_value(v):
    try:
        return v.value
    except AttributeError:
        return v


def enum_option_names(enum_cls: Type[enum.Enum]) -> List[str]:
    names = [x for x in dir(enum_cls) if "__" not in x]
    values = [_try_unwrap_value(getattr(enum_cls, n)) for n in names]

    return [x[0] for x in sorted(zip(names, values), key=lambda x: x[1])]


def enum_mapping(enum_cls: Type[enum.Enum], invert=False):
    options = enum_option_names(enum_cls)
    d = dict([[o, _try_unwrap_value(getattr(enum_cls, o))] for o in options])
    if invert:
        d = {v: k for k, v in d.items()}
    return d


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


class RichEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return (datetime.datetime.min + o).time().isoformat()
        elif callable(o):
            return o.__name__

        return super().default(o)


class AccessRecorder:
    def __init__(self, scope=None):
        self.path = []
        self.scope = scope

    def __getattr__(self, item):
        self.path.append(item)
        return self

    def __getitem__(self, item):
        self.path.append(item)
        return self

    def name_(self):
        return ".".join(map(str, self.full_path_()))

    def full_path_(self):
        return tuple(([] if self.scope is None else [self.scope]) + self.path)


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
        from daquiri.instrument.property import ChoiceProperty

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
