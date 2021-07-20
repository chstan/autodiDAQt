Plotting
========

While you can plot interim data however you like using custom panels,
many use cases actually fit well enough into common contexts that DAQuiri
has extra primitives to work with for plotting data. For performance reasons,
most of these use pyqtgrah instead of Matplotlib, but either can be used.

Adding plots for interim data to scan methods
---------------------------------------------

In the ``sequence`` method of a scan, we have access to the experiment object.
Using this, we can add additional plots to be displayed using
python:meth:`Daquiri.experiment.Experiment.plot`. This function expects a few arguments:
``name=`` which specifies the name or title to attach to the plot in the interface, the
``independent=`` axes as the axis URLs, and the ``dependent=`` axes as axis URLs.

.. code-block:: python

   def sequence(self, experiment, ...):
       ...
       # plot the reads from `power_meter.device` against `mc.stages[0]` while running
       experiment.plot(dependent='power_meter.device', independent=['mc.stages[0]', name='Line Plot')

       # plot the reads from `power_meter.device` against `mc.stages[0]` and `mc.stages[1]` as a
       # heatmap
       experiment.plot(dependent='power_meter.device', independent=['mc.stages[0]', 'mc.stages[1]'],
                       name='Heatmap/Image Plot)


Adding plots as their own Panels
--------------------------------

For an example of adding a plot as its own panel, have a look at
``daquiri.examples.plot_data``.