=========
 autodidaqt
=========

|test_status| |coverage| |docs_status| 

|example|

.. |docs_status| image:: https://readthedocs.org/projects/autodidaqt/badge/?version=latest&style=flat
   :target: https://autodidaqt.readthedocs.io/en/latest/
.. |coverage| image:: https://codecov.io/gh/chstan/autodidaqt/branch/master/graph/badge.svg?token=8M5ON9HZL2
   :target: https://codecov.io/gh/chstan/autodidaqt
.. |example| image:: docs/source/_static/autodidaqt-example.gif
.. |test_status| image:: https://github.com/chstan/autodidaqt/workflows/CI%20with%20pytest/badge.svg?branch=master
   :target: https://github.com/chstan/autodidaqt/actions


autodidaqt := DAQ + UI generation + Reactivity + Instruments

You should be spending your time designing and running experiments,
not your DAQ software.

autodidaqt is a nuts and bolts included framework for scientific data acquisition (DAQ),
designed for rapid prototyping and the challenging DAQ environment of angle resolved
photoemission spectroscopy. If you specify how to sequence motions and data collection,
autodidaqt can manage the user interface, talking to and managing instruments,
plotting interim data, data collation, and IO for you.

autodidaqt also has logging and notification support built in and can let you know
over email or Slack when your experiment finishes (successfully or not!).

If autodidaqt doesn't do exactly what you need, get in contact with us or
check out the examples. There's a good chance that if it isn't built in,
autodidaqt is flexible enough to support your use case.


Requirements
============

* Python 3.7 over
* NoArch

Features
========

Automated DAQ
-------------

autodidaqt wraps instruments and data sources in a uniform interface, if you specify how
to sequence motion and acquisition, autodidaqt handles async collection, IO, and visualizing
your data as it is acquired.

UI Generation
-------------

autodidaqt using PyQt and Qt5 to generate UIs for your experiments. It also
provides simple bindings (autodidaqt.ui) that make making managing the day to day
of working on PyQt simpler, if you need to do UI scripting of your own.

It also ships with a window manager that you can register your windows against,
making it seamless to add extra functionality to your experiments.

The autodidaqt UI bindings are wrapped to publish as RxPY observables, making it easier
to integrate your PyQT UI into a coherent asynchronous application.

Installation
============

::

  $ pip install autodidaqt


Usage
=====

For usage examples, explore the scripts in the examples folder. You can run them with

::

  $ python -m autodidaqt.examples.[example_name]


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

  $ python -m autodidaqt.examples


