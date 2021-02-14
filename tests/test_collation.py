import pytest
import itertools
from collections import defaultdict
from dataclasses import dataclass
import datetime
import xarray as xr
import numpy as np
import random

from daquiri.experiment import Collation

@dataclass
class DAQHelper:
    step: int = 0
    point: int = 0

    def daq_point(self, data):
        return {
            "data": data,
            "time": datetime.datetime.now(),
            "step": self.step,
            "point": self.point,
        }

def test_collation_end_to_end():
    coll = Collation(
        independent={("x",): "X", ("y",): "Y"},
        dependent={("z",): "Z"},
    )

    # generate some data
    daq_values = defaultdict(list)
    helper = DAQHelper()

    n_per_axis = 6
    xs = np.linspace(0, 10, n_per_axis)
    ys = np.linspace(10, 20, n_per_axis)
    for x, y in itertools.product(xs, ys):
        daq_values[("x",)].append(helper.daq_point(x))
        daq_values[("y",)].append(helper.daq_point(y))
        daq_values[("z",)].append(helper.daq_point(helper.step % 9))

        coll.receive(("x",), x)
        coll.receive(("y",), y)

        helper.step += 1
        helper.point += 1

    zs = (np.arange(0, n_per_axis ** 2) % 9).tolist()
    group = Collation.iter_single_group(daq_values[("z",)])
    assert list(itertools.chain(*group)) == zs

    dset = coll.to_xarray(daq_values)
    assert set(dset.data_vars.keys()) == {"X-values", "Y-values", "Z"}
    assert set(dset["Z"].dims) == {"X", "Y",}
    assert dset["Z"].values.shape == (n_per_axis, n_per_axis,)
    assert dset["Z"].values.astype(int).ravel().tolist() == zs 

def test_collation_array_values():
    """
    We also allow producing an array as a single scalar value, for instance
    when we are dealing with a camera which produces an image as a single measurement
    """    

    coll = Collation(
        independent={("x",): "X"},
        dependent={("z",): "Z"},
    )

    daq_values = defaultdict(list)
    helper = DAQHelper()
    for x in range(10):
        daq_values[("x",)].append(helper.daq_point(x))
        daq_values[("z",)].append(helper.daq_point(np.random.randn(5,5)))
        coll.receive(("x",), x)
        helper.step += 1
        helper.point += 1

    arr = coll.to_xarray(daq_values)
    assert set(arr.data_vars.keys()) == {"X-values", "Z"}
    assert arr.Z.shape == (10, 5, 5)

def test_collation_axes():
    coll = Collation(
        independent={("x",): "X", ("y",): "Y"},
        dependent={("z",): "Z"},
    )
    # send the xs twice
    xs = np.linspace(-1, 1, 101)
    for x in xs:
        coll.receive(("x",), x)
    for x in xs:
        coll.receive(("x",), x)

    # shuffle the ys
    ys = np.linspace(-5, 20, 101).tolist()
    random.shuffle(ys)
    for y in ys:
        coll.receive(("y",), y)
    
    # check that we build axes correctly
    coords, dims = coll.internal_axes()
    assert dims == ["X", "Y"]
    assert coords["X"].tolist() == xs.tolist()
    assert coords["Y"].tolist() == sorted(ys)
