from pymeasure.instruments.signalrecovery.dsp7265 import DSP7265

from daquiri import Daquiri, Experiment
from daquiri.instrument.spec import ChoicePropertySpecification, MethodSpecification
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import scan
from daquiri.instrument import ManagedInstrument, AxisSpecification


class ManagedDSP7265(ManagedInstrument):
    driver_cls = DSP7265

    # -> don't need where= because we can look on self.instrument.phase by default
    phase = AxisSpecification(float)
    x = AxisSpecification(float)
    y = AxisSpecification(float)
    mag = AxisSpecification(float)

    sensitivity = ChoicePropertySpecification(
        where=['sensitivity'], choices=DSP7265.SENSITIVITIES, labels=lambda _, k: f'{k} V')
    time_constant = ChoicePropertySpecification(
        where=['time_constant'], choices=DSP7265.TIME_CONSTANTS, labels=lambda _, k: f'{k} s')
    auto_sensitivity = MethodSpecification(where=['auto_sensitivity'])
    auto_phase = MethodSpecification(where=['auto_phase'])

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


class MyExperiment(Experiment):
    dx = MockMotionController.scan('mc').stages[0](limits=[-10, 10])
    dsensitivity = ManagedDSP7265.scan('lockin').sensitivity()
    dtime_constant = ManagedDSP7265.scan('lockin').time_constant()

    read_power = {'power': 'power_meter.device', }

    scan_methods = [
        scan(x=dx, sensitivity=dsensitivity, name='Sensitivity Scan', read=read_power),
        scan(x=dx, tc=dtime_constant, name='Time Constant Scan', read=read_power),

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
