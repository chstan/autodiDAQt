from daquiri import Daquiri
from daquiri.experiment import AutoExperiment
from daquiri.mock import MockMotionController, MockScalarDetector
from daquiri.examples.scanning_time_to_completion import TwoAxisScan


class MyExperiment(AutoExperiment):
    scan_methods = [TwoAxisScan]
    run_with = [TwoAxisScan(n_steps_x=100, n_steps_y=50)] * 5

    exit_after_finish = True
    discard_data = False
    save_on_main = True


app = Daquiri(__name__, {}, {'experiment': MyExperiment}, {
    'mc': MockMotionController,
    'power_meter': MockScalarDetector,
})

if __name__ == '__main__':
    app.start()
