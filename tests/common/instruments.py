import contextlib

from pymeasure.instruments.signalrecovery import DSP7265

from daquiri import ManagedInstrument
from daquiri.instrument import AxisSpecification
from daquiri.instrument.spec import ChoicePropertySpecification

__all__ = ["PropertyInstrument"]


class Driver(DSP7265):
    category = "A"


class PropertyInstrument(ManagedInstrument):
    driver_cls = Driver

    # -> don't need where= because we can look on self.instrument.phase by default
    phase = AxisSpecification(float)
    x = AxisSpecification(float)
    y = AxisSpecification(float)
    mag = AxisSpecification(float)

    sensitivity = ChoicePropertySpecification(
        where=["sensitivity"],
        choices=DSP7265.SENSITIVITIES,
        labels=lambda _, k: f"{k} V",
    )

    _categories = ["A", "B", "C", "D", "E"]
    categorical = ChoicePropertySpecification(
        where=["category"], choices=dict(zip(_categories, _categories))
    )

    time_constant = ChoicePropertySpecification(
        where=["time_constant"],
        choices=DSP7265.TIME_CONSTANTS,
        labels=lambda _, k: f"{k} s",
    )

    profiles = {
        "Fast": {
            "sensitivity": DSP7265.SENSITIVITIES[8],
            "time_constant": DSP7265.TIME_CONSTANTS[9],
        },
        "Slow": {
            "sensitivity": DSP7265.SENSITIVITIES[8],
            "time_constant": DSP7265.TIME_CONSTANTS[13],
        },
    }
