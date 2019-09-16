from pymeasure.instruments.signalrecovery.dsp7265 import DSP7265

from daquiri import Daquiri, Experiment
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import ScanAxis, scan

from daquiri.instrument.spec import (
    ManagedInstrument, Generate, AxisSpecification)
from daquiri.instrument.property import ChoiceProperty


class ManagedDSP7265(ManagedInstrument):
    driver_cls = DSP7265
    test_cls = Generate()

    # -> don't need where= because we can look on self.instrument.phase by default
    phase = AxisSpecification(float)
    x = AxisSpecification(float)
    y = AxisSpecification(float)
    mag = AxisSpecification(float)

    properties = {
        'sensitivity': ChoiceProperty(choices=DSP7265.SENSITIVITIES, labels=lambda x: f'{x} V'),
        'time_constant': ChoiceProperty(choices=DSP7265.TIME_CONSTANTS, labels=lambda x: f'{x} s'),
    }

    profiles = {
        'Fast': {
            'sensitivity': DSP7265.SENSITIVITIES[8],
            'time_constant': DSP7265.TIME_CONSTANTS[9],
        },
        'Slow': {
            'sensitivity': DSP7265.SENSITIVITIES[8],
            'time_constant': DSP7265.TIME_CONSTANTS[13],
        }
    }

    proxy_methods = ['auto_sensitivity', 'auto_phase']


dx = MockMotionController.scan('mc').stages[0]
sensitivity = ManagedDSP7265.scan('lockin').sensitivity
time_constant = ManagedDSP7265.scan('lockin').time_constant

read_power = {'power': 'power_meter.device', }


class MyExperiment(Experiment):
    scan_methods = [
        scan(x=dx, sensitivity=sensitivity, name='Sensitivity Scan', read=read_power),
        scan(x=dx, tc=time_constant, name='Time Constant Scan', read=read_power),

        scan(x=dx, name='Fast Scan', read=read_power, profiles=dict(lockin='Fast')),
        scan(x=dx, name='Slow Scan', read=read_power, profiles=dict(lockin='Slow')),
    ]


app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': MockMotionController,
    'power_meter': MockScalarDetector,
    'lockin': ManagedDSP7265,
})

if __name__ == '__main__':
    app.start()
