"""
The absolute, bare minimum. Open an application with no panels.
"""
from zhivago import Zhivago

app = Zhivago(__name__, {})
app.start()
