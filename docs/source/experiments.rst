Experiments
===========

Experiments are a way to organize a bunch of scan modes together along with
some utility features like UI generation, queueing, and automated data IO.

You can think of an experiment as the ``Actor`` that actual reads through your
desired sequence of action performs the motions and data acquisition for you.

This logic is inverted compared to a few other scientific data acquisition libraries:
usually you as the user perform all the motions and DAQ and it's just data collation
that gets handled by the library.

Although it may seem strange, this inverted control scheme has a number of benefits.

Benefits of inverted experiment control
---------------------------------------

**Inverted control is safer.** As a user, you only specify what actions to take,
this prevents data loss in the event that you try to do something illegal or that
would otherwise cause issue (such as by violating an interlock). In this case DAQuiri
will try to proceed anyway, will save any data collected so far, and will let you
know there was an issue.

**Inverted control provides a record of what you intended to do.** Because you are already
providing a representation of what to do in data as opposed to in code, DAQuiri can just
save the sequence of actions you requested. A huge benefit here is that there is no ambiguity
as to what happened during the course of data collection, the record of motions and data
collections is available after the fact together with complete timestamps.

**Inverted control decouples planning from execution.** By using inverted control,
it is straightforward to manipulate the desired scan sequence in order to achieve a
desirable goal. As an example, it becomes trivial to perform a scan many times, adjusting
the temperature between each internal experiment. As another example, during optical pump-probe
experiments, we perform data collection out-of-sequence in order to remove the effect of
laser power drift during experiments.

Other benefits of experiments in DAQuiri
----------------------------------------

You are welcome to perform experiments that don't follow this inverted control scheme.
If you do, you can still make use of a variety of other benefits DAQuiri can provide to you.

**UI generation:** DAQuiri provides utility wrappers around Qt to make it a bit softer and
more Pythonic, and can perform full UI generation for you scans if they are straightforward
enough.

**Handling data IO:** In most cases you don't need to use the inverted control scheme to
let DAQuiri handle data IO for you. Of course, you are free to collate data on your own and save
it however you want.

