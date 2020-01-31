DAQuiri: Painless scientific DAQ
================================

**DAQuiri** := DAQ + UI generation + reactivity + instruments

You should be spending your time designing and running experiments,
not your DAQ software.

DAQuiri is a nuts and bolts included framework for scientific data acquisition (DAQ), designed
for rapid prototyping and the challenging DAQ environment of angle resolved photoemission
spectroscopy. If you specify how to *sequence* motions and data collection, daquiri can manage
the user interface, talking to and managing instruments, plotting interim data, data collation,
and IO for you. Despite all this, DAQuiri is very low overhead and is profiled before
each release: acquisition rates faster than 100μs are possible on synthetic tasks, meaning
most reasonable experiments will be IO bound using DAQuiri.

If DAQuiri doesn't do exactly what you need, get in contact with us or check out the
examples. There's a good chance that if it isn't built in, DAQuiri is flexible enough to support
your use case.

Documention
-----------

**Getting Started**

* :doc:`why-use-daquiri`
* :doc:`faq`
* :doc:`overview`
* :doc:`examples`
* :doc:`installing`

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Getting Started

   why-use-daquiri
   faq
   overview
   examples
   installing

**User Guide**

* :doc:`terminology`
* :doc:`axes`
* :doc:`experiments`
* :doc:`instruments`
* :doc:`scanning`
* :doc:`plotting`
* :doc:`panels`
* :doc:`actors`
* :doc:`notifications`
* :doc:`configuration`

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: User Guide

   terminology
   axes
   experiments
   instruments
   scanning
   plotting
   panels
   actors
   notifications
   configuration

**Reference**

* :doc:`development-efforts`
* :doc:`api`
* :doc:`internals`
* :doc:`contributing`
* :doc:`CHANGELOG`

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Reference

   development-efforts
   api
   internals
   contributing
   CHANGELOG

