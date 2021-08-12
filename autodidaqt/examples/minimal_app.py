"""
The absolute, bare minimum. Open an application with no panels.
"""
from autodidaqt import AutodiDAQt

app = AutodiDAQt(__name__, {})

if __name__ == "__main__":
    app.start()
