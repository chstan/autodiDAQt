Usage Examples
==============

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


Granular Examples
=================

AxisSpecification
-----------------

.. code-block:: python

   class ExampleInstrumnt(ManagedInstrument):
       polarization = AxisSpecification(float, where=['thorlabs_rot_controller.theta'])


PropertiesSpecification
-----------------------

.. code-block:: python

   class ExampleLockInAmplifier(ManagedInstrument):
       # a discrete property
       time_constant = ChoicePropertySpecification(choices=LockinDriver.TIME_CONSTANTS, where=['time_constant'])

       # a continuous property
       internal_freq = PropertySpecification(float, where=['internal_frequency'])


Scan Methods
------------

There are many different ways of defining types of scans your experiment should be able to perform.
Make sure you're familiar with the scan documentation, and then you can have a look below.

In order to use a scan, you need to make sure it's registered with your experiment by adding it
to the python:attr:``daquiri.experiment.Experiment.scan_methods`` attribute.

.. code-block:: python

   class MyExperiment(Experiment):
       scan_methods = [
           # Scan method classes here
       ]

       ...

The most direct way to specify a scan is to sequence the
actions explicitly yourself. This amounts to making a class with a `sequence`
generator providing the motion and DAQ steps.

DAQuiri insists on classes for this purpose because typically your scan will
require some configuration (conditions under which to collect data, desired ranges,
etc.).

You should use the dataclass decorator (``@dataclasses.dataclass``) for now,
so that DAQuiri can render UI for you to populate the configuration of the scan.
In the future, you will be able to specify how to render fields if you need to.

.. code-block:: python

   import numpy as np
   from dataclasses import dataclass

   @dataclass
   class CustomScanMethod:
       n_points: int = 100
       start_point: float = 0
       step_size: float = 0.1

       def sequence(self, experiment, point_mover, value_reader):
           points = np.arange(self.start_point, self.start_point + self.n_points * self.step_size, self.n_points)
           for next_point in points:
               yield point_mover.location.write(next_point)
               yield value_reader.value.read()

This is the most general way to write a scan using the inverted control scheme. In the 1.0.0 release, you will
also be able to directly talk to instruments, if you find the inverted control scheme too rigid, despite its advantges.

You can also generate scans by forming products over axes. This is what is provided by
python:func:``daquiri.scan.scan``, which constructs a class with a ``.sequence`` method for you
by scanning over the axes provided and reading from the axes specified in the ``read=`` keyword.

.. code-block:: python

   d_location = PointMover.scan('mc').location()

   scan(location=d_location, read={'signal': 'value_reader.value'})
