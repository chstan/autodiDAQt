from dataclasses import dataclass

import numpy as np

from daquiri import Daquiri, Experiment
from daquiri.instrument import AxisSpecification, ManagedInstrument
from daquiri.instrument.spec import ChoicePropertySpecification
from daquiri.mock import MockMotionController
from daquiri.scan import scan
from pymeasure.instruments.signalrecovery.dsp7265 import DSP7265


class ManagedDSP7265(ManagedInstrument):
    # Minimal, for more details look at scanning_properties_and_profiles
    driver_cls = DSP7265

    x = AxisSpecification(float)
    time_constant = ChoicePropertySpecification(
        where=["time_constant"],
        choices=DSP7265.TIME_CONSTANTS,
        labels=lambda _, k: f"{k} s",
    )

    profiles = {
        "Fast": {"time_constant": DSP7265.TIME_CONSTANTS[9]},
        "Slow": {"time_constant": DSP7265.TIME_CONSTANTS[13]},
    }

    proxy_methods = [
        "auto_sensitivity",
        "auto_phase",
    ]


@dataclass
class CustomScan:
    """
    A basic scan, but set some instrument state and use a profile before starting. Set the profile back
    later.
    """

    start_x: float = 0
    stop_x: float = 10
    n_x: int = 10

    def sequence(self, experiment, lockin, mc, **kwargs):
        yield lockin.set_profile("Fast")
        yield lockin.auto_phase()

        for step_x in np.linspace(self.start_x, self.stop_x, self.n_x):
            with experiment.point():
                yield [
                    mc.stages[0].write(step_x),
                ]
                yield [
                    lockin.x.read(),
                ]

        yield lockin.set_profile("Slow")


def setup_lockin(experiment, lockin=None, **kwargs):
    yield lockin.set_profile("Fast")
    yield lockin.auto_phase()


def teardown_lockin(experiment, lockin=None, **kwargs):
    yield lockin.set_profile("Slow")


class MyExperiment(Experiment):
    dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])
    dtime_constant = ManagedDSP7265.scan("lockin").time_constant()

    read_power = {
        "power": "lockin.x",
    }

    scan_methods = [
        # Two different ways of achieving a one axis scan with some instrument setup and teardown
        scan(
            x=dx,
            name="dx Scan",
            read=read_power,
            setup=setup_lockin,
            teardown=teardown_lockin,
        ),
        CustomScan,
    ]


app = Daquiri(
    __name__,
    {},
    {"experiment": MyExperiment},
    {"mc": MockMotionController, "lockin": ManagedDSP7265},
)

if __name__ == "__main__":
    app.start()
