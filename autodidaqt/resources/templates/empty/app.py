import os
import sys

from autodidaqt import AutodiDAQt

# You can put custom DAQ code in the local module
sys.path.append(os.path.dirname(__file__))
from local import *

app = AutodiDAQt(__name__, {})

if __name__ == "__main__":
    app.start()
