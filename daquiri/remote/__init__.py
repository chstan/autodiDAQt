from dataclasses import dataclass
import asyncio
from asyncio.queues import QueueEmpty
from typing import Type
from daquiri.actor import Actor
import json
from pynng import Pair0, Socket, TryAgain


@dataclass
class RemoteConfiguration:
    ui_address: str


class Remote(Actor):
    """
    Serves as a communications endpoint to the remote UI
    so that an experiment can be controlled. Pretty barebones
    because it is basically just a router which forwards
    messages to the appropriate party.
    """

    def __init__(self, app: Type["Daquiri"], config: RemoteConfiguration):
        super().__init__(app)
        self.config = config

    @staticmethod
    async def send_on_socket(message, socket: Socket):
        await socket.asend(json.dumps(message).encode("utf-8"))

    @staticmethod
    async def recv_on_socket(socket: Socket):
        data = await socket.recv(block=False)
        return json.load(data.decode("utf-8"))

    async def run(self):
        with Pair0(dial=self.config.ui_address) as socket:
            # try to forward one message to the remote ui if available
            try:
                message = self.messages.get_nowait()
                await self.send_on_socket(message, socket)
            except QueueEmpty:
                pass

            # then we try to receive a message and dispatch it on the
            # local message passing system. Typically this means
            # forwarding messages to the App or to the Experiment
            # instance.
            try:
                message = self.recv_on_socket(socket)
                # for now just echo
                self.messages.put_nowait(message)
            except TryAgain:
                pass

            await asyncio.sleep(0.05)
