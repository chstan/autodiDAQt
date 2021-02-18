from daquiri import Daquiri, Experiment
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.scan import scan

dx = MockMotionController.scan("mc").stages[0](limits=[-10, 10])
dy = MockMotionController.scan("mc").stages[1](limits=[-30, 30])

read_power = {
    "power": "power_meter.device",
}


class MyExperiment(Experiment):
    scan_methods = [
        scan(x=dx, name="dx Scan", read=read_power),
        scan(x=dx, y=dy, name="dx-dy Scan", read=read_power),
    ]


app = Daquiri(
    __name__,
    {},
    {"experiment": MyExperiment},
    {"mc": MockMotionController, "power_meter": MockScalarDetector},
)

if __name__ == "__main__":
    app.start()
