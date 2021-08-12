from autodidaqt import AutodiDAQt
from autodidaqt.experiment import AutoExperiment
from autodidaqt.mock import MockMotionController, MockScalarDetector
from autodidaqt.scan import scan


class MyExperiment(AutoExperiment):
    dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])
    dy = MockMotionController.scan("mc").stages[1](limits=[-30, 30])

    read_power = {"power": "power_meter.device"}

    DxDyScan = scan(x=dx, y=dy, name="dx-dy Scan", read=read_power)

    scan_methods = [DxDyScan]
    run_with = [DxDyScan(n_x=10, n_y=10)] * 100

    exit_after_finish = True
    discard_data = True


app = AutodiDAQt(
    __name__,
    {},
    {"experiment": MyExperiment},
    {
        "mc": MockMotionController,
        "power_meter": MockScalarDetector,
    },
)

if __name__ == "__main__":
    app.start()
