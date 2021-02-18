import random

from daquiri import Daquiri, Experiment
from daquiri.interlock import InterlockException
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import scan


async def second_axis_is_retracted(experiment, mc, power_meter):
    second_stage_value = await mc.stages[1].read()
    if not (0 < second_stage_value < 5):
        raise InterlockException(
            "The second manipulator axis must be retracted before starting the experiment!"
        )


async def high_voltage_is_off(*_):
    if random.random() < 0.5:
        raise InterlockException("You forgot to turn off the high voltage!")


class MyExperiment(Experiment):
    dx = MockMotionController.scan("mc").stages[0]()
    read_power = dict(power="power_meter.device")

    scan_methods = [
        scan(
            x=dx,
            name="dx Scan",
            read=read_power,
            preconditions=[second_axis_is_retracted],
        ),
    ]

    # can also set a "global" check, that can be verified whenever starting or resuming a scan
    # if you need really custom behavior just modify `start_running` or `{initial_state}_to_running`
    # as is appropriate for your application
    interlocks = [high_voltage_is_off]


app = Daquiri(
    __name__,
    {},
    {"experiment": MyExperiment},
    {"mc": MockMotionController, "power_meter": MockScalarDetector},
)

if __name__ == "__main__":
    app.start()
