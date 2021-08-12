from dataclasses import dataclass

import numpy as np

from autodidaqt.experiment import Experiment
from autodidaqt.mock import MockMotionController, MockScalarDetector

__all__ = ["BasicScan", "UninvertedScan"]


@dataclass
class BasicScan:
    @property
    def n_points(self) -> int:
        return 10

    def sequence(self, experiment, mc, power_meter):
        experiment.collate(
            independent=[[mc.stages[0], "dx"]],
            dependent=[[power_meter.device, "power"]],
        )

        for i in range(10):
            with experiment.point():
                yield [mc.stages[0].write(i)]
                yield [power_meter.device.read()]


@dataclass
class UninvertedScan:
    n_steps: int = 5
    start: float = 0
    stop: float = 20

    @property
    def n_points(self):
        return self.n_steps

    async def sequence(
        self,
        experiment: Experiment,
        mc: MockMotionController,
        power_meter: MockScalarDetector,
    ):
        experiment.collate(
            independent=[["mc.stages[0]", "dx"]],
            dependent=[["power_meter.device", "power"]],
        )

        for i, x in enumerate(np.linspace(self.start, self.stop, self.n_steps)):
            with experiment.point():
                experiment.comment(f"Starting point at step {i}")
                await mc.stages[0].write(x)
                read_value = await power_meter.device.read()
                yield {"mc.stages[0]": x, "power_meter.device": read_value}
