# need to mock pyqt_led because it does not work on the CI server
import sys


class Led:
    pass


module = type(sys)('pyqt_led')
module.Led = Led
sys.modules['pyqt_led'] = module

from typing import Dict

import pytest
from daquiri import Daquiri, Actor
from daquiri.collections import AttrDict
from daquiri.config import Config, default_config_for_platform, MetaData
from daquiri.instrument import ManagedInstrument
from daquiri.state import AppState


class MockDaquiri(Daquiri):
    _instruments: Dict[str, ManagedInstrument]
    _actors: Dict[str, Actor]

    def __init__(self, *args, **kwargs):
        self._instruments = {}
        self._actors = {}
        self.config = Config(default_config_for_platform())
        self.meta = MetaData()
        self.app_state = AppState()

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