from multiprocessing import Process

from autodidaqt_common.remote.command import (
    AllState,
    GetAllStateCommand,
    SetScanConfigCommand,
    StartRunCommand,
)
from autodidaqt_common.remote.config import RemoteConfiguration

from autodidaqt.core import CommandLineConfig
from autodidaqt.examples.scanning_experiment import SimpleScan, SimpleScanMode, app
from autodidaqt.remote.scheduler import PairScheduler

remote_config = RemoteConfiguration("tcp://127.0.0.1:13133")


class TestScheduler(PairScheduler):
    async def run_schedule(self):
        self.socket.send(GetAllStateCommand())
        state: AllState = await self.wait_for_message()

        # just a sanity check
        assert "SimpleScan" in [t.name for t in state.state.extra_types.values()]

        scan = SimpleScan(n_steps=17, start=-9, stop=7, mode=SimpleScanMode.MOVE_WHILE_MEASURING)
        self.socket.send(SetScanConfigCommand.from_scan_config(scan))
        self.socket.send(StartRunCommand())
        data = await self.run_finishes()

        await self.shuts_down_normally()


def run():
    config = CommandLineConfig(headless=True, remote_config=remote_config)
    app.configure_as_headless(config)
    app.start()


if __name__ == "__main__":
    TestScheduler.run_with_standard_middleware(Process(target=run), remote_config)
