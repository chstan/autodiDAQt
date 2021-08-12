Overview
========

autodidaqt is a consistent set of user interface (UI), concurrency, and scientific instrumentation tools
built around Qt5 (and PyQt5) and Python 3's ``asyncio``.

You can use autodidaqt to automate or simplify essentially any tasks where your computer
is being used to coordinate pieces of hardware, but it is especially well suited to
scientific data collection.

To accomplish this, autodidaqt is built around a few central abstractions.

Panels and Actors
=================

autodidaqt is concerned with organizing concurrency, and providing UI for scientists.
Panels are the window abstraction that autodidaqt builds over PyQt5, a popular UI framework
in order to simplify matters.

For concurrency, autodidaqt provides actors: long running and independent pieces of
code which execute simultaneously and which may own an associated picee of user interface.

These abstractions are used to facilitate communicating with scientific instruments (a practical
example of an actor in autodidaqt) and to plan and execute experiments. Here we arrive at a more granular
set of abstractions.

Axes, Scans, Strategies, Experiments
====================================

autodidaqt asks that you wrap the hardware you use in your experiments in axes:
these represent ways in which you can reconfigure your experiment, and thereby
determine the configuration-space in which your experiment takes place.

Particular sections of this configuration space can be explored, and data
collected, this is called *scanning* in autodidaqt. Nonetheless, there are many
different meaningful ways of traversing configuration space as we collect data,
and we shouldn't generally have to concern ourselves with these details: they
should be strongly decoupled from the configuration-space.

By performing many scans, we can collect a series of datasets and thereby
conduct an experiment.

autodidaqt provides primitives that correspond to each of the ideas here discussed:
there are facilities to traverse and collect data over relevant portions of the
parameter space, primitives to specify the degrees of freedom that exist in your
setup, and an execution runtime to perform the experiment for you.
