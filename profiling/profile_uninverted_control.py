import numpy as np
import asyncio
from dataclasses import dataclass

from daquiri import Daquiri
from daquiri.experiment import AutoExperiment
from daquiri.mock import MockMotionController, MockScalarDetector


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

    async def sequence(self, experiment, mc, power_meter, **kwargs):
        experiment.collate(
            independent=[["mc.stages[0]", "dx"], ["mc.stages[1]", "dy"]],
            dependent=[["power_meter.device", "power"]],
        )

        for x in np.linspace(self.start_x, self.stop_x, self.n_steps_x):
            for y in np.linspace(self.start_y, self.stop_y, self.n_steps_y):
                with experiment.point():
                    await asyncio.gather(
                        mc.stages[0].write(x),
                        mc.stages[1].write(y),
                    )
                    value = await power_meter.device.read()
                    yield {
                        "mc.stages[0]": x,
                        "mc.stages[1]": y,
                        "power_meter.device": value,
                    }


class MyExperiment(AutoExperiment):
    scan_methods = [TwoAxisScan]
    run_with = [TwoAxisScan(n_steps_x=100, n_steps_y=50)] * 5

    exit_after_finish = True
    discard_data = True


app = Daquiri(
    __name__,
    {},
    {"experiment": MyExperiment},
    {
        "mc": MockMotionController,
        "power_meter": MockScalarDetector,
    },
)

if __name__ == "__main__":
    app.start()
