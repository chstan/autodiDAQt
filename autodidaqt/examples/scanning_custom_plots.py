import itertools
from dataclasses import dataclass

import numpy as np

from autodidaqt import AutodiDAQt, Experiment
from autodidaqt.mock import MockMotionController, MockScalarDetector


@dataclass
class XScan:
    n_points_x: int = 20
    n_points_y: int = 20

    def sequence(self, experiment, mc, power_meter):
        experiment.plot(
            dependent="power_meter.device",
            independent=["mc.stages[0]"],
            name="Line Plot",
        )
        experiment.plot(
            dependent="power_meter.device",
            independent=["mc.stages[0]", "mc.stages[1]"],
            name="Power",
            size=lambda value: np.abs(value),
        )

        for x, y in itertools.product(range(self.n_points_x), (range(self.n_points_y))):
            with experiment.point():
                yield [mc.stages[0].write(x), mc.stages[1].write(y)]
                yield [power_meter.device.read()]


class MyExperiment(Experiment):
    scan_methods = [XScan]


app = AutodiDAQt(
    __name__,
    {},
    dict(experiment=MyExperiment),
    dict(mc=MockMotionController, power_meter=MockScalarDetector),
)

if __name__ == "__main__":
    app.start()
