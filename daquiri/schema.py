from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ArrayType:
    """
    Indicates that an axis produces ndarrays

    If the shape is provided, then this will be the shape of the arrays produced.
    A `None` value here indicates that we don't know ahead of time how big they
    will be.
    
    The `dtype` member indicates the type of the array values
    """

    shape: Optional[List[int]] = None
    dtype: type = None

    @classmethod
    def of(cls, dtype):
        return ArrayType(None, dtype)


DEFAULT_VALUES = {
    int: 0,
    float: 0,
    str: '',
}