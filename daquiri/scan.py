from dataclasses import make_dataclass, field
from typing import Dict

import numpy as np
import itertools

__all__ = ('ScanAxis', 'scan')


def unwrap(value):
    try:
        return int(value)
    except ValueError:
        return value

def str_device_to_list(device_name):
    return [unwrap(x) for x in device_name.replace('[', '.').replace(']', '.').split('.') if x]

class ScanAxis:
    def __init__(self, device_name, limits=None):
        self.devices = str_device_to_list(device_name)
        self.limits = limits
        self.name = device_name

    def __repr__(self):
        return f'ScanAxis(device_name={self.devices}, limits={self.limits})'

    def __mul__(self, other):
        multiplied = ScanAxis('')
        multiplied.devices = self.devices + other.devices
        multiplied.limits = self.limits + other.limits
        return multiplied

def scan(name=None, read=None, **axes: Dict[str, ScanAxis]):
    if name is None:
        raise ValueError('You must provide a name for the scan.')

    if read is None:
        read = {}

    fields = {ax_name: [(f'n_{ax_name}', int, field(default=5)),
                        (f'start_{ax_name}', float, field(default=0)),
                        (f'stop_{ax_name}', float, field(default=10))]
              for ax_name, axis in axes.items()}

    def sequence_scan(self, experiment, **_):
        dependent = {read_name: str_device_to_list(read_device)
                     for read_name, read_device in read.items()}

        experiment.collate(
            independent=[[axis.devices, name]
                         for name, axis in axes.items()],
            dependent=[[dependent[read_name], read_name]
                       for read_name in read.keys()],
        )

        ax_names = list(axes.keys())
        device_spaces = [
            np.linspace(getattr(self, f'start_{ax_name}'),
                        getattr(self, f'stop_{ax_name}'),
                        getattr(self, f'n_{ax_name}'), endpoint=True)
            for ax_name in ax_names
        ]

        for locations in itertools.product(*device_spaces):
            with experiment.point():
                experiment.comment(f'Moving {ax_names} to {locations}')
                yield [
                    {'write': location, 'path': axes[ax_name].devices[1:], 'scope': axes[ax_name].devices[0]}
                    for ax_name, location in zip(ax_names, locations)
                ]
                yield [
                    {'read': None, 'path': dependent[read_name][1:], 'scope': dependent[read_name][0],}
                    for read_name in read.keys()
                ]

    scan_cls = make_dataclass(
        name,
        itertools.chain(*fields.values()),
        namespace={
            'sequence': sequence_scan,
        },
    )

    return scan_cls