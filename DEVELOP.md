# Installing for Dev Purposes

You can use the environment.dev.yml file in order to configure a conda environment. This will use reasonable defaults for the Python version and will also install all requirements in order to run tests interactively as opposed to through tox.

```bash
$> conda env create -f environment.yml
```

## TDD and running tests

Scripts are available through yarn.

```bash
$> yarn watch-tests
```

There are separate scripts for different test phases, as appropriate.

## Generating profiling data

UNFINISHED ADD CROSS PLATFORM
