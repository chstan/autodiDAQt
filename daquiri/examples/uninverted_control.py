from dataclasses import dataclass
import numpy as np

from daquiri import Daquiri
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.experiment import Experiment

@dataclass
class SimpleScan:
    n_steps: int = 100
    start: float = 0
    stop: float = 20

    async def sequence(self, experiment: Experiment, mc: MockMotionController,
                       power_meter: MockScalarDetector):
        experiment.collate(
            independent=[('mc.stages[0]', 'dx',)],
            dependent=[('power_meter.device', 'power',),]
        )

        for i, x in enumerate(np.linspace(self.start, self.stop, self.n_steps)):
            with experiment.point():
                experiment.comment(f'Starting point at step {i}')
                moved_to = await mc.stages[0].write(x)
                read_value = await power_meter.device.read()
                yield {'mc.stages[0]': moved_to,
                       'power_meter.device': read_value}


class MyExperiment(Experiment):
    scan_methods = [SimpleScan,]


app = Daquiri(__name__, actors={
    'experiment': MyExperiment,
}, managed_instruments={
    'mc': MockMotionController,
    'power_meter': MockScalarDetector,
})

if __name__ == '__main__':
    app.start()
