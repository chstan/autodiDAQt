from dataclasses import make_dataclass, field
from enum import Enum

from typing import Optional, Union, Iterator, Any

import numpy as np
import itertools

from daquiri.utils import AccessRecorder, InstrumentScanAccessRecorder

__all__ = ('ScanAxis', 'scan')


def _set_profile(scope, profile_name):
    return {
        'call': ([profile_name], {}),
        'path': ['set_profile'],
        'scope': scope,
    }


def unwrap(value):
    try:
        return int(value)
    except ValueError:
        return value


def str_device_to_list(device_name):
    return [unwrap(x) for x in device_name.replace('[', '.').replace(']', '.').split('.') if x]


class ScanAxis:
    values = None
    def __init__(self, device_name: Union[str, AccessRecorder], limits=None, values=None, is_property=False):
        if isinstance(device_name, InstrumentScanAccessRecorder):
            self.devices = device_name.full_path_()
            self.limits = device_name.limits_()
            self.values = device_name.values_()
            self.name = device_name.name_()
            self.is_property = device_name.is_property_()
        else:
            self.devices = str_device_to_list(device_name)
            self.name = device_name
            self.is_property = is_property

        if limits is not None:
            self.limits = limits
        if values is not None:
            self.values = values

    def to_fields(self, base_name):
        if self.values is None:
            return [(f'n_{base_name}', int, field(default=5)),
                    (f'start_{base_name}', float, field(default=0)),
                    (f'stop_{base_name}', float, field(default=10))]
        else:
            # TODO need to be careful here as the labels we present in the UI need to be massaged.
            ValuesEnum = Enum(f'{base_name}Values', {k: i + 1 for i, (k, _) in enumerate(self.values.items())})

            return [
                (f'start_{base_name}', ValuesEnum, field(default=1)),
                (f'stop_{base_name}', ValuesEnum, field(default=len(self.values)))
            ]

    def write(self, value):
        return {'write': value, 'path': list(self.devices[1:]), 'scope': self.devices[0], 'is_property': self.is_property}

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

    axes = {name: ax if isinstance(ax, ScanAxis) else ScanAxis(ax) for name, ax in axes.items()}
    fields = {name: ax.to_fields(name) for name, ax in axes.items()}

    def sequence_scan(self, experiment, **kwargs):
        dependent = {read_name: str_device_to_list(read_device)
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