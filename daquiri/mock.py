import numpy as np

from daquiri.instrument.managed_instrument import ManagedInstrument
from daquiri.instrument.spec import (AxisListSpecification, AxisSpecification,
                                     MockDriver)
from daquiri.schema import ArrayType

__all__ = (
    "MockMotionController",
    "MockScalarDetector",
    "MockImageDetector",
)


class MockMotionController(ManagedInstrument):
    driver_cls = MockDriver

    stages = AxisListSpecification(
        float,
        where=lambda i: ["axis", i],
        read="position",
        write="move",
        # create three mocked axes
        mock=dict(n=3, readonly=False),
    )


class MockScalarDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        float, where=["device"], mock=dict(read=lambda: np.random.normal() + 5),
    )


class MockImageDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        ArrayType([250, 250], float),
        where=["device"],
        mock=dict(read=lambda: np.random.random((250, 250))),
    )
