import pytest

from daquiri.experiment import Experiment, ExperimentTransitions, ExperimentStates
from daquiri.interlock import InterlockException
from daquiri.scan import scan

from .conftest import MockDaquiri

async def failing_interlock(*_):
    raise InterlockException("This is a failing interlock.")

async def succeeding_interlock(*_):
    return


class Sink:
    """
    There are a lot of hooks on Experiments which are explicitly configured
    in relation to the Qt UI. This may change when we provide headless operation
    but but now we can get around it by pretending to mount the UI using this sink
    which implements the Ruby "method missing" pattern.
    """
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

class UILessExperiment(Experiment):
    def __init__(self, app):
        super().__init__(app)
        self.ui = Sink()
    

@pytest.mark.asyncio
async def test_experiment_interlocks(app: MockDaquiri):
    class WithInterlocks(UILessExperiment):
        interlocks = [succeeding_interlock]
        scan_methods = [scan(name="No Scan")]

    experiment = WithInterlocks(app)
    await experiment.fsm_handle_message(ExperimentTransitions.Initialize)
    assert experiment.state == ExperimentStates.Idle
    await experiment.fsm_handle_message(ExperimentTransitions.Start)
    assert experiment.state == ExperimentStates.Running

    class WithFailingInterlocks(UILessExperiment):
        interlocks = [failing_interlock]
        scan_methods = [scan(name="No Scan")]
    
    experiment = WithFailingInterlocks(app)
    await experiment.prepare()
    await experiment.fsm_handle_message(ExperimentTransitions.Initialize)
    assert experiment.state == ExperimentStates.Idle
    await experiment.fsm_handle_message(ExperimentTransitions.Start)
    # flush the internal transition message
    await experiment.read_one_message()

    # should still be in the idle state
    assert experiment.state == ExperimentStates.Idle