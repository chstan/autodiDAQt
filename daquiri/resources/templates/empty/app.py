import os, sys
from daquiri import Daquiri

# You can put custom DAQ code in the local module
sys.path.append(os.path.dirname(__file__))
from local import *


app = Daquiri(__name__, {})

if __name__ == "__main__":
    app.start()
