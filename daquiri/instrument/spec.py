from inspect import Parameter

import numpy as np

from typing import Union, List, Dict, Tuple, Any, Optional, Callable, Type

from daquiri.instrument.method import Method, TestMethod
from daquiri.instrument.property import ChoiceProperty, Property, TestProperty, SimpleProperty
from daquiri.instrument.axis import TestAxis, ProxiedAxis, LogicalAxis, Axis
from daquiri.utils import tokenize_access_path

__all__ = ('MockDriver',

           # axes
           'Specification',
           'AxisListSpecification',
           'AxisSpecification',
           'LogicalAxisSpecification',

           # properties
           'PropertySpecification',
           'ChoicePropertySpecification',

           # methods
           'parameter',
           'MethodSpecification')


class MockDriver:
    """
    A fake driver
    """


class Specification:
    where = None  # path to the appropriate location on the instrument driver
    axis_cls = None
    test_axis_cls = TestAxis

    @property
    def where_list(self) -> Tuple[Union[str, int]]:
        return tokenize_access_path(self.where or [])

    def realize(self, key_name, driver_instance, instrument) -> Union[Axis, List[Axis], Dict[str, Axis]]:
        axis_cls = self.axis_cls
        if isinstance(driver_instance, MockDriver):
            axis_cls = self.test_axis_cls

        return axis_cls(key_name, driver_instance, instrument)

    def to_scan_axis(self, over, path, *args, **kwargs):
        raise NotImplementedError()


class AxisListSpecification(Specification):
    """
    Represents the specification for a list of axes, such as is present on
    a motion controller.
    """
    def __init__(self, schema, where=None, read=None, write=None, mock=None,
                 settle=None):
        if mock is None:
            mock = {'n': 5}

        self.mock = mock
        self.schema = schema
        self.name = None
        self.read = read
        self.write = write
        self.settle = settle

        self.where = where

    def __repr__(self):
        return ('AxisListSpecification('
                f'name={self.name!r},'
                f'schema={self.schema!r},'
                f'where={self.where("{ index }")!r},'
                ')')

    def realize(self, key_name, driver_instance, instrument) -> List[Axis]:
        where_root = tokenize_access_path(self.where(np.nan))
        where_root = where_root[:where_root.index(np.nan)]

        if isinstance(driver_instance, MockDriver):
            axis_cls = TestAxis
            n = self.mock['n']
        else:
            axis_cls = ProxiedAxis
            g = driver_instance
            for elem in where_root:
                if isinstance(elem, str):
                    g = getattr(g, elem)
                else:
                    g = g[elem]

            n = len(g)

        return [
            axis_cls(name=key_name, schema=self.schema, where=self.where(i), driver=driver_instance,
                     settle=self.settle, read=self.read, write=self.write)
            for i in range(n)
        ]

    def to_scan_axis(self, over, path, rest, *args, **kwargs):
        from daquiri.scan import ScanAxis
        return ScanAxis([over] + path + rest, *args, **kwargs)


class AxisSpecification(Specification):
    """
    Represents a single axis or detector.
    """
    def __init__(self, schema, where=None, range=None, validator=None, read=None,
                 write=None, settle=None, mock=None):
        self.name = None
        self.schema = schema
        self.range = range
        self.validator = validator
        self.is_axis = False if write is None else True
        self.read = read
        self.write = write
        self.where = where
        self.settle = settle
        self.mock = mock or {}

    def __repr__(self):
        return ('AxisSpecification('
                f'name={self.name!r},'
                f'where={self.where!r},'
                f'schema={self.schema!r},'
                f'range={self.range!r},'
                f'validator={self.validator!r},'
                f'is_axis={self.is_axis!r},'
                f'read={self.read},'
                f'write={self.write}',
                f'settle={self.settle}'
                ')')

    def realize(self, key_name, driver_instance, instrument) -> Axis:
        if isinstance(driver_instance, MockDriver):
            axis_cls = TestAxis
            init_kwargs = {'mock': self.mock}
        else:
            axis_cls = ProxiedAxis
            init_kwargs = {}

        return axis_cls(name=key_name, schema=self.schema, where=self.where, driver=driver_instance,
                        read=self.read, write=self.write, settle=self.settle, **init_kwargs)

    def to_scan_axis(self, over, path, *args, **kwargs):
        from daquiri.scan import ScanAxis
        return ScanAxis([over] + path, *args, **kwargs)


class LogicalAxisSpecification(Specification):
    """
    TODO, maybe better to allow null initial_state if we can artfully
    build it or load it from somewhere

    TODO fix schema here
    """
    def __init__(self, forward_transforms, inverse_transforms, initial_coords, state=None):
        self.forward_transforms = forward_transforms
        self.inverse_transforms = inverse_transforms
        self.initial_coords = initial_coords
        self.state = state

    def realize(self, key_name, driver_instance, instrument) -> Axis:
        physical_axes = {}

        for physical_name in self.forward_transforms.keys():
            physical_axes[physical_name] = instrument.lookup_axis(physical_name)

        return LogicalAxis(
            name=key_name, schema=None,
            physical_axes=physical_axes,
            forward_transforms=self.forward_transforms,
            inverse_transforms=self.inverse_transforms,
            logical_state=self.initial_coords,
            internal_state=self.state
        )

    def to_scan_axis(self, over, path, rest, *args, **kwargs):
        from daquiri.scan import ScanAxis
        return ScanAxis([over] + path + rest, *args, **kwargs)


class PropertySpecification:
    """
    sensitivity = ChoicePropertySpecification(choices=DSP7265.SENSITIVITIES, labels=lambda x: f'{x} V')
    time_constant = ChoicePropertySpecification(choices=DSP7265.TIME_CONSTANTS, labels=lambda x: f'{x} s')
    """
    where: Tuple[Union[str, float]]
    axis_cls: type = None
    test_axis_cls: type = TestProperty

    def __init__(self, where):
        self.where = tokenize_access_path(where)

    def realize(self, key_name, driver_instance, instrument) -> Union[Axis, List[Axis], Dict[str, Axis]]:
        axis_cls = self.axis_cls
        if isinstance(driver_instance, MockDriver):
            axis_cls = self.test_axis_cls

        return axis_cls(key_name, driver_instance, instrument)

    def to_scan_axis(self, over, path, *args, **kwargs):
        raise NotImplementedError()


class ChoicePropertySpecification(PropertySpecification):
    choices = Dict[str, Any]  # unique choices -> hardware values
    labels = Dict[str, str]  # unique choices -> display values

    def __init__(self, where, choices, labels: Optional[Union[Dict[str, str], Callable[[Any], str]]] = None):
        if isinstance(choices, list):
            self.choices = dict(zip(range(len(choices)), choices))
        else:
            self.choices = choices

        if labels is None:
            self.labels = dict(zip(self.choices.keys(), self.choices.keys()))
        elif callable(labels):
            self.labels = {k: labels(v, k) for k, v in self.choices.items()}
        else:
            self.labels = labels

        super().__init__(where)

    def realize(self, key_name, driver_instance, instrument) -> Property:
        return ChoiceProperty(name=key_name, where=self.where, driver=driver_instance,
                              choices=self.choices, labels=self.labels)

    def to_scan_axis(self, over, path, *args, **kwargs):
        from daquiri.scan import ScanChoiceProperty
        return ScanChoiceProperty([over] + path, self)


class DataclassPropertySpecification(PropertySpecification):
    """
    Allows setting Dataclass instances against a driver.
    """
    data_cls: type
    default_instance: Any

    axis_cls = SimpleProperty

    def __init__(self, where, data_cls: type, default_instance=None):
        super().__init__(where)
        self.data_cls = data_cls
        self.default_instance = default_instance

    def to_scan_axis(self, over, path, *args, **kwargs):
        from daquiri.scan import ScanDataclassProperty
        return ScanDataclassProperty([over] + path, self)


def parameter(name, **kwargs):
    return Parameter(name, kind=Parameter.POSITIONAL_OR_KEYWORD, **kwargs)


class MethodSpecification:
    where: Tuple[Union[str, float]]
    parameters: Optional[Dict[str, Parameter]] = None
    return_annotation: Optional[Type] = None

    def __init__(self, where, parameters=None, return_annotation=None):
        self.where = tokenize_access_path(where)
        self.parameters = parameters
        self.return_annotation = return_annotation

    def realize(self, key_name, driver_instance, instrument) -> Method:
        method_cls = TestMethod if isinstance(driver_instance, MockDriver) else Method
        return method_cls(name=key_name, where=self.where, driver=driver_instance,
                          parameters=self.parameters, return_annotation=self.return_annotation)
