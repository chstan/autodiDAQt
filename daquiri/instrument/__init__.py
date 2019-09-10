from .front_panel import *
from .ivi_front_panel import *
from .axis import Axis, Detector
from .spec import DaquiriInstrumentMeta


def open_instrument(instrument_fp_cls, experiment, name, address=None):
    resolved_address = address or instrument_fp_cls.address

    if issubclass(instrument_fp_cls, FrontPanel):
        return instrument_fp_cls(instrument_fp_cls.instrument_cls.open_visa(resolved_address), experiment, name)

    return instrument_fp_cls(
        instrument_fp_cls.instrument_cls(resolved_address, prefer_pyvisa=True),
        experiment, name)


def open_test(instrument_fp_cls, experiment, name):
    if issubclass(instrument_fp_cls, FrontPanel):
        return instrument_fp_cls(instrument_fp_cls.instrument_cls.open_test(), experiment, name)

    # temporarily just inject a test driver
    return instrument_fp_cls(
        instrument_fp_cls.instrument_cls(
            instrument_fp_cls.test_driver_cls()),
        experiment, name)


