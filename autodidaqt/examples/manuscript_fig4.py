"""See also examples.strategies for more ways of combining simple experiments."""
from autodidaqt import AutodiDAQt, Experiment
from autodidaqt.mock import MockMotionController, MockScalarDetector
from autodidaqt.scan import randomly, scan


class MyExperiment(Experiment):
    dt = MockMotionController.scan("mc").stages[0](limits=[-10, 10])

    read_power = { "power": "power_meter.device"}
    scan_methods = [
        scan(delay=dt, name="Regular Delay Scan", read=read_power),
        scan(delay=dt.step(randomly), name="Shuffled Delay Scan", read=read_power),
    ]


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
