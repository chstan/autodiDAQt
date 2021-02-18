from dataclasses import dataclass

import numpy as np

from daquiri import Daquiri
from daquiri.experiment import Experiment
from daquiri.mock import MockMotionController, MockScalarDetector


@dataclass
class SimpleScan:
    n_steps: int = 100
    start: float = 0
    stop: float = 20

    @property
    def n_points(self):
        return self.n_steps

    def sequence(self, experiment, mc, power_meter, **kwargs):
        experiment.collate(
            independent=[[mc.stages[0], "dx"]],
            dependent=[[power_meter.device, "power"]],
        )

        for i, x in enumerate(np.linspace(self.start, self.stop, self.n_steps)):
            with experiment.point():
                experiment.comment(f"Starting point at step {i}")
                yield [mc.stages[0].write(x)]
                yield [power_meter.device.read()]


@dataclass
class TwoAxisScan:
    n_steps_x: int = 10
    n_steps_y: int = 3
    start_x: float = 0
    start_y: float = 0
    stop_x: float = 5
    stop_y: float = 5

    @staticmethod
    def interp(start, stop, n_steps, current_step):
        return start + (stop - start) * current_step / n_steps

    @property
    def n_points(self):
        return self.n_steps_x * self.n_steps_y

    def sequence(self, experiment, mc, power_meter, **kwargs):
        experiment.collate(
            independent=[[mc.stages[0], "dx"], [mc.stages[1], "dy"]],
            dependent=[[power_meter.device, "power"]],
        )

        for x in np.linspace(self.start_x, self.stop_x, self.n_steps_x):
            for y in np.linspace(self.start_y, self.stop_y, self.n_steps_y):
                with experiment.point():
                    yield [mc.stages[0].write(x), mc.stages[1].write(y)]
                    yield [power_meter.device.read()]


class MyExperiment(Experiment):
    scan_methods = [SimpleScan, TwoAxisScan]


app = Daquiri(
    __name__,
    actors=dict(experiment=MyExperiment),
    managed_instruments=dict(
        mc=MockMotionController,
        power_meter=MockScalarDetector,
    ),
)

if __name__ == "__main__":
    app.start()
