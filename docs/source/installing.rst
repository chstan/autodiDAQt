Installing DAQuiri
==================

Required software
-----------------

* Python >= 3.7

Additionally, we require a number of packages as dependencies, including

* scipy
* numpy
* PyQt5
* pyqtgraph
* zarr
* dask

You can get a full list of requirements from the setup.py and requirements.txt
if you are interested.

Instructions
------------

DAQuiri is just a Python package, published under the name ``daquiri``. It is listed
on PyPI and conda, so you can install it like any other package

.. code-block::bash
   $ conda install daquiri

   # or...
   $ pip install daquiri

If you opt not to use conda, you will need to make sure you have installed the
dependencies requiring conda first. Installing ``pyqtgraph`` and ``dask`` should
be enough to ensure that a subsequent ``pip install`` will work.

