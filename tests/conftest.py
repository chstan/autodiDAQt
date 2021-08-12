# need to monkeypatch pyqt_led because it does not work on the CI server
import sys

from PyQt5.QtWidgets import QWidget


class Led(QWidget):
    capsule = 1
    circle = 2
    rectangle = 3

    def __init__(self, *args, **kwargs):
        super().__init__()

    def turn_on(self):
        pass


module = type(sys)("pyqt_led")
module.Led = Led
sys.modules["pyqt_led"] = module

from typing import Dict

import logging
from pathlib import Path

import pytest
from _pytest.logging import caplog as _caplog
from loguru import logger

from autodidaqt import Actor, AutodiDAQt
from autodidaqt.collections import AttrDict
from autodidaqt.config import Config, MetaData, default_config_for_platform
from autodidaqt.core import make_user_data_dataclass
from autodidaqt.experiment.save import ZarrSaver
from autodidaqt.instrument import ManagedInstrument
from autodidaqt.mock import MockMotionController, MockScalarDetector
from autodidaqt.state import AppState

from .common.experiments import BasicExperiment


@pytest.fixture
def caplog(_caplog):
    """
    Forwards loguru log messages to the pytest logger according to the advice in
    https://loguru.readthedocs.io/en/stable/resources/migration.html
    """

    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropogateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class Mockautodidaqt(AutodiDAQt):
    _instruments: Dict[str, ManagedInstrument]
    _actors: Dict[str, Actor]

    def __init__(self, *args, **kwargs):
        self._instruments = {}
        self.managed_instrument_classes = {}
        self._actors = {}
        self.panel_definitions = {}

        self.config = Config(default_config_for_platform())
        self.meta = MetaData()
        self.app_state = AppState()

        self.user_cls = make_user_data_dataclass(profile_field=None)
        self.user = self.user_cls(user="test_user", session_name="test_session")

        self.main_window = AttrDict({"open_panels": {}})

    @property
    def file(self):
        return "[pytest]"

    def init_with(self, managed_instruments=None, panels=None):
        if managed_instruments is None:
            managed_instruments = {}

        if panels is None:
            panels = {}

        for k, ins_cls in managed_instruments.items():
            ins = ins_cls(app=self)
            self._instruments[k] = ins
            self.managed_instrument_classes[k] = ins_cls

        self.panel_definitions.update(panels)

    def cleanup(self):
        print("Cleanup")

    @property
    def instruments(self):
        return AttrDict(self._instruments)

    @property
    def actors(self):
        return AttrDict(self._actors)

    @property
    def managed_instruments(self):
        return self._instruments


@pytest.fixture(scope="function")
def app():
    """
    Generates a ``autodidaqt.core.autodidaqt`` like instance to act in place of an app.

    Returns: A ``Testautodidaqt`` instance.
    """

    app = Mockautodidaqt()
    yield app
    app.cleanup()


@pytest.fixture(scope="function")
def experiment_cls():
    return None


@pytest.fixture(scope="function")
def instrument_classes():
    return None


@pytest.fixture(scope="function")
async def experiment(app, mocker, caplog, experiment_cls, instrument_classes):
    if experiment_cls is None:
        experiment_cls = BasicExperiment

    if instrument_classes is None:
        instrument_classes = {
            "mc": MockMotionController,
            "power_meter": MockScalarDetector,
        }

    app.init_with(instrument_classes)

    mocker.patch.object(ZarrSaver, "save_run")
    mocker.patch.object(ZarrSaver, "save_metadata")
    mocker.patch.object(ZarrSaver, "save_user_extras")
    mocker.patch.object(Path, "mkdir")

    exp = experiment_cls(app)
    app.actors["experiment"] = exp
    await exp.prepare()

    yield exp
