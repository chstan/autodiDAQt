import asyncio

from daquiri.state import ActorState

__all__ = ('Actor', 'EchoActor')


class Actor:
    panel_cls = None

    def __init__(self, app):
        self.app = app
        self.messages = None

    async def prepare(self):
        self.messages = asyncio.Queue()

    async def run(self):
        raise NotImplementedError()

    def collect_state(self) -> ActorState:
        return ActorState()

    def receive_state(self, state: ActorState):
        print(self, 'Received state', state)


class EchoActor(Actor):
    async def run(self):
        while True:
            message = await self.messages.get()
            print(message)