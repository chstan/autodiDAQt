Change Log
==========

0.0.3 (2019-12-14)
------------------

Writes appropriately to instruments and properties.

More uniform structure and API:

* ``Specification`` for an axis or property specifies a relationship
  to an instrument that will be made at time of instrument ``__init__``.
* ``ScanDegreeOfFreedom`` helper class for ``daquiri.scan.scan``
  useful in constructing scans over instrument axes and properties.

General improvements

* Tore out a lot of old code.
* No more metaclass programming.
* Fewer magic strings.
* Started putting stronger type hinting in place.
* ``CollectUI`` can now be nested/scoped.

**Logical Axes**

Logical axes supporting arbitrary coordinate transforms are now available,
even with state. These are "local" to the same managed instrument.

The internal state is currently lost when restarting but this will be changed
in a future release.

**Testing/Mocking**

No more ``test_cls`` mock information is placed on the axis
directly with a ``mock=`` keyword. All axes are mocked if the global setting
is used or if the driver for the instrument subclasses the sentinel
``MockDriver``.

**Documentation**

Started putting together real documentation.

**General Usabability**

The first generally usable release will be 0.1.0 and
we should be very close.

0.0.2 (2019-09-10)
------------------

Added scan modes + publish examples through the examples module.

0.0.1 (2019-09-09)
------------------

* Essentially working for basic applications

