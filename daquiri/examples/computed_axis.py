"""
DAQuiri also provides the ability to define an axis computed over one or several other axes. For instance, suppose you
want to move in polar coordinates rather than cartesian coordinates, we want to define axes r, theta that internally
drive the x, y axes.

In this example we show how to generate these computed axes and to scan over them, allowing scanning over arbitrary
coordinates specified by the user.

This example is otherwise very similar to `examples/scanning_experiment_revisited.py`
"""

import numpy as np

from daquiri import Daquiri, Experiment
from daquiri.instrument.property import LogicalAxisSpecification
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import ScanAxis, scan


class LogicalMockMotionController(MockMotionController):
    r = np.pi / 4

    # cartesian
    x_y_z = LogicalAxisSpecification({
        'stages[0]': lambda self, x, y, z: x - y,
        'stages[1]': lambda self, x, y, z: x + y,
        'stages[2]': lambda self, x, y, z: z,
    }, initial_state=(0, 0, 0))

    # cylindrical coordinates
    r_theta_z = LogicalAxisSpecification({
        'stages[0]': lambda self, r, theta, z: r * np.cos(theta),
        'stages[1]': lambda self, r, theta, z: r * np.sin(theta),
        'stages[2]': lambda self, r, theta, z: z,
    }, initial_state=(0, 0, 0))


class MyExperiment(Experiment):
    dx = ScanAxis('mc.stages[0]', limits=[-10, 10])
    dy = ScanAxis('mc.stages[1]', limits=[-30, 30])

    logical_x = ScanAxis('mc.x_y_z.x', limits=[-10, 10])
    logical_y = ScanAxis('mc.x_y_z.y', limits=[-10, 10])
    logical_z = ScanAxis('mc.x_y_z.z', limits=[-5, 5])

    logical_r = ScanAxis('mc.r_theta_z.r', limits=[0, 10])
    logical_theta = ScanAxis('mc.r_theta_z.theta', limits=[0, 2 * np.pi])
    logical_cylindrical_z = ScanAxis('mc.r_theta_z.z', limits=[-5, 5])

    read_power = {'power': 'power_meter.device', }

    scan_methods = [
        scan(x=dx, name='dx Scan', read=read_power),
        scan(x=dx, y=dy, name='dx-dy Scan', read=read_power),

        # Single Axes (variable X scan)
        scan(x=logical_x, name='Logical X', read=read_power),

        # XZ Plane scan
        scan(x=logical_x, z=logical_z, name='Logical XZ', read=read_power),

        # cylindrical coordinates scan
        scan(r=logical_r, theta=logical_theta, z=logical_cylindrical_z, name='Cylindrical', read=read_power)
    ]


app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': LogicalMockMotionController,
    'power_meter': MockScalarDetector,
})

if __name__ == '__main__':
    app.start()
