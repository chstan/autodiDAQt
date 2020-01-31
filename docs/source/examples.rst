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

If we are just calling methods on our driver, we can use the declarative interface
to generate an axis. Here, we generate a polarization axis which reads from
``driver.thorlabs_rot_controller.theta`` and provides no write capability.


.. code-block:: python

   class ExampleInstrumnt(ManagedInstrument):
       polarization = AxisSpecification(float, where=['thorlabs_rot_controller.theta'])


PropertiesSpecification
-----------------------

We can also wrap discrete configuration (Properties) of our instruments, which allows us to
scan over, read, and write from these bits of configuration during our experiment. This is
exceptionally useful because it allows DAQuiri to generate scans for us that allow us to determine
optimal configuration conditions for our experiments, and to automatically log the state
of our hardware on startup and shutdown, and before and after each run of our experiment.


.. code-block:: python

   class ExampleLockInAmplifier(ManagedInstrument):
       # a discrete property
       time_constant = ChoicePropertySpecification(
           choices=LockinDriver.TIME_CONSTANTS, where=['time_constant'])

       # a continuous property
       internal_freq = PropertySpecification(float, where=['internal_frequency'])


@axis
-----

@axis provides an interface similar to Python's @property descriptor for an axis.
This is especially useful if the declarative interfaces provided by the ``*Specification``
classes are too constraining for your use case. In particular, you get to define arbitrary
async methods on your instrument that handle reading and writing for your axis, as well
as mocks.

.. code-block:: python

   class ExampleInstrument(ManagedInstrument):
       STEPS_PER_RAD = 4500
       _mock_polarization = 0

       @axis(float)
       async def polarization(self):
           steps = self.driver.thorlabs_rot_controller.theta_steps
           return float(steps) / STEPS_PER_RAD

       @polarization.write
       async def polarization(self, value):
           steps = value * STEPS_PER_RAD
           self.driver.thorlabs_rot_controller.move_theta_steps(steps)
           while True:
               if self.driver.thorlabs_rot_controller.theta_motion_finished():
                  break

               await asyncio.sleep(0.1)

       @polarization.mock_read
       async def polarization(self):
           return self._mock_polarization

       @polarization.mock_write
       async def polarization(self, value):
           self._mock_polarization = value


If you don't need them, you don't have to provide the ``@mock_read`` and ``@mock_write`` functions.
As a shorthand for just storing a value on a property, you can also pass ``mock_to=`` to the call
to the ``@axis`` decorator, which is entirely equivalent


.. code-block:: python

   class ExampleInstrument(ManagedInstrument):
       STEPS_PER_RAD = 4500

       @axis(float, mock_to='_mock_polarization')
       async def polarization(self):
           steps = self.driver.thorlabs_rot_controller.theta_steps
           return float(steps) / STEPS_PER_RAD

       @polarization.write
       async def polarization(self, value):
           steps = value * STEPS_PER_RAD
           self.driver.thorlabs_rot_controller.move_theta_steps(steps)
           while True:
               if self.driver.thorlabs_rot_controller.theta_motion_finished():
                  break

               await asyncio.sleep(0.1)


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
actions explicitly yourself. This amounts to making a class with a ``sequence``
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


This is the most general way to write a scan. If you're very familiar with Python, you'll
realize that we are yielding values back to the caller of this function. We might be tempted
to think that these are the values we wrote to the ``location`` axis and read from the ``value``
axis respectively, but they are not. Instead, they are Python objects that describe
the intent we would like to accomplish: in the first case, setting ``location`` to  ``next_point``'s
value, and in the second reading a value from ``value_reader.value``. These are collected by an
Experiment runtime inside DAQuiri and handled asynchronously.

Despite looking like clean imperative code, this provides a fully declarative way of sequencing
scans, and this some huge advantages: DAQuiri can record every action taken during the course
of our experiment and save it transparently for us with our data. Additionally, DAQuiri takes
care of the difficulty of dealing with asynchronous code for us. Any values we ``yield``
together will happen at the same time, and everything in that ``yield`` will finish before
DAQuiri moves onto the next step in the sequence.


Automated Products
------------------

You can also generate scans by forming products over axes. This is what is provided by
python:func:``daquiri.scan.scan``, which constructs a class with a ``.sequence`` method for you
by scanning over the axes provided and reading from the axes specified in the ``read=`` keyword.

.. code-block:: python

   d_location = PointMover.scan('mc').location()

   scan(location=d_location, read={'signal': 'value_reader.value'})


Manually Sequencing Scans
-------------------------

In addition to the declarative interface DAQuiri allows you to take full control if you need.
Here's an example entirely equivalent to the one above, except that we write the
async code ourselves and have direct access to the instruments.

.. code-block:: python

   @dataclass
   class CustomScanMethod:
       n_points: int = 100
       start_point: float = 0
       step_size: float = 0.1

       async def sequence(self, experiment, point_mover, value_reader):
           points = np.arange(self.start_point, self.start_point + self.n_points * self.step_size, self.n_points)
           for next_point in points:
               await point_mover.location.write(next_point)
               value = await value_reader.value.read()

               yield {'point_mover.location': next_point, 'value_reader.value': value}


We still ``yield`` back to DAQuiri, but now it is with the actual data.
This also allows us to do some computation on the data if necessary. You might notice that
DAQuiri does not make it very simple to compute values to be saved in the standard (declarative)
interface. This is intentional: it is better to save the data in as close a format as it was
recorded as possible, together with as much metadata about the process as possible, and push
computations to your data analysis. Saving partially analyzed adds opacity to the DAQ process
that contravenes scientific reproducibility.