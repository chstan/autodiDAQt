from dataclasses import dataclass
import numpy as np

from daquiri import Daquiri, ManagedInstrument, Experiment
from daquiri.instrument.spec import MockDriver, axis
from daquiri.mock import MockMotionController
from daquiri.schema import ArrayType


class MockImageDetector(ManagedInstrument):
    driver_cls = MockDriver

    @axis(ArrayType([250, 250]))
    async def device(self):
        return self.driver.read()

    @device.mock_read
    async def device(self):
        return np.random.random((250, 250))


class MockSimpleDetector(ManagedInstrument):
    driver_cls = MockDriver

    @axis(float)
    async def device(self):
        return self.device.read()

    @device.mock_read
    async def device(self):
        return np.random.normal() + 5


@dataclass
class SimpleScan:
    n_steps: int = 10
    start: float = 0
    stop: float = 20

    def sequence(self, experiment, mc, ccd, power_meter, **kwargs):
        experiment.collate(
            independent=[[mc.stages[0], 'dx']],
            dependent=[
                [ccd.device, 'spectrum'],
                [power_meter.device, 'power'],
            ]
        )

        for loc in np.linspace(self.start, self.stop, self.n_steps):
            with experiment.point():
                motions = [mc.stages[0].write(loc)]
                daq = [
                    ccd.device.read(),
                    power_meter.device.read(),
                ]

                yield motions
                yield daq


class MyExperiment(Experiment):
    scan_methods = [SimpleScan,]


app = Daquiri(__name__, actors={
    'experiment': MyExperiment,
}, managed_instruments={
    'mc': MockMotionController,
    'ccd': MockImageDetector,
    'power_meter': MockSimpleDetector,
})

if __name__ == '__main__':
    app.start()
