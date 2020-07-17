import itertools
from dataclasses import dataclass
from enum import Enum

import numpy as np

from daquiri import Daquiri
from daquiri.experiment import Experiment
from daquiri.instrument import ManagedInstrument
from daquiri.instrument.spec import AxisSpecification, MockDriver
from daquiri.mock import MockMotionController
from daquiri.schema import ArrayType


class MockImageDetector(ManagedInstrument):
    """
    Generate some fake instruments, here we make a mocked (fake) 400px by 400px camera
    and a mocked scalar detector (in this case a "power meter").

    Various utility mocks are available in daquiri.mock as well.

    By mocking, we can coarsely test our DAQ programs even if we have none or only some of the physical hardware.
    """

    driver_cls = (
        MockDriver  # <- specifies that we should always be mocking this instrument
    )
    device = AxisSpecification(
        ArrayType([250, 250], float),
        where=["device"],
        mock=dict(
            read=lambda: np.random.random((250, 250))
        ),  # <- specifies how we want to fake reads
    )


class MockSimpleDetector(ManagedInstrument):
    driver_cls = MockDriver
    device = AxisSpecification(
        float, where=["device"], mock=dict(read=lambda: np.random.normal() + 5)
    )


"""
Next we set up scan modes, here are two common types of scans,
a single degree of freedom scan and a two degree of freedom scan
we also illustrate that you can control the internal function and
sequencing, such as by measuring while motors are moving or not.

By using `with experiment.point:` we demarcate which DAQ and motion
sequences are grouped together. These points are collected together
due to the optional invokation of `experiment.collate`.
"""


class SimpleScanMode(Enum):
    MOVE_WHILE_MEASURING = 0
    MOVE_THEN_MEASURE = 1


@dataclass
class SimpleScan:
    """
    A scan mode consists of a generator 'sequence', which computes
    the DAQ steps for the experiment. You can perform whatever logic you like
    in here, even adjusting the experimental course depending on the measurement
    so far.
    """

    n_steps: int = 10
    start: float = 0
    stop: float = 20
    mode: SimpleScanMode = SimpleScanMode.MOVE_THEN_MEASURE

    def sequence(self, experiment, mc, ccd, power_meter, **kwargs):
        """
        An example measurement sequence, here we scan over a stage,
        at each step, we take data from a Power Meter (a DAQ device reading a scalar) and
        a CCD (a DAQ device that reads an image).

        Using experiment.collate, we can name various DAQ devices in the output
        and form an array-like output by grouping depenndent variables to independent
        variables.

        At the end of the run here, we will produce an xr.Dataset with the structure

        power: dims=['dx'], shape=[len(dx')]
        spectrum: dims=['dx', 'spectrum-dim_0', 'spectrum-dim_1'], shape=[len('dx'), 100, 100]

        Additionally, we record the full metadata and DAQ sequence, always.
        """
        experiment.collate(
            independent=[[mc.stages[0], "dx"]],
            dependent=[[power_meter.device, "power"], [ccd.device, "spectrum"]],
        )

        for step_i in range(self.n_steps):
            with experiment.point():
                experiment.comment(f"Starting point at step {step_i}")

                # move the stages
                next_location = (
                    self.start + (self.stop - self.start) * step_i / self.n_steps
                )
                motions = [mc.stages[0].write(next_location)]
                daq = [
                    ccd.device.read(),
                    power_meter.device.read(),
                ]

                if self.mode == SimpleScanMode.MOVE_THEN_MEASURE:
                    yield motions
                    yield daq
                else:
                    yield list(itertools.chain(motions, daq))


@dataclass
class TwoAxisScan:
    """Another scan mode we implement: here a two axis scan."""

    n_steps_x: int = 10
    n_steps_y: int = 3
    start_x: float = 0
    start_y: float = 0
    stop_x: float = 5
    stop_y: float = 5

    @staticmethod
    def interp(start, stop, n_steps, current_step):
        return start + (stop - start) * current_step / n_steps

    def sequence(self, experiment, mc, power_meter, **kwargs):
        experiment.collate(
            independent=[[mc.stages[0], "dx"], [mc.stages[1], "dy"]],
            dependent=[[power_meter.device, "power"]],
        )

        for step_x in range(self.n_steps_x):
            next_x = self.interp(self.start_x, self.stop_x, self.n_steps_x, step_x)

            for step_y in range(self.n_steps_y):
                next_y = self.interp(self.start_y, self.stop_y, self.n_steps_y, step_y)

                with experiment.point():
                    yield [mc.stages[0].write(next_x), mc.stages[1].write(next_y)]
                    yield [power_meter.device.read()]


class MyExperiment(Experiment):
    scan_methods = [SimpleScan, TwoAxisScan]


app = Daquiri(
    __name__,
    actors={"experiment": MyExperiment,},
    managed_instruments={
        "mc": MockMotionController,
        "ccd": MockImageDetector,
        "power_meter": MockSimpleDetector,
    },
)

if __name__ == "__main__":
    app.start()
