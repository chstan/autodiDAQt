"""
DAQuiri also provides the ability to define an axis computed over one or several other axes. For instance, suppose you
want to move in polar coordinates rather than cartesian coordinates, we want to define axes r, theta that internally
drive the x, y axes.

In this example we show how to generate these computed axes and to scan over them, allowing scanning over arbitrary
coordinates specified by the user.

This example is otherwise very similar to `examples/scanning_experiment_revisited.py`
"""

import numpy as np
from dataclasses import dataclass

from daquiri import Daquiri, Experiment
from daquiri.instrument import LogicalAxisSpecification
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import scan


def mod_angle_positive(theta):
    return theta + 2 * np.pi if theta < 0 else theta


@dataclass
class CoordinateOffsets:
    x_off: float = 0
    y_off: float = 0
    z_off: float = 0


class LogicalMockMotionController(MockMotionController):
    r = np.pi / 4

    # cartesian
    x_y_z = LogicalAxisSpecification({
        'stages[0]': lambda state, x, y, z: x - y,
        'stages[1]': lambda state, x, y, z: x + y,
        'stages[2]': lambda state, x, y, z: z,
    }, {
        'x': lambda state, s0, s1, s2: s0 + s1 / 2,
        'y': lambda state, s0, s1, s2: s1 - s0 / 2,
        'z': lambda state, s0, s1, s2: s2,
    }, initial_coords=(0, 0, 0)) # (x,y,z) = (0,0,0)

    # cylindrical coordinates
    r_theta_z = LogicalAxisSpecification({
        'stages[0]': lambda state, r, theta, z: r * np.cos(theta),
        'stages[1]': lambda state, r, theta, z: r * np.sin(theta),
        'stages[2]': lambda state, r, theta, z: z,
    }, {
        'r': lambda state, s0, s1, s2: np.sqrt(s0 ** 2 + s1 ** 2),
        'theta': lambda state, s0, s1, s2: mod_angle_positive(np.arctan2(s1, s0)),
        'z': lambda state, s0, s1, s2: s2,
    }, initial_coords=(0, 0, 0)) # (r,theta,z) = (0,0,0)

    # stateful transform: offset coordinates
    offset_x_y_z = LogicalAxisSpecification({
        'stages[0]': lambda state, x, y, z: x + state.x_off,
        'stages[1]': lambda state, x, y, z: y + state.y_off,
        'stages[2]': lambda state, x, y, z: z + state.z_off,
    }, {
        'x': lambda state, s0, s1, s2: s0 - state.x_off,
        'y': lambda state, s0, s1, s2: s1 - state.y_off,
        'z': lambda state, s0, s1, s2: s2 - state.z_off,
    }, initial_coords=(0, 0, 0), state=CoordinateOffsets)


mc_cls = LogicalMockMotionController


class MyExperiment(Experiment):
    dx = mc_cls.scan('mc').stages[0](limits=[-10, 10])
    dy = mc_cls.scan('mc').stages[0](limits=[-30, 30])

    dlogical_x = mc_cls.scan('mc').x_y_z.x(limits=[-10, 10])
    dlogical_y = mc_cls.scan('mc').x_y_z.y(limits=[-10, 10])
    dlogical_z = mc_cls.scan('mc').x_y_z.z(limits=[-5, 5])

    dlogical_r = mc_cls.scan('mc').r_theta_z.r(limits=[0, 10])
    dlogical_theta = mc_cls.scan('mc').r_theta_z.theta(limits=[0, 2 * np.pi])
    dlogical_cylindrical_z = mc_cls.scan('mc').r_theta_z.z(limits=[-5, 5])

    read_power = {'power': 'power_meter.device', }

    scan_methods = [
        scan(x=dx, name='dx Scan', read=read_power),
        scan(x=dx, y=dy, name='dx-dy Scan', read=read_power),

        # Single Axes (variable X scan)
        scan(x=dlogical_x, name='Logical X', read=read_power),

        # XZ Plane scan
        scan(x=dlogical_x, z=dlogical_z, name='Logical XZ', read=read_power),

        # Cylindrical coordinates scan
        scan(r=dlogical_r, theta=dlogical_theta, z=dlogical_cylindrical_z,
             name='Cylindrical', read=read_power)
    ]


app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': LogicalMockMotionController,
    'power_meter': MockScalarDetector,
})

if __name__ == '__main__':
    app.start()
