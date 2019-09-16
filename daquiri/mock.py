import numpy as np

from daquiri.instrument.spec import (
    ManagedInstrument, Generate, AxisListSpecification, AxisSpecification)

__all__ = ('MockMotionController', 'MockDetector', 'MockScalarDetector')

class MockDriver:
    """
    A fake driver
    """

class MockMotionController(ManagedInstrument):
    driver_cls = MockDriver
    test_cls = Generate({'stages': {'length': 3}})

    stages = AxisListSpecification(
        lambda index: AxisSpecification(
            float, where=['axis', index],
            read='position',
            write='move'),
        where='axis',
    )


class MockDetector(ManagedInstrument):
    driver_cls = MockDriver
    test_cls = Generate({'device': {'mock_read': 'generate'}})

    device = AxisSpecification(float, where=['device'])

    def generate(self):
        return 3.14159


class MockScalarDetector(MockDetector):
    def generate(self):
        return np.random.normal() + 5
