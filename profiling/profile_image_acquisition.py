from daquiri import Daquiri
from daquiri.experiment import AutoExperiment
from daquiri.mock import MockMotionController, MockImageDetector
from daquiri.scan import scan


class MyExperiment(AutoExperiment):
    dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])
    read_power = {"power": "ccd.device"}

    DxScan = scan(x=dx, name="dx Scan", read=read_power)

    scan_methods = [DxScan]
    run_with = [DxScan(n_x=1000)] * 10

    exit_after_finish = True
    discard_data = True


app = Daquiri(
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
