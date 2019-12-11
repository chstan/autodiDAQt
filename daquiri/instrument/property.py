from dataclasses import dataclass, field
from typing import Optional, List, Any, Union, Callable, Dict
import inspect

import numpy as np

from daquiri.instrument.axis import ProxiedAxis, LogicalAxis, Detector, TestAxis
from daquiri.utils import tokenize_access_path

__all__ = ('Property', 'ChoiceProperty', 'LogicalAxisSpecification')

def _unwrapped_where(where):
    as_list = where.split('.') if isinstance(where, str) else where
    return as_list


@dataclass
class Property:
    where: Optional[str] = None

    @property
    def where_list(self) -> List[Union[str, int]]:
        return _unwrapped_where(self.where or [])

@dataclass
class ChoiceProperty(Property):
    choices: List[Any] = field(default_factory=list)
    labels: Optional[Union[Callable, List[str]]] = None


class Specification:
    where = None

    @property
    def where_list(self) -> List[Union[str, int]]:
        return _unwrapped_where(self.where or [])

    def realize(self, key_name, driver_instance, instrument) -> Union[Detector, List[Detector], Dict[str, Detector]]:
        print(key_name, driver_instance)
        raise NotImplementedError()


class AxisListSpecification(Specification):
    """
    Represents the specification for a list of axes, such as is present on
    a motion controller.
    """
    def __init__(self, schema, where=None, read=None, write=None, mock=None):
        if mock is None:
            mock = {'n': 5}

        self.mock = mock
        self.schema = schema
        self.name = None
        self.read = read
        self.write = write

        self.where = where

    def __repr__(self):
        return ('AxisListSpecification('
                f'name={self.name!r},'
                f'schema={self.schema!r},'
                f'where={self.where("{ index }")!r},'
                ')')

    def realize(self, key_name, driver_instance, instrument) -> List[Detector]:
        from daquiri.mock import MockDriver

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
                        read=self.read, write=self.write)
            for i in range(n)
        ]


class AxisSpecification(Specification):
    """
    Represents a single axis or detector.
    """
    def __init__(self, schema, where=None, range=None, validator=None, axis=True, read=None, write=None, mock=None):
        self.name = None
        self.schema = schema
        self.range = range
        self.validator = validator
        self.is_axis = axis
        self.read = read
        self.write = write
        self.where = where
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
                f'write={self.write}'
                ')')

    def realize(self, key_name, driver_instance, instrument) -> Detector:
        from daquiri.mock import MockDriver

        if isinstance(driver_instance, MockDriver):
            axis_cls = TestAxis
            init_kwargs = {'mock': self.mock}
        else:
            axis_cls = ProxiedAxis
            init_kwargs = {}

        return axis_cls(name=key_name, schema=self.schema, where=self.where, driver=driver_instance,
                        read=self.read, write=self.write, **init_kwargs)


class LogicalAxisSpecification(Specification):
    """
    TODO, maybe better to allow null initial_state if we can artfully
    build it or load it from somewhere

    TODO fix schema here
    """
    def __init__(self, forward_transforms, initial_state):
        self.forward_transforms = forward_transforms
        self.initial_state = initial_state

    def realize(self, key_name, driver_instance, instrument) -> Detector:
        physical_axes = {}

        for physical_name in self.forward_transforms.keys():
            physical_axes[physical_name] = instrument.lookup_axis(physical_name)

        argspec = inspect.getfullargspec(list(self.forward_transforms.values())[0])
        coordinate_names = argspec.args[1:]
        coordinate_indices = [argspec.args.index(arg) - 1 for arg in coordinate_names]

        return LogicalAxis(
            name=key_name, schema=None,
            coordinate_names=coordinate_names,
            coordinate_indices=coordinate_indices,
            physical_axes=physical_axes,
            forward_transforms=self.forward_transforms, logical_state=self.initial_state
        )


class DetectorSpecification(AxisSpecification):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, axis=True)


@dataclass
class PolledWrite:
    write: Optional[str] = None
    poll: Optional[str] = None


@dataclass
class PolledRead:
    read: str
    poll: Optional[str] = None