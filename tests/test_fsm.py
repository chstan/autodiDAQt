import pytest
import asyncio
import enum

from daquiri.experiment import FSM
from tests.conftest import MockDaquiri


class States(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Transitions(str, enum.Enum):
    EnterB = "enter-b"
    Inc = "increment"
    Dec = "decrement"
    SwapBC = "swap-bc"
    EnterD = "enter-d"


class ExampleFSM(FSM):
    STARTING_STATE = States.A
    STATE_TABLE = {
        States.A: [
            dict(match=Transitions.EnterB, to=States.B),
            dict(match=Transitions.Inc, to=States.B),
            # make sure we accept callable transitions too
            dict(match=lambda x: x == Transitions.Dec, to=States.C),
        ],
        States.B: [
            dict(match=Transitions.SwapBC, to=States.C),
            dict(match=Transitions.Inc, to=States.C),
            dict(match=Transitions.Dec, to=States.A),
        ],
        States.C: [
            dict(match=Transitions.Dec, to=States.B),
            dict(match=Transitions.Inc, to=States.A),
            dict(match=Transitions.SwapBC, to=States.B),
            dict(match=Transitions.EnterB, to=States.B),
            dict(match=Transitions.EnterD, to=States.D),
        ],
        States.D: [],
    }

    async def enter_c(self, *_):
        pass

    async def c_to_d(self, *_):
        pass

    async def leave_a(self, *_):
        pass


class MisconfiguredFSM(FSM):
    STARTING_STATE = States.A
    STATE_TABLE = {
        States.A: [
            dict(match=Transitions.Dec, to=States.D),
        ],
        # missing the D state
    }


class MissingStartingStateFSM(MisconfiguredFSM):
    STARTING_STATE = None


class InvalidStartingStateFSM(MisconfiguredFSM):
    STARTING_STATE = States.B


@pytest.mark.asyncio
async def test_fsm_missing_starting_state(app: MockDaquiri):
    with pytest.raises(AssertionError) as assert_exc:
        _ = MissingStartingStateFSM(app)

    assert "must be specified" in str(assert_exc)


@pytest.mark.asyncio
async def test_fsm_bad_initial_state(app: MockDaquiri):
    with pytest.raises(AssertionError) as assert_exc:
        _ = InvalidStartingStateFSM(app)

    assert "must be among" in str(assert_exc)


@pytest.mark.asyncio
async def test_bad_fsm_transition(app: MockDaquiri):
    fsm = ExampleFSM(app)
    # A -> C -> D
    await fsm.fsm_handle_message(Transitions.Dec)
    await fsm.fsm_handle_message(Transitions.EnterD)

    # if the state transition does not exist then
    # it is interpreted as a generic message but in this case
    # there is no handler and the transition raises
    with pytest.raises(Exception) as exc:
        await fsm.fsm_handle_message(Transitions.Dec)

    assert "Dec" in str(exc.value)


@pytest.mark.asyncio
async def test_fsm_transitions_called(app: MockDaquiri, mocker):
    fsm = ExampleFSM(app)

    spy_leave_a = mocker.spy(fsm, "leave_a")
    spy_enter_c = mocker.spy(fsm, "enter_c")
    spy_c_to_d = mocker.spy(fsm, "c_to_d")

    await fsm.fsm_handle_message(Transitions.Dec)

    assert spy_leave_a.call_count == 1
    assert spy_enter_c.call_count == 1

    await fsm.fsm_handle_message(Transitions.EnterD)
    assert spy_c_to_d.call_count == 1
