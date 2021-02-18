from daquiri import Daquiri, ManagedInstrument
from daquiri.experiment import AutoExperiment
from daquiri.instrument.spec import MockDriver, axis
from daquiri.mock import MockScalarDetector
from daquiri.scan import scan


class ManualMotionController(ManagedInstrument):
    driver_cls = MockDriver

    mock_s0 = 0
    mock_s1 = 0

    @axis(float)
    async def s0(self):
        return self.driver.axis[0].position

    @s0.write
    async def s0(self, value):
        self.driver.axis[0].move(value)

    @s0.mock_read
    async def s0(self):
        return self.mock_s0

    @s0.mock_write
    async def s0(self, value):
        self.mock_s0 = value

    @axis(float)
    async def s1(self):
        return self.driver.axis[1].position

    @s1.write
    async def s1(self, value):
        self.driver.axis[1].move(value)

    @s1.mock_read
    async def s1(self):
        return self.mock_s1

    @s1.mock_write
    async def s1(self, value):
        self.mock_s1 = value


class MyExperiment(AutoExperiment):
    dx = ManualMotionController.scan("mc").s0(limits=[-10, 10])
    dy = ManualMotionController.scan("mc").s1(limits=[-30, 30])

    read_power = {"power": "power_meter.device"}

    DxScan = scan(x=dx, name="dx Scan", read=read_power)
    DxDyScan = scan(x=dx, y=dy, name="dx-dy Scan", read=read_power)

    scan_methods = [DxScan, DxDyScan]
    run_with = [DxScan(n_x=2500)] * 10

    exit_after_finish = True
    discard_data = True


app = Daquiri(
    __name__,
    {},
    {"experiment": MyExperiment},
    {
        "mc": ManualMotionController,
        "power_meter": MockScalarDetector,
    },
)

if __name__ == "__main__":
    app.start()
