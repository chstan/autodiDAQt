from dataclasses import dataclass, field
from typing import Optional, List, Any, Union, Callable

__all__ = ('Property', 'ChoiceProperty',)


@dataclass
class Property:
    where: Optional[str] = None


@dataclass
class ChoiceProperty(Property):
    choices: List[Any] = field(default_factory=list)
    labels: Optional[Union[Callable, List[str]]] = None