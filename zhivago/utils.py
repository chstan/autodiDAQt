import datetime
from json import JSONEncoder
import functools
from pathlib import Path
import enum
import asyncio
from typing import Dict, List, Type, TypeVar

__all__ = (
    'ZHIVAGO_LIB_ROOT', 'run_on_loop', 'find_conflict_free_matches',
    'gather_dict', 'find_conflict_free_matches',
    'enum_option_names', 'enum_mapping',
)

ZHIVAGO_LIB_ROOT = Path(__file__).parent.absolute()

def enum_option_names(enum_cls: Type[enum.Enum]) -> List[str]:
    return [x for x in dir(enum_cls) if '__' not in x]

def enum_mapping(enum_cls: Type[enum.Enum], invert=False):
    options = enum_option_names(enum_cls)
    d = dict([[o, getattr(enum_cls, o)] for o in options])
    if invert:
        d = {v: k for k, v in d.items()}
    return d



def mock_print(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        print(f'{f.__name__}: {args}, {kwargs}')

    return wrapped

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


T = TypeVar('T')
def find_conflict_free_matches(constraints: Dict[str, List[T]]) -> Dict[str, T]:
    """
    Given allowable matches between keys and lists of values, finds a pairing such that every
    key is paired to a single value uniquely, satisfying the constraints.

    As an example, if given constraints
    constraints = {
        'a': [1, 2, 3],
        'b: [2],
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
            raise ValueError('Matches not consistent.')
        else:
            results[found_key] = options[0]
            current = {k: [v for v in vs if v != options[0]]
                       for k, vs in current.items() if k != found_key}

    return results

class RichEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()

        elif isinstance(o, datetime.timedelta):
            return (datetime.datetime.min + o).time().isoformat()

        return super().default(o)
