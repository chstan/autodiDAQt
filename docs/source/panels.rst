Panels
======

Panels are windows, as provided by PyQt5, but simpler to manage:

* Panels are restartable, and autodidaqt gives you another window where you
  can open closed panels
* Panels are easily sized, can be opened automatically on start
* (in 1.0.0) The location and state of panels will be restored
  between application starts.
* The contents of panels can be easily configured using the context
  manager ``CollectUI`` and data binding to Python objects.


Panels can exist independently from the rest of the application. In
this way you can use them for whatever UI needs you have.
Additionally however, panels tend to be in correspondence with actors,
so that independent computational contexts have associated UI.

This is used to provide front panels for instruments, and to provide
the user interface for running experiments.
