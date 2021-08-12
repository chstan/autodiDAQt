import numpy as np
from autodidaqt_common.schema import ArrayType

from autodidaqt.instrument.managed_instrument import ManagedInstrument
from autodidaqt.instrument.spec import AxisListSpecification, AxisSpecification, MockDriver

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
        float, where=["device"], mock=dict(read=lambda: float(np.random.normal() + 5))
    )


class MockImageDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        ArrayType([250, 250], float),
        where=["device"],
        mock=dict(read=lambda: np.random.random((250, 250))),
    )
