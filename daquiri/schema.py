from dataclasses import dataclass
from typing import List, Optional

import numpy as np


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
    str: "",
}


def default_value_for_schema(schema):
    if isinstance(schema, ArrayType):
        if schema.shape is None:
            return None

        return np.zeros(dtype=schema.dtype or float, shape=schema.shape)

    return DEFAULT_VALUES[schema]
