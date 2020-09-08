from PyQt5.QtCore import QTimer

__all__ = ("debounce",)

class Debouncer:
    timer = None
    callback = None
    duration: float = 0.15

    cached_args = None
    cached_kwargs = None
    
    def __init__(self, callback, duration=0.15):
        self.timer = None
        self.callback = callback
        self.duration = duration
    
    def fire(self):
        self.callback(*self.cached_args, **self.cached_kwargs)

        # cleanup
        self.cached_args = None
        self.cached_kwargs = None

        self.dispose_timer()
    
    def dispose_timer(self):
        if self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None


    def __call__(self, *args, **kwargs):
        self.cached_args = args
        self.cached_kwargs = kwargs

        self.dispose_timer()

        self.timer = QTimer()
        self.timer.setInterval(self.duration * 1000)
        self.timer.timeout.connect(self.fire)
        self.timer.start()
        

def debounce(duration=0.15):
    def wrap(f):
        debouncer = Debouncer(f, duration)

        # this is necessary because otherwise Python will
        # not pass self to the bound __call__ of Debouncer
        def internal(*args, **kwargs):
            debouncer(*args, **kwargs)

        return internal
    
    return wrap

