=========
 DAQuiri
=========

daquiri := DAQ + UI generation + Reactivity + Instruments

You should be spending your time designing and running experiments,
not your DAQ software.

DAQuiri is a nuts and bolts included framework for scientific data acquisition (DAQ),
designed for rapid prototyping and the challenging DAQ environment of angle resolved
photoemission spectroscopy. If you specify how to sequence motions and data collection,
daquiri can manage the user interface, talking to and managing instruments,
plotting interim data, data collation, and IO for you.

DAQuiri also has logging and notification support built in and can let you know
over email or Slack when your experiment finishes (successfully or not!).

If DAQuiri doesn't do exactly what you need, get in contact with us or
check out the examples. There's a good chance that if it isn't built in,
DAQuiri is flexible enough to support your use case.


Requirements
============

* Python 3.7 over
* NoArch

Features
========

Automated DAQ
-------------

DAQuiri wraps instruments and data sources in a uniform interface, if you specify how
to sequence motion and acquisition, DAQuiri handles async collection, IO, and visualizing
your data as it is acquired.

UI Generation
-------------

DAQuiri using PyQt and Qt5 to generate UIs for your experiments. It also
provides simple bindings (daquiri.ui) that make making managing the day to day
of working on PyQt simpler, if you need to do UI scripting of your own.

It also ships with a window manager that you can register your windows against,
making it seamless to add extra functionality to your experiments.

The DAQuiri UI bindings are wrapped to publish as RxPY observables, making it easier
to integrate your PyQT UI into a coherent asynchronous application.

Installation
============

::

  $ pip install daquiri


Usage
=====

For usage examples, explore the scripts in the examples folder. You can run them with

::

  $ python -m daquiri.examples.[example_name]


replacing [example_name] with one of:

1. minimal_app
2. plot_data
3. simple_actors
4. ui_panels
5. wrapping_instruments
6. scanning_experiment
7. scanning_experiment_revisited
8. scanning_interlocks
9. scanning_custom_plots
10. scanning_setup_and_teardown
11. scanning_properties_and_profiles

You can also get a list of all the available examples by running

::

  $ python -m daquiri.examples


