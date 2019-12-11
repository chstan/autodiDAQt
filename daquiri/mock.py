import numpy as np

from daquiri.instrument.spec import ManagedInstrument
from daquiri.instrument.property import AxisListSpecification, AxisSpecification

__all__ = ('MockMotionController', 'MockScalarDetector')


class MockDriver:
    """
    A fake driver
    """


class MockMotionController(ManagedInstrument):
    driver_cls = MockDriver

    stages = AxisListSpecification(
        float,
        where=lambda i: ['axis', i],
        read='position',
        write='move',

        mock=dict(n=3),
    )


class MockScalarDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        float, where=['device'],
        mock=dict(read=lambda: np.random.normal() + 5)
    )

    async def run(self):
        while True:
            import asyncio
            await asyncio.sleep(0.1)
            await self.device.read()