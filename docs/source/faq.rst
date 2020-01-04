Frequently Asked Questions
==========================

Why should I use DAQuiri instead of LabView?
--------------------------------------------

You shouldn't if you're that rare LabView guru that filters through
physics departments every now and again. If you're like the rest of
us and you don't have real-time requirements (or are willing to interface
with another language to deal with those requirements) then there's
a good chance you can get to taking data faster than if you use LabView.

Why should I use DAQuiri instead of PyMeasure/InstrumentKit/...
---------------------------------------------------------------

PyMeasure is an excellent library for interfacing directly with
scientific hardware, but it is still lower-level than is desirable for
scripting experiments. With DAQuiri you won't have to write
a single line of UI code but you can get instrument front panels,
multiple scan modes, interim data plotting, logging, and more.

Ideally, we think you should use PyMeasure or similar to write your
instrument drivers, and then script your experiment with DAQuiri.

Do I need to use Python 3.7?+
-----------------------------

Yes. DAQuiri uses type annotations in a few places to do UI generation magic.
Also dataclasses are the most convenient way to specify scan types.

