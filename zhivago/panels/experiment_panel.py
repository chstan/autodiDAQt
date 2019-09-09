import enum

from zhivago.panel import Panel
from zhivago.ui import (
    CollectUI, tabs, vertical, group, horizontal,
    combo_box, button, numeric_input,
    check_box,
    label, line_edit,
    bind_dataclass,
    layout_dataclass)
from zhivago.utils import enum_option_names

__all__ = ('ExperimentPanel',)

class ExperimentPanel(Panel):
    SIZE = (250, 450)
    TITLE = 'Experiment'
    DEFAULT_OPEN = True
    RESTART = True

    def layout_scan_methods(self, methods):
        return [[m.__name__ , layout_dataclass(m)] for m in methods]

    @property
    def experiment(self):
        # better to configure things so panels can be associated 1-to-1 with actors
        # at setup time otherwise this will break or require runtime type inspection
        return self.app.actors['experiment']

    def layout(self):
        experiment = self.experiment
        scan_methods = experiment.scan_methods

        ui = {}
        with CollectUI(ui):
            vertical(
                horizontal(
                    button('Start', id='start'),
                    button('Pause', id='pause'),
                    button('Stop', id='stop'),
                    label('Status: Waiting', id='status-box'),
                ),
                horizontal(
                    'Use',
                    combo_box([s.__name__ for s in scan_methods], id='selected_scan_method'),
                ),
                tabs(
                    ['Status', vertical('Status')],
                    ['Scans', tabs(
                        *self.layout_scan_methods(scan_methods)
                    )],
                ),
                widget=self,
            )

        for scan_method in scan_methods:
            name = scan_method.__name__
            bind_dataclass(experiment.scan_configuration[name], prefix=name + '.', ui=ui)

        ui['start'].subject.subscribe(self.start)
        ui['stop'].subject.subscribe(self.stop)
        ui['pause'].subject.subscribe(self.pause)

        ui['selected_scan_method'].subject.on_next(experiment.use_method)
        ui['selected_scan_method'].subject.subscribe(self.set_scan_method)

    def set_scan_method(self, scan_method):
        self.experiment.use_method = scan_method

    def start(self, *_):
        self.experiment.messages.put_nowait('start')

    def stop(self, *_):
        self.experiment.messages.put_nowait('stop')

    def pause(self, *_):
        self.experiment.messages.put_nowait('pause')
