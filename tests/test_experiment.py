import pytest
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri import experiment

from daquiri.experiment import Experiment, ExperimentTransitions, ExperimentStates
from daquiri.interlock import InterlockException
from daquiri.scan import scan
from daquiri.experiment.save import ZarrSaver
from typing import Callable

from .conftest import MockDaquiri

async def run_until(exp, condition: Callable[[Experiment], bool], max_steps: int = 100):
    for _ in range(max_steps):
        await exp.read_all_messages()
        await exp.run_current_state()
        if condition(exp):
            break


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
    save_on_main = True

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

# Test data saving policies

class SimpleScan:
    def sequence(self, experiment, mc, power_meter):
        experiment.collate(
            independent=[[mc.stages[0], "dx"]],
            dependent=[[power_meter.device, "power"]],
        )

        for i in range(10):
            with experiment.point():
                yield [mc.stages[0].write(i)]
                yield [power_meter.device.read()]


@pytest.mark.asyncio
async def test_experiment_collates_data(app: MockDaquiri, mocker):
    app.init_with(managed_instruments={
        'mc': MockMotionController,
        'power_meter': MockScalarDetector,
    })
    mocker.patch.object(ZarrSaver, "save_run")
    mocker.patch.object(ZarrSaver, "save_metadata")
    mocker.patch.object(ZarrSaver, "save_user_extras")

    class MyExperiment(UILessExperiment):
        scan_methods = [SimpleScan]

    exp = MyExperiment(app)
    await exp.prepare()
    await run_until(exp, lambda e: e.state == ExperimentStates.Idle)
    await exp.messages.put(ExperimentTransitions.Start)
    await run_until(exp, lambda e: e.state == ExperimentStates.Idle)
    ZarrSaver.save_run.assert_called_once()

        

