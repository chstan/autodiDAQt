# need to monkeypatch pyqt_led because it does not work on the CI server
from daquiri.core import make_user_data_dataclass
import sys
from PyQt5.QtWidgets import QWidget

class Led(QWidget):
    capsule = 1
    circle = 2
    rectangle = 3

    def __init__(self, *args, **kwargs):
        super().__init__()
        

module = type(sys)('pyqt_led')
module.Led = Led
sys.modules['pyqt_led'] = module

import pytest

import logging
from _pytest.logging import caplog as _caplog
from loguru import logger

from typing import Dict
from pathlib import Path

from daquiri.experiment.save import ZarrSaver
from daquiri import Daquiri, Actor
from daquiri.collections import AttrDict
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.config import Config, default_config_for_platform, MetaData
from daquiri.instrument import ManagedInstrument
from daquiri.state import AppState

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


class MockDaquiri(Daquiri):
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

        self.main_window = AttrDict({
            'open_panels': {}
        })

    @property
    def file(self):
        return '[pytest]'

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
        print('Cleanup')

    @property
    def instruments(self):
        return AttrDict(self._instruments)

    @property
    def actors(self):
        return AttrDict(self._actors)

    @property
    def managed_instruments(self):
        return self._instruments


@pytest.fixture(scope='function')
def app():
    """
    Generates a ``daquiri.core.Daquiri`` like instance to act in place of an app.

    Returns: A ``TestDaquiri`` instance.
    """

    app = MockDaquiri()
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
            'mc': MockMotionController,
            'power_meter': MockScalarDetector,
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

