from dataclasses import dataclass
import numpy as np

from pymeasure.instruments.signalrecovery.dsp7265 import DSP7265

from daquiri import Daquiri, Experiment
from daquiri.mock import MockMotionController
from daquiri.scan import ScanAxis, scan

from daquiri.instrument.spec import (
    ManagedInstrument, Generate)
from daquiri.instrument.property import ChoiceProperty, AxisSpecification


class ManagedDSP7265(ManagedInstrument):
    # Minimal, for more details look at scanning_properties_and_profiles
    driver_cls = DSP7265
    test_cls = Generate()

    x = AxisSpecification(float)

    properties = {'time_constant': ChoiceProperty(choices=DSP7265.TIME_CONSTANTS),}
    profiles = {
        'Fast': {'time_constant': DSP7265.TIME_CONSTANTS[9]},
        'Slow': {'time_constant': DSP7265.TIME_CONSTANTS[13]}
    }

    proxy_methods = [
        'auto_sensitivity',
        'auto_phase',
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
        yield lockin.set_profile('Fast')
        yield lockin.auto_phase()

        for step_x in np.linspace(self.start_x, self.stop_x, self.n_x):
            with experiment.point():
                yield [mc.stages[0].write(step_x),]
                yield [lockin.x.read(),]

        yield lockin.set_profile('Slow')


def setup_lockin(experiment, lockin=None, **kwargs):
    yield lockin.set_profile('Fast')
    yield lockin.auto_phase()


def teardown_lockin(experiment, lockin=None, **kwargs):
    yield lockin.set_profile('Slow')


class MyExperiment(Experiment):
    dx = ScanAxis('mc.stages[0]', limits=[-10, 10])
    sensitivity = ScanAxis('lockin.properties.sensitivity')

    read_power = {'power': 'lockin.x', }

    scan_methods = [
        # Two different ways of achieving a one axis scan with some instrument setup and teardown
        scan(x=dx, name='dx Scan', read=read_power, setup=setup_lockin, teardown=teardown_lockin),
        CustomScan,
    ]


app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': MockMotionController,
    'lockin': ManagedDSP7265,
})

if __name__ == '__main__':
    app.start()
