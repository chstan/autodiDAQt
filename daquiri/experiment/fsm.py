from asyncio import QueueEmpty, sleep

from daquiri.actor import Actor
from loguru import logger

__all__ = ["FSM"]


class FSM(Actor):
    STATE_TABLE = {
        "IDLE": [{"match": "start", "to": "RUNNING"}],
        "RUNNING": [{"match": "pause", "to": "PAUSED"}],
        "PAUSED": [{"match": "start", "to": "RUNNING"}],
    }
    STARTING_STATE = "IDLE"

    def __init__(self, app):
        super().__init__(app)
        self.state = self.STARTING_STATE
        assert self.state is not None, "Initial state must be specified"
        assert (
            self.state in self.STATE_TABLE
        ), f"Initial state must be among {list(self.STATE_TABLE.keys())}"

    async def transition_to(self, transition, trigger):
        """
        Roughly speaking, we call

        1. A function to transition out of the current state
        2. A function to transition specifically from the current state into the new one
        3. A function to transition into the next state

        1. and 3. represent teardown and setup for the states respectively, and 2.
        can capture and transition specific state logic
        Args:
            transition (dict): The transition message, with "to" and "match" keys.
            trigger: The message causing the transition

        """
        from_state = self.state.lower()
        logger.info(f"{transition}, {trigger}")
        to_state = transition["to"].lower()

        try:
            f = getattr(self, f"leave_{from_state}")
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

        try:
            f = getattr(self, f"{from_state}_to_{to_state}")
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

        self.state = transition["to"]

        try:
            f = getattr(self, f"enter_{to_state}")
        except AttributeError:
            pass
        else:
            await f(transition, trigger)

    async def fsm_handle_message(self, message):
        """
        First check if there is a transition available in the state table,
        if there is, then perform the transition with the message as context
        and invoke the appropriate transition functions and updating the internal state.

        If there is no transition available, then the message is passed off to the client message
        handler `handle_message`

        Args:
            message (str): Request to transition the state machine
        """
        found_transition = None
        if isinstance(message, str):
            # possible transitions
            for transition in self.STATE_TABLE[self.state]:
                match = transition["match"]
                if isinstance(match, str) and match == message:
                    found_transition = transition
                elif callable(match) and match(message):
                    found_transition = transition

                if found_transition:
                    break

        if found_transition is None:
            await self.handle_message(message)
        else:
            await self.transition_to(found_transition, message)

    async def handle_message(self, message):
        """
        Handler for messages not related to state transitions.

        If subclassed, you can handle any work related to external events here.

        Args:
            message (str): Message from another Actor or thread
        """
        raise Exception(message)

    async def read_one_message(self):
        message = self.messages.get_nowait()
        await self.fsm_handle_message(message)
        self.messages.task_done()

    async def read_all_messages(self):
        """
        This is mostly a convenience hook for testing,
        but it also reduces nesting in the run definition slightly
        """
        try:
            while True:
                await self.read_one_message()
        except QueueEmpty:
            pass

    async def run_current_state(self):
        f = getattr(self, "run_{}".format(self.state.lower()))
        await f()
        # NEVER TRUST THE USER, this ensures we yield back to the scheduler
        await sleep(0)

    async def run(self):
        while True:
            await self.read_all_messages()
            await self.run_current_state()
