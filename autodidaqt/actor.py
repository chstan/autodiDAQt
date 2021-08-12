import asyncio

from autodidaqt.state import ActorState

__all__ = ("Actor", "EchoActor", "MessagingActor")


class StopException(Exception):
    pass


class Actor:
    panel_cls = None

    def __init__(self, app):
        self.app = app
        self.messages = None

    async def prepare(self):
        self.messages = asyncio.Queue()

    async def run(self):
        raise NotImplementedError

    async def shutdown(self):
        pass

    def collect_state(self) -> ActorState:
        return ActorState()

    def receive_state(self, state: ActorState):
        pass

    def collect_remote_state(self):
        return None

    def collect_extra_wire_types(self):
        return {}


class MessagingActor(Actor):
    async def run(self):
        try:
            while True:
                await self.read_messages()
                await self.run_step()
        except StopException:
            return

    async def handle_user_message(self, message):
        pass

    async def handle_message(self, message):
        from autodidaqt_common.remote.command import RequestShutdown

        if isinstance(message, RequestShutdown):
            await self.shutdown()
            await message.respond_did_shutdown(self.app)
            raise StopException()

        await self.handle_user_message(message)

    async def read_messages(self):
        try:
            while True:
                message = self.messages.get_nowait()
                self.messages.task_done()
                await self.handle_message(message)
        except asyncio.QueueEmpty:
            pass

    async def run_step(self):
        pass


class EchoActor(Actor):
    async def handle_user_message(self, message):
        print(message)
