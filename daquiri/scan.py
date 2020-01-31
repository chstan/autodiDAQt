from dataclasses import make_dataclass, field, Field
from enum import Enum

from typing import Union, Iterator, Any, Dict, Tuple, List

import numpy as np
import itertools

from daquiri.instrument.spec import ChoicePropertySpecification, DataclassPropertySpecification
from daquiri.utils import AccessRecorder, InstrumentScanAccessRecorder, tokenize_access_path, PathType

__all__ = ('ScanAxis', 'scan')


def _set_profile(scope, profile_name):
    return {
        'call': ([profile_name], {}),
        'path': ['set_profile'],
        'scope': scope,
    }


FieldSetType = Tuple[str, type, Field]


class ScanDegreeOfFreedom:
    devices: PathType

    def to_postfixless_fields(self) -> List[FieldSetType]:
        raise NotImplementedError()

    def to_fields(self, base_name: str) -> List[FieldSetType]:
        def postfix(f: FieldSetType) -> FieldSetType:
            return f'{f[0]}_{base_name}', f[1], f[2]

        return [postfix(f) for f in self.to_postfixless_fields()]

    def write(self, value) -> Dict[str, Any]:
        return {'write': value, 'path': list(self.devices[1:]), 'scope': self.devices[0], }

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        raise NotImplementedError()


class ScanProperty(ScanDegreeOfFreedom):
    def __init__(self, device_name: Union[str, AccessRecorder], spec):
        self.spec = spec

        if isinstance(device_name, InstrumentScanAccessRecorder):
            self.devices = device_name.full_path_()
        else:
            self.devices = tokenize_access_path(device_name)

    def __repr__(self):
        return f'{self.__class__.__name__}(device_name={self.devices})'

    def write(self, value):
        return {'set': value, 'path': list(self.devices[1:]), 'scope': self.devices[0], }


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
        return f'ScanDataclassProperty(device_name={self.devices}, spec.data_cls={self.spec.data_cls})'

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
        ValuesEnum = Enum(f'{base_name}Values', enum_items)

        return [
            (f'start_{base_name}', ValuesEnum, field(default=1)),
            (f'stop_{base_name}', ValuesEnum, field(default=len(self.spec.choices)))
        ]

    def iterate(self, fields: Any, base_name: str) -> Iterator[Any]:
        start = getattr(fields, f'start_{base_name}').value
        stop = getattr(fields, f'stop_{base_name}').value
        stop_delta = 0 if self.inclusive else -1
        return list(self.spec.choices.values())[start-1:stop+stop_delta]


class ScanAxis(ScanDegreeOfFreedom):
    values = None

    def __init__(self, device_name: Union[str, AccessRecorder], limits=None, values=None, is_property=False):
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
            return [(f'n_{base_name}', int, field(default=5)),
                    (f'start_{base_name}', float, field(default=0)),
                    (f'stop_{base_name}', float, field(default=10))]
        else:
            # TODO need to be careful here as the labels we present in the UI need to be massaged.
            ValuesEnum = Enum(f'{base_name}Values',
                              {k: i + 1 for i, (k, _) in enumerate(self.values.items())})

            return [
                (f'start_{base_name}', ValuesEnum, field(default=1)),
                (f'stop_{base_name}', ValuesEnum, field(default=len(self.values)))
            ]

    def write(self, value):
        return {'write': value, 'path': list(self.devices[1:]), 'scope': self.devices[0],
                'is_property': self.is_property}

    def iterate(self, fields, base_name) -> Iterator[Any]:
        if self.values is None:
            return np.linspace(getattr(fields, f'start_{base_name}'),
                               getattr(fields, f'stop_{base_name}'),
                               getattr(fields, f'n_{base_name}'), endpoint=True)
        else:
            start, stop = getattr(fields, f'start_{base_name}'), getattr(fields, f'stop_{base_name}')
            return list(self.values.values())[start:stop]

    def __repr__(self):
        return f'ScanAxis(device_name={self.devices}, limits={self.limits}, values={self.values})'


def scan(name=None, read=None, profiles=None, setup=None, teardown=None,
         preconditions=None, **axes: Union[str, ScanAxis, AccessRecorder]):
    if name is None:
        raise ValueError('You must provide a name for the scan.')

    if read is None:
        read = {}

    axes = {name: ax if isinstance(ax, ScanDegreeOfFreedom) else ScanAxis(ax) for name, ax in axes.items()}
    axes: Dict[str, ScanDegreeOfFreedom] = axes

    fields = {name: ax.to_fields(name) for name, ax in axes.items()}

    def sequence_scan(self, experiment, **kwargs):
        dependent = {read_name: tokenize_access_path(read_device)
                     for read_name, read_device in read.items()}
        experiment.collate(
            independent=[[axis.devices, name]
                         for name, axis in axes.items()],
            dependent=[[dependent[read_name], read_name]
                       for read_name in read.keys()],
        )

        ax_names = list(axes.keys())
        device_spaces = [axis.iterate(fields=self, base_name=name) for name, axis in axes.items()]

        if preconditions:
            yield [{'preconditions': preconditions}]

        if profiles:
            yield [_set_profile(k, v) for k, v in profiles.items()]

        if setup:
            yield from setup(experiment, **kwargs)

        for locations in itertools.product(*device_spaces):
            with experiment.point():
                experiment.comment(f'Moving {ax_names} to {locations}')
                yield [axes[ax_name].write(location) for ax_name, location in zip(ax_names, locations)]
                yield [
                    {'read': None, 'path': dependent[read_name][1:], 'scope': dependent[read_name][0],}
                    for read_name in read.keys()
                ]

        if teardown:
            yield from teardown(experiment, **kwargs)

    scan_cls = make_dataclass(
        name,
        itertools.chain(*fields.values()),
        namespace={
            'sequence': sequence_scan,
        },
    )

    return scan_cls