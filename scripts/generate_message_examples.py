import typing
from typing import Any

import datetime
import enum
import random
import uuid
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path

from autodidaqt_common.remote.command import InternalMessage, serialize_wire_types
from autodidaqt_common.remote.utils import ALL_WIRE_MESSAGES


def random_string(length=10):
    LETTERS = "abcdefghijklmnopqrstuvxyz"
    return "".join(random.choice(LETTERS) for _ in range(length))


TYPE_DEFAULTS = {
    # I gotta say, this is the weirdest legal syntax
    float: lambda: 3.14159,
    int: lambda: 0,
    str: random_string,
    bool: lambda: True,
    uuid.UUID: lambda: str(uuid.uuid4),
    datetime.datetime: lambda: datetime.datetime.now().isoformat(),
}


def fuzz_type(type_: Any):
    if isinstance(type_, type) and issubclass(type_, enum.Enum):
        return list((type_.__members__).values())[0]
    if isinstance(type_, type) and is_dataclass(type_):
        return fuzz(type_)
    if type_ in TYPE_DEFAULTS:
        return TYPE_DEFAULTS[type_]()
    if isinstance(type_, typing._GenericAlias):
        type_name = str(type_).replace("typing.", "")
        if type_name.startswith("List"):
            return [fuzz_type(type_.__args__[0]) for _ in range(5)]
        elif type_name.startswith("Union"):
            return fuzz_type(random.choice(type_.__args__))
        elif type_name.startswith("Dict"):
            key_type, value_type = type_.__args__
            return dict([[fuzz_type(key_type), fuzz_type(value_type)] for _ in range(5)])

    print(type_)
    raise NotImplementedError


def fuzz(datacls):
    init_values = {}

    for field in fields(datacls):
        if field.default_factory is not MISSING:
            init_values[field.name] = field.default_factory()
        elif field.default is not MISSING:
            init_values[field.name] = field.default
        else:
            init_values[field.name] = fuzz_type(field.type)

    return datacls(**init_values)


for name, cls in ALL_WIRE_MESSAGES.items():
    if not is_dataclass(cls) or issubclass(cls, InternalMessage):
        continue

    instance = fuzz(cls)
    path_to_output = Path(__file__).parent / ".." / "example_messages"
    path_to_output.mkdir(parents=True, exist_ok=True)

    print(name)
    with open(str(path_to_output / f"{name}.json"), "w") as f:
        f.write(serialize_wire_types(instance))
