from daquiri.experiment import AutoExperiment, Experiment
from daquiri.scan import scan

from .scans import BasicScan, UninvertedScan

__all__ = ["BasicExperiment", "UninvertedExperiment", "Sink"]


class Sink:
    """
    There are a lot of hooks on Experiments which are explicitly configured
    in relation to the Qt UI. This may change when we provide headless operation
    but but now we can get around it by pretending to mount the UI using this sink
    which implements the Ruby "method missing" pattern.
    """

    def __call__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return self


class UILessExperiment(Experiment):
    save_on_main = True
    scan_methods = [scan(name="No Scan")]

    def __init__(self, app):
        super().__init__(app)
        self.ui = Sink()


class UILessAutoExperiment(AutoExperiment):
    save_on_main = True
    config_cls = scan(name="No Scan")
    scan_methods = [config_cls]
    run_with = [config_cls()]

    def __init__(self, app):
        super().__init__(app)
        self.ui = Sink()


class BasicExperiment(UILessExperiment):
    scan_methods = [BasicScan]


class UninvertedExperiment(UILessExperiment):
    scan_methods = [UninvertedScan]
