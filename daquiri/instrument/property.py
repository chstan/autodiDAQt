from dataclasses import dataclass, field
from typing import Optional, List, Any, Union, Callable

__all__ = ('Property', 'ChoiceProperty',)

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


class AxisListSpecification(Specification):
    """
    Represents the specification for a list of axes, such as is present on
    a motion controller.
    """
    def __init__(self, internal_specification, where=None):
        self.internal_specification = internal_specification
        self.name = None
        self.where = where

    def __repr__(self):
        return ('AxisListSpecification('
                f'name={self.name!r},'
                f'where={self.where!r},'
                f'internal_specification={self.internal_specification!r},'
                ')')


class AxisSpecification(Specification):
    """
    Represents a single axis or detector.
    """
    def __init__(self, schema, where=None, range=None, validator=None, axis=True, read=None, write=None):
        self.name = None
        self.schema = schema
        self.range = range
        self.validator = validator
        self.is_axis = axis
        self.read = read
        self.write = write
        self.where = where

    def __repr__(self):
        return ('AxisSpecification('
                f'name={self.name!r},'
                f'where={self.where!r},'
                f'schema={self.schema!r},'
                f'range={self.range!r},'
                f'validator={self.validator!r},'
                f'is_axis={self.is_axis!r},'
                f'read={self.read}'
                f'write={self.write}'
                ')')


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