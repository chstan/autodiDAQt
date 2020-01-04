Instruments
===========

Instruments are the most important part of our experiments.
Unfortunately, essentially every manufacturer and driver library has a different way
of configuring, communicating with, reading from, and writing to instruments.

Also, most instrument drivers are synchronous, but the natural way of thinking
about experiments is asynchronous (this is something LabView did correctly).

DAQuiri deals with these issues by letting you specify where to find controls/meaurements
and settings on your instruments and wrapping them.

This seems like extra work but it's straightforward and it provides many benefits.

Completely uniform access to axes
---------------------------------

DAQuiri has only one API for axes, so if you swap out physical hardware none
of your scan-level code has to change, just the location of the control on the physical
instrument. The DAQuiri ``Axis`` API is also very simple with essentially two
asynchronous functions: ``read`` and ``write``.

Automated logging
-----------------

DAQuiri can be configured to log all reads and writes to axes for you.


Coordinate transforms and logical axes
--------------------------------------

Because of the consistent API surrounding the wrapped axes, and because internally
DAQuiri knows what kind of data every axis and setting corresponds to, you can easily
create higher level descriptions of the degrees-of-freedom in your experiment with
logical axes.

These logical axes can be used on the same footing as the physical axes that they abstract,
and make the process of scripting your experiments simpler and less error prone.

Front panel generation
----------------------

Finally, one of the largest advantages is that having wrapped a driver in axes and properties,
DAQuiri will handle building UI "front panels" for you. This lets you write to axes separately
from your experimental protocol, visualize measurements, and configure your instruments
before the experiment.