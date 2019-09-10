from loguru import logger
from PyQt5.QtWidgets import QPlainTextEdit

from daquiri.panel import Panel
from daquiri.ui import grid

__all__ = ('LogPanel',)

class LogPanel(Panel):
    MAX_HISTORY = 300
    TITLE = 'Application Logs'
    SIZE = (700, 500)

    def before_close(self):
        try:
            logger.remove(self._log_handler)
        except ValueError:
            pass
        super().before_close()

    def __init__(self, *args, **kwargs):
        self.lines = []
        self._log_handler = None
        self.log_table = None

        super().__init__(*args, **kwargs)

    def on_log(self, message):
        self.lines.append(message)
        self.log_table.appendPlainText(message.strip())

    def layout(self):
        with open(self.app.log_file, 'r') as logfile:
            self.lines = [l.strip() for l in logfile.readlines()[-self.MAX_HISTORY:]]

        self.log_table = QPlainTextEdit(self)
        self.log_table.setReadOnly(True)

        self.log_table.appendPlainText('\n'.join(self.lines))
        self._log_handler = logger.add(self.on_log)

        grid(
            self.log_table,
            self.close_button,
            widget=self,
        )
