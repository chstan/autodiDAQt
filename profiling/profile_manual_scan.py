from autodidaqt import AutodiDAQt
from autodidaqt.examples.scanning_time_to_completion import TwoAxisScan
from autodidaqt.experiment import AutoExperiment
from autodidaqt.mock import MockMotionController, MockScalarDetector


class MyExperiment(AutoExperiment):
    scan_methods = [TwoAxisScan]
    run_with = [TwoAxisScan(n_steps_x=100, n_steps_y=50)] * 5

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
