from autodidaqt import AutodiDAQt, Experiment
from autodidaqt.mock import MockMotionController, MockScalarDetector
from autodidaqt.scan import (
    backwards,
    forwards_and_backwards,
    only,
    randomly,
    scan,
    staircase_product,
    step_together,
)


class MyExperiment(Experiment):
    dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])
    dy = MockMotionController.scan("mc").stages[1](limits=[-30, 30])

    read_power = {
        "power": "power_meter.device",
    }

    scan_methods = [
        scan(x=dx.step(randomly), name="Random Scan", read=read_power),
        scan(
            name="Forwards and Backwards",
            x=dx.step(forwards_and_backwards),
            read=read_power,
        ),
        scan(x=dx.step(backwards), name="Backwards", read=read_power),
        scan(x=dx.step(only(10)), name="At Most 10", read=read_power),
        scan(xy=step_together(dx, dy), name="Diagonal Scan", read=read_power),
        scan(xy=staircase_product(dx, dy), name="Staircase Scan", read=read_power),
    ]


app = AutodiDAQt(
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
