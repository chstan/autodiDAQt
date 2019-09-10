"""
The absolute, bare minimum. Open an application with no panels.
"""
from daquiri import Daquiri

app = Daquiri(__name__, {})

if __name__ == '__main__':
    app.start()
