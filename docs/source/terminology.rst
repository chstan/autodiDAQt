Terminology
===========

Collected here are some terminology used throughout the documentation
and in the DAQuiri source. Hopefully they are useful in understanding
the documentation and in appreciating the philosophy behind decisions
and compromises DAQuiri has made.

----

**axis**: Anything that can be read from, and possibly written to.
Writes and reads take finite time, potentially long amounts of time,
axes are therefore asynchronous. Axes may represent physical pieces of
hardware, like temperature controllers, motion controllers, photodiodes,
spectrometeters, or DAQ cards. Axes can represent logical devices,
such as coordinate transforms (Kelvin <-> Fahrenheit, XYZ <-> RThetaZ).
Axes can also represent conveniences that don't exist in actuality:
waits, virtual motors to repeat experiments, etc. An **axis** is
formalized in DAQuiri by the **Axis** class and its declarations in
**AxisSpecification** and others.

----

**property**: A setting or bit of configuration on an instrument or your
experiment. Properties tend to be discrete rather than continuous (axes tend
to be continuous) but this is only coincidence. In DAQuiri, you can write and
read from properties as well. Like an axis, a property can be scanned.

----

**scan**: Informally, a sequence of motions and data collection steps that
defines a dat acquisition routine. A scan fully specifies a data collection
procedure. By analogy, a loop together with its contents fully describes a
computation while neither the method of looping (in DAQuiri, a **strategy**)
nor the loop contents and range (in DAQuiri, the configuration-space or axes)
does.

----

**strategy**: An approach to iterating across configurations of the setup without
details of what the dimensions or ranges are, or what data collection
is to be performed at each point. For practical examples of strategies view
the separate documentation page on them.

