"""
Package setup.py
"""

import os
from pathlib import Path
from setuptools import setup

about = {}
with open(str(Path(__file__).parent.absolute() / "daquiri" / "version.py")) as fp:
    exec(fp.read(), about)

VERSION = about["VERSION"]


def read_content(filepath):
    with open(filepath) as fobj:
        return fobj.read()


classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: Implementation :: CPython",
    "Natural Language :: English",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: Microsoft :: Windows :: Windows 7",
    "Operating System :: Microsoft :: Windows :: Windows 8",
    "Operating System :: Microsoft :: Windows :: Windows 10",
    "Operating System :: Unix",
    "Operating System :: POSIX :: Linux",
    "Topic :: Scientific/Engineering",
    "Topic :: Software Development :: Libraries :: Python Modules",
]


long_description = read_content("README.rst") + read_content(
    os.path.join("docs/source", "CHANGELOG.rst")
)

requirements = [
    "setuptools",
    "PyQt5>=5.13.0",
    "Quamash>=0.6.1",
    "asyncqt",
    "matplotlib>=3.1.1",
    "python-dotenv>=0.10.3",
    "pyqt-led>=0.0.6",
    "slackclient>=2.1.0",
    "loguru>=0.3.2",
    "rx>=3.0.1",
    "pyqtgraph",
    "qtsass",
    "pymeasure",
    "pyrsistent",
    "appdirs",
    # Instruments
    "python-ivi>=0.14.9",
    "instrumentkit>=0.5.0",
    "pyvisa",
    "pyvisa-sim",
    # other numerics
    "numpy",
    "scipy",
    # zarr + xarray support
    "toolz",
    "pandas",
    "partd",
    "fsspec",
    "xarray",
    "zarr",
    "dask",
]

extras_require = {
    "reST": ["Sphinx"],
}

setup(
    name="daquiri",
    version=VERSION,
    description="DAQuiri = DAQ + UI Generation + Reactivity + Instruments: A simple scientific DAQ framework.",
    long_description=long_description,
    python_requires=">=3.7.0",
    author="Conrad Stansbury",
    author_email="chstansbury@gmail.com",
    url="https://daquiri.readthedocs.org",
    classifiers=classifiers,
    packages=["daquiri"],
    data_files=[],
    install_requires=requirements,
    include_package_data=True,
    extras_require=extras_require,
)
