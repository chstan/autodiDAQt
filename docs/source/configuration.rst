Configuring Applications
========================

DAQuiri allows external (outside of the code) configuration via a configuration
file: "config.json". An annotated copy of the defaults used is included here as a
Python dictionary literal:

.. code-block:: python

   {
     # Version of your, the user's software. This is used for attaching DAQ software versions to
     # data collected, and to the application's state so that we can persist logical motors, window locations,
     # etc between restarts. You can use any string here, so if you have multiple DAQ applications consider using
     # '{application_name}-X.Y.Z'.
     "version": "0.0.0",
     # DEBUG flag, used to do some checking that incurs extra overhead internally
     "debug": True,

     # Whether to keep internal logs, we recommend that you keep this on
     "logging": True,
     # Where to keep logs, by default both lots and output data are recorded in out/
     "logging_directory": "out/logs",
     # The pattern used to make the log file name
     "log_format": "{time}-{user}-{session}",

     # Where to keep output data
     "data_directory": "out/data",
     # Format for the data filenames
     "data_format": "{user}/{date}-{session}-{run}",

     # Whether to persist window locations and logical coordinates between restarts
     "maintain_state": True,
     # Where to put application state information
     "state_directory": "out/state",

     # Configuration related to instruments in your application
     "instruments": {
       # Replace all instrument drivers by mocked (fake) drivers?
       "simulate_instruments": True

       # ... more here related to individual instruments, see below.
     },

     # Per user settings: this allows configuring notifications, etc.
     "use_profiles": False,
     # profile name -> profile information
     "profiles": {}
   }


logging_directory
--------------------------

If a relative path, this is understood as being relative to the file where you call
``app.start()``. Absolute paths can be specified as well.

log_format
-------------------

This is just the name of the file to be used. We recommend time first, as this allows
simple sorting of the logs if you need to check something against a particular data file.

The actual name is constructed by using the following metadata:

1. user (str): The name of the current user or ``"test_user"`` if not specified.
2. time (str): The date and time as a string.
3. session (str): A user-provided description of the current experiment.
4. run (int): An index indicating the number of experiments/runs that have taken place
   since starting the application.

data_directory
--------------

Where to store data. See also ``logging_directory``.

data_format
-----------

What filename to use for data. See also ``log_format``

instruments
-----------

This is a whole section that contains both global and per-instrument settings.
You can use this section to replace certain instruments with test articles,
and to specify arguments to be fed into drivers during the startup process.

instruments.simulate_instruments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``bool`` flag indicating whether to replace *every* instrument with a mocked
instrument.

