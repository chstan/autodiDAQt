import numpy as np

from daquiri import Daquiri, Experiment
from daquiri.mock import MockMotionController, MockDetector
from daquiri.scan import ScanAxis, scan

# As before, a fake detector
class MockSimpleDetector(MockDetector):
    def generate(self):
        return np.random.normal() + 5

class MyExperiment(Experiment):
    dx = ScanAxis('mc.stages[0]', limits=[-10, 10])
    dy = ScanAxis('mc.stages[1]', limits=[-30, 30])

    read_power = {'power': 'power_meter.device', }

    scan_methods = [
        scan(x=dx, name='dx Scan', read=read_power),
        scan(x=dx, y=dy, name='dx-dy Scan', read=read_power),
    ]

app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': MockMotionController,
    'power_meter': MockSimpleDetector,
})

if __name__ == '__main__':
    app.start()
