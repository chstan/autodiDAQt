import numpy as np

from daquiri.instrument.spec import AxisListSpecification, AxisSpecification, MockDriver
from daquiri.instrument.managed_instrument import ManagedInstrument

__all__ = ('MockMotionController', 'MockScalarDetector')


class MockMotionController(ManagedInstrument):
    driver_cls = MockDriver

    stages = AxisListSpecification(
        float,
        where=lambda i: ['axis', i],
        read='position',
        write='move',

        # create three mocked axes
        mock=dict(n=3),
    )


class MockScalarDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        float, where=['device'],
        mock=dict(read=lambda: np.random.normal() + 5)
    )
