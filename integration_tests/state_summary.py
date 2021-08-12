from multiprocessing import Process

from autodidaqt_common.remote.command import GetAllStateCommand
from autodidaqt_common.remote.config import RemoteConfiguration

from autodidaqt.core import CommandLineConfig
from autodidaqt.examples.scanning_experiment_revisited import app
from autodidaqt.remote.scheduler import PairScheduler

remote_config = RemoteConfiguration("tcp://127.0.0.1:13133")


class TestScheduler(PairScheduler):
    async def run_schedule(self):
        self.socket.send(GetAllStateCommand())
        message = await self.wait_for_message()
        print(message)
        await self.shuts_down_normally()


def run():
    config = CommandLineConfig(headless=True, remote_config=remote_config)
    app.configure_as_headless(config)
    app.start()


if __name__ == "__main__":
    TestScheduler.run_with_standard_middleware(Process(target=run), remote_config)
