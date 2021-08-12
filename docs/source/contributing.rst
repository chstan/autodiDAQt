Contributing to autodidaqt
=======================

We would gladly appreciate contributions from users to improve autodidaqt and
the documentation. We also welcome reports of any issues with software or the
clarity of the documentation, and ideas that might advance the core aims
of the project: to let scientists write free data acquisition software
(quickly!).

If you want to contribute to the code, get in touch (see the authors page) and
check out some of the features on our backlog. You'll need a few tools in order
to work on autodidaqt:

1. git
2. Python >= 3.7 (Anaconda/Miniconda is best because some dependencies are otherwise
   difficult to install).

Installing a development copy of autodidaqt
----------------------------------------

Clone (or fork) the repository::
    git clone https://github.com/chstan/autodidaqt.git
    cd autodidaqt

Install an environment you can work with using Anaconda or Miniconda (preferably).
This process is well documented elsewhere, and there's nothing unusual in the process
for us.

Once in your environment, install autodidaqt and its requirements locally with

.. code-block:: bash

   # conda activate {my environment}

   pip install -e .

   # ...much time passes...
   # at this point you should be able to run autodidaqt and the examples.

   python -m autodidaqt.examples.scanning_experiment


Working on a new feature
------------------------

After 1.0.0 (before which there will likely be a lot of code churn),
development will roughly follow *A Successful Git Branching Model*, albeit
with the more standard branch names **develop -> master** and **master -> release**.

Please contribute new features on feature branches and issue pull/merge requests
in order to make changes.

If you make a large change such as adding a new feature, please contribute or recruit
a willing volunteer to make sure the adjustment is reflected in the documentation
and tests.