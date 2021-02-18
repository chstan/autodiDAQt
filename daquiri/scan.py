import itertools
import random
from dataclasses import Field, field, make_dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Iterator, List, Tuple, Union

import numpy as np

from daquiri.instrument.spec import (
    ChoicePropertySpecification,
    DataclassPropertySpecification,
)
from daquiri.utils import (
    AccessRecorder,
    InstrumentScanAccessRecorder,
    PathType,
    _try_unwrap_value,
    tokenize_access_path,
)

__all__ = (
    "ScanAxis",
    "scan",
    "randomly",
    "forwards_and_backwards",
    "backwards",
    "only",
    "staircase_product",
    "step_together",
)


def randomly(seq):
    seq = list(seq)
    random.shuffle(seq)
    yield from seq


def only(n):
    def strategy(seq):
        yield from itertools.islice(seq, n)

    return strategy


def backwards(seq):
    yield from list(seq)[::-1]


def forwards_and_backwards(seq):
    yield from seq
    yield from backwards(seq)


def _set_profile(scope, profile_name):
    return {
        "call": ([profile_name], {}),
        "path": ["set_profile"],
        "scope": scope,
    }


FieldSetType = Tuple[str, type, Field]


class ScanDegreeOfFreedom:
    devices: PathType

    @property
    def independent_axes(self) -> List[PathType]:
        return [self.devices]

    def independent_renamings(self, name: str) -> List[Tuple[PathType, str]]:
        return [(self.devices, name)]

    def to_postfixless_fields(self) -> List[FieldSetType]:
        raise NotImplementedError

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        def postfix(f: FieldSetType) -> FieldSetType:
            return f"{f[0]}_{base_name}", f[1], f[2]

        return [postfix(f) for f in self.to_postfixless_fields()]

    def write(self, value) -> List[Dict[str, Any]]:
        return [
            {
                "write": value,
                "path": list(self.devices[1:]),
                "scope": self.devices[0],
            }
        ]

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        raise NotImplementedError

    def step(self, *strategies):
        return SimpleStrategyScan(self, strategies)


class SimpleStrategyScan(ScanDegreeOfFreedom):
    def __init__(
        self,
        internal_scan: ScanDegreeOfFreedom,
        strategies: Iterable[Callable] = None,
    ):
        self.internal_scan = internal_scan
        self.strategies = strategies or []

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        return self.internal_scan.to_fields(base_name)

    def to_postfixless_fields(self) -> List[FieldSetType]:
        return self.internal_scan.to_postfixless_fields()

    def write(self, value) -> List[Dict[str, Any]]:
        return self.internal_scan.write(value)

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        base_iterator = self.internal_scan.iterate(fields=fields, base_name=base_name)

        for strategy in self.strategies:
            base_iterator = strategy(base_iterator)

        yield from base_iterator

    @property
    def devices(self):
        return self.internal_scan.devices

    def independent_renamings(self, name: str) -> List[Tuple[PathType, str]]:
        return self.internal_scan.independent_renamings(name)


class StaircaseProduct(ScanDegreeOfFreedom):
    def __init__(self, scan_outer: ScanDegreeOfFreedom, scan_inner: ScanDegreeOfFreedom):
        self.scan_outer = scan_outer
        self.scan_inner = scan_inner

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        return self.scan_outer.to_fields(
            base_name=f"outer_{base_name}"
        ) + self.scan_inner.to_fields(base_name=f"inner_{base_name}")

    @property
    def independent_axes(self) -> List[PathType]:
        return list(self.scan_outer.independent_axes) + list(self.scan_inner.independent_axes)

    def independent_renamings(self, name: str) -> List[Tuple[PathType, str]]:
        return list(self.scan_inner.independent_renamings(name=f"{name}-inner")) + list(
            self.scan_outer.independent_renamings(name=f"{name}-outer")
        )

    def write(self, value) -> List[Dict[str, Any]]:
        writes = []

        if value[0] is not None:
            writes += self.scan_outer.write(value[0])

        if value[1] is not None:
            writes += self.scan_inner.write(value[1])

        return writes

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        flat_inner = list(self.scan_inner.iterate(fields, base_name=f"inner_{base_name}"))

        forwards = True
        for outer in self.scan_outer.iterate(fields, base_name=f"outer_{base_name}"):
            yield from zip(
                itertools.cycle([outer]),
                flat_inner if forwards else flat_inner[::-1],
            )
            forwards = not forwards


def staircase_product(outer: ScanDegreeOfFreedom, inner: ScanDegreeOfFreedom) -> StaircaseProduct:
    return StaircaseProduct(scan_outer=outer, scan_inner=inner)


class ScanTogether(ScanDegreeOfFreedom):
    def __init__(self, *inner_scans: ScanDegreeOfFreedom):
        self.inner_scans = inner_scans

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        return list(
            itertools.chain(
                *[
                    inner_scan.to_fields(base_name=f"{i}_{base_name}")
                    for i, inner_scan in enumerate(self.inner_scans)
                ]
            )
        )

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        yield from zip(
            *[
                inner_scan.iterate(fields, f"{i}_{base_name}")
                for i, inner_scan in enumerate(self.inner_scans)
            ]
        )

    @property
    def independent_axes(self) -> List[PathType]:
        return list(
            itertools.chain(*[inner_scan.independent_axes for inner_scan in self.inner_scans])
        )

    def independent_renamings(self, name: str) -> List[Tuple[PathType, str]]:
        return list(
            itertools.chain(
                *[
                    inner_scan.independent_renamings(name=f"{name}-{i}")
                    for i, inner_scan in enumerate(self.inner_scans)
                ]
            )
        )

    def write(self, value) -> List[Dict[str, Any]]:
        return list(itertools.chain(*[s.write(v) for v, s in zip(value, self.inner_scans)]))


def step_together(*scans: ScanDegreeOfFreedom):
    return ScanTogether(*scans)


class ScanProperty(ScanDegreeOfFreedom):
    def __init__(self, device_name: Union[str, AccessRecorder], spec):
        self.spec = spec

        if isinstance(device_name, InstrumentScanAccessRecorder):
            self.devices = device_name.full_path_()
        else:
            self.devices = tokenize_access_path(device_name)

    def __repr__(self):
        return f"{self.__class__.__name__}(device_name={self.devices})"

    def write(self, value) -> List[Dict[str, Any]]:
        return [
            {
                "set": value,
                "path": list(self.devices[1:]),
                "scope": self.devices[0],
            }
        ]


def field_to_ranged_ui_fields(field_name, f):
    """
    Takes the definition of a field from a dataclass and determines how to
    provide "range controls".

    Args:
        field_name (str): Name of the field being rendered currently.
        f: Internal field specification created by @dataclasses.dataclass
    """
    return None


class ScanDataclassProperty(ScanProperty):
    spec: DataclassPropertySpecification

    def __repr__(self):
        return (
            f"ScanDataclassProperty(device_name={self.devices}, spec.data_cls={self.spec.data_cls})"
        )

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        for field_name, f in self.spec.data_cls.__dataclass_fields__.items():
            print(field_to_ui_fields(field_name, f))

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        pass


class ScanChoiceProperty(ScanProperty):
    spec: ChoicePropertySpecification
    inclusive = True

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        enum_items = {v: i + 1 for i, (k, v) in enumerate(self.spec.labels.items())}
        ValuesEnum = Enum(f"{base_name}Values", enum_items)

        return [
            (f"start_{base_name}", ValuesEnum, field(default=1)),
            (f"stop_{base_name}", ValuesEnum, field(default=len(self.spec.choices))),
        ]

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        start = _try_unwrap_value(getattr(fields, f"start_{base_name}"))
        stop = _try_unwrap_value(getattr(fields, f"stop_{base_name}"))

        stop_delta = 0 if self.inclusive else -1
        return list(self.spec.choices.values())[start - 1 : stop + stop_delta]


class ScanAxis(ScanDegreeOfFreedom):
    values = None

    def __init__(
        self,
        device_name: Union[str, AccessRecorder],
        limits=None,
        values=None,
        is_property=False,
    ):
        if isinstance(device_name, InstrumentScanAccessRecorder):
            self.devices = device_name.full_path_()
            self.limits = device_name.limits_()
            self.values = device_name.values_()
            self.name = device_name.name_()
            self.is_property = device_name.is_property_()
        else:
            self.devices = tokenize_access_path(device_name)
            self.name = device_name
            self.is_property = is_property

        if limits is not None:
            self.limits = limits
        if values is not None:
            self.values = values

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        if self.values is None:
            return [
                (f"n_{base_name}", int, field(default=5)),
                (f"start_{base_name}", float, field(default=0)),
                (f"stop_{base_name}", float, field(default=10)),
            ]
        else:
            # TODO need to be careful here as the labels we present in the UI need to be massaged.
            ValuesEnum = Enum(
                f"{base_name}Values",
                {k: i + 1 for i, (k, _) in enumerate(self.values.items())},
            )

            return [
                (f"start_{base_name}", ValuesEnum, field(default=1)),
                (
                    f"stop_{base_name}",
                    ValuesEnum,
                    field(default=len(self.values)),
                ),
            ]

    def write(self, value) -> List[Dict[str, Any]]:
        return [
            {
                "write": value,
                "path": list(self.devices[1:]),
                "scope": self.devices[0],
            }
        ]

    def iterate(self, fields, base_name) -> Iterator[Any]:
        if self.values is None:
            return np.linspace(
                getattr(fields, f"start_{base_name}"),
                getattr(fields, f"stop_{base_name}"),
                getattr(fields, f"n_{base_name}"),
                endpoint=True,
            )
        else:
            start, stop = (
                getattr(fields, f"start_{base_name}"),
                getattr(fields, f"stop_{base_name}"),
            )
            return list(self.values.values())[start:stop]

    def __repr__(self):
        return f"ScanAxis(device_name={self.devices}, limits={self.limits}, values={self.values})"


def scan(
    name=None,
    read=None,
    profiles=None,
    setup=None,
    teardown=None,
    preconditions=None,
    **axes: Union[str, ScanDegreeOfFreedom, AccessRecorder],
):
    if name is None:
        raise ValueError("You must provide a name for the scan.")

    if read is None:
        read = {}

    axes = {
        name: ax if isinstance(ax, ScanDegreeOfFreedom) else ScanAxis(ax)
        for name, ax in axes.items()
    }
    axes: Dict[str, ScanDegreeOfFreedom] = axes

    fields = {name: ax.to_fields(name) for name, ax in axes.items()}

    def sequence_scan(self, experiment, **kwargs):
        dependent = {
            read_name: tokenize_access_path(read_device) for read_name, read_device in read.items()
        }

        independent = list(
            itertools.chain(*[axis.independent_renamings(name) for name, axis in axes.items()])
        )
        extra = []
        experiment.collate(
            independent=independent,
            dependent=[[dependent[read_name], read_name] for read_name in read.keys()] + extra,
        )

        if preconditions:
            yield [{"preconditions": preconditions}]

        if profiles:
            yield [_set_profile(k, v) for k, v in profiles.items()]

        if setup:
            yield from setup(experiment, **kwargs)

        ax_names = list(axes.keys())
        coordinate_spaces = [
            axis.iterate(fields=self, base_name=name) for name, axis in axes.items()
        ]
        for locations in itertools.product(*coordinate_spaces):
            with experiment.point():
                experiment.comment(f"Moving {ax_names} to {locations}")
                yield list(
                    itertools.chain(
                        *[
                            axes[ax_name].write(location)
                            for ax_name, location in zip(ax_names, locations)
                        ]
                    )
                )
                yield [
                    {
                        "read": None,
                        "path": dependent[read_name][1:],
                        "scope": dependent[read_name][0],
                    }
                    for read_name in read.keys()
                ]

        if teardown:
            yield from teardown(experiment, **kwargs)

    scan_cls = make_dataclass(
        cls_name=name,
        fields=itertools.chain(*fields.values()),
        namespace={"sequence": sequence_scan},
    )

    return scan_cls
