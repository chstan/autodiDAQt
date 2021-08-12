from autodidaqt import AutodiDAQt
from autodidaqt.experiment import AutoExperiment
from autodidaqt.mock import MockImageDetector, MockMotionController
from autodidaqt.scan import scan


class MyExperiment(AutoExperiment):
    dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])

    read_power = {"power": "ccd.device"}

    DxScan = scan(x=dx, name="dx Scan", read=read_power)

    scan_methods = [DxScan]
    run_with = [DxScan(n_x=100)] * 3

    exit_after_finish = True
    discard_data = False


app = AutodiDAQt(
    __name__,
    {},
    {"experiment": MyExperiment},
    {
        "mc": MockMotionController,
        "ccd": MockImageDetector,
    },
)

if __name__ == "__main__":
    app.start()
