from daquiri.scan import scan
from tests.common.experiments import UninvertedExperiment
import pytest
import inspect
from daquiri.experiment import AutoExperiment, Experiment, ExperimentTransitions, ExperimentStates
from daquiri.interlock import InterlockException
from daquiri.experiment.save import ZarrSaver
from typing import Callable, Union

from .common.experiments import BasicExperiment, UILessAutoExperiment, UILessExperiment

RunUntilCondition = Union[Callable[[Experiment], bool], ExperimentStates]

async def run_until(exp, condition: RunUntilCondition, max_steps: int = 100):
    if not callable(condition):
        target_state = condition
        condition = lambda e: e.state == target_state

    for _ in range(max_steps):
        await exp.read_all_messages()
        await exp.run_current_state()
        if condition(exp):
            break


async def failing_interlock(*_):
    raise InterlockException("This is a failing interlock.")

async def succeeding_interlock(*_):
    return

class WithInterlocks(UILessExperiment):
    interlocks = [succeeding_interlock]

class WithFailingInterlocks(UILessExperiment):
    interlocks = [failing_interlock]


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [WithInterlocks])
async def test_experiment_interlocks(experiment: Experiment):
    await experiment.fsm_handle_message(ExperimentTransitions.Initialize)
    assert experiment.state == ExperimentStates.Idle

    await experiment.fsm_handle_message(ExperimentTransitions.Start)
    assert experiment.state == ExperimentStates.Running


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [WithFailingInterlocks])
async def test_experiment_failing_interlocks(experiment: Experiment):
    await experiment.fsm_handle_message(ExperimentTransitions.Initialize)
    assert experiment.state == ExperimentStates.Idle
    
    # flush the internal transition message
    await experiment.fsm_handle_message(ExperimentTransitions.Start)
    await experiment.read_one_message()

    # should still be in the idle state
    assert experiment.state == ExperimentStates.Idle


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [None])
async def test_experiment_collates_data(experiment: Experiment):
    await run_until(experiment, ExperimentStates.Idle)
    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)

    ZarrSaver.save_run.assert_called_once()


@pytest.mark.asyncio        
@pytest.mark.parametrize('experiment_cls', [None])
async def test_experiment_queues_basic(experiment: Experiment, mocker):
    await run_until(experiment, ExperimentStates.Idle)

    spy_enter_running = mocker.spy(experiment, "idle_to_running")

    experiment.enqueue()
    experiment.enqueue()

    assert len(experiment.scan_deque) == 2
    
    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)

    assert spy_enter_running.call_count == 2
    assert len(experiment.scan_deque) == 0

    spy_enter_running.reset_mock()
    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)

    assert spy_enter_running.call_count == 1
    assert len(experiment.scan_deque) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [UninvertedExperiment])
async def test_uninverted_experiment(experiment: Experiment):
    await run_until(experiment, ExperimentStates.Idle)
    assert inspect.isasyncgenfunction(experiment.scan_configuration.sequence)

    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)

    ZarrSaver.save_run.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [BasicExperiment])
async def test_can_pause_experiment(experiment: Experiment):
    await run_until(experiment, ExperimentStates.Idle)
    await experiment.messages.put(ExperimentTransitions.Start)

    await run_until(experiment, ExperimentStates.Idle, 5)
    await experiment.messages.put(ExperimentTransitions.Pause)

    await run_until(experiment, ExperimentStates.Paused)
    assert experiment.state == ExperimentStates.Paused

    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Running)
    assert experiment.state == ExperimentStates.Running
    await run_until(experiment, ExperimentStates.Idle)
    assert experiment.state == ExperimentStates.Idle

    ZarrSaver.save_run.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [BasicExperiment])
async def test_experiment_progress(experiment: Experiment):
    await run_until(experiment, ExperimentStates.Idle)

    # The basic experiment we use for testing runs a scan
    # which does a separate read and write on each step.
    # Therefore, it will take 20+1 steps before we complete the scan
    assert experiment.current_progress == (None, 10)
    await experiment.messages.put(ExperimentTransitions.Start)

    await run_until(experiment, ExperimentStates.Idle, 5)
    assert experiment.current_progress == (2, 10)

    await run_until(experiment, ExperimentStates.Idle, 5)
    assert experiment.current_progress == (4, 10)

    await run_until(experiment, ExperimentStates.Idle, 11)
    assert experiment.current_progress == (10, 10)

    # finished now
    await run_until(experiment, ExperimentStates.Idle, 11)
    assert experiment.current_progress == (None, 10)


def precondition(*args, **kwargs):
    raise ValueError("xyz")

class PreconditionFailExperiment(UILessExperiment):
    scan_methods = [
        scan(
            name="Precondition Scan",
            preconditions=[precondition,],
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [PreconditionFailExperiment])
async def test_experiment_precondition(experiment: Experiment, caplog):
    await run_until(experiment, ExperimentStates.Idle)

    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)

    assert "Failed precondition" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('experiment_cls', [UILessAutoExperiment])
async def test_autoexperiment(experiment: AutoExperiment, mocker):
    run_running_spy = mocker.spy(Experiment, "run_running")
    await run_until(experiment, ExperimentStates.Idle)
    assert run_running_spy.call_count > 0
    assert ZarrSaver.save_run.call_count == 1

    experiment.discard_data = True
    ZarrSaver.save_run.reset_mock()
    await experiment.messages.put(ExperimentTransitions.Start)
    await run_until(experiment, ExperimentStates.Idle)
    assert ZarrSaver.save_run.call_count == 0

