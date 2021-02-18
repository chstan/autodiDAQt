from dataclasses import dataclass

from daquiri.instrument import LogicalAxisSpecification
from daquiri.mock import MockMotionController


@dataclass
class CoordinateOffsets:
    x_off: float = 0
    y_off: float = 0
    z_off: float = 0


class LogicalMockMotionController(MockMotionController):
    r = 3.14159 / 4

    # cartesian
    x_y_z = LogicalAxisSpecification(
        {
            "stages[0]": lambda state, x, y, z: x - y,
            "stages[1]": lambda state, x, y, z: x + y,
            "stages[2]": lambda state, x, y, z: z,
        },
        {
            "x": lambda state, s0, s1, s2: (s0 + s1) / 2,
            "y": lambda state, s0, s1, s2: (s1 - s0) / 2,
            "z": lambda state, s0, s1, s2: s2,
        },
        initial_coords=(0, 0, 0),
    )  # (x,y,z) = (0,0,0)

    # stateful transform: offset coordinates
    offset_x_y_z = LogicalAxisSpecification(
        {
            "stages[0]": lambda state, x, y, z: x + state.x_off,
            "stages[1]": lambda state, x, y, z: y + state.y_off,
            "stages[2]": lambda state, x, y, z: z + state.z_off,
        },
        {
            "x": lambda state, s0, s1, s2: s0 - state.x_off,
            "y": lambda state, s0, s1, s2: s1 - state.y_off,
            "z": lambda state, s0, s1, s2: s2 - state.z_off,
        },
        initial_coords=(0, 0, 0),
        state=CoordinateOffsets,
    )
