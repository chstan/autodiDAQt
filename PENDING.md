# Refactors

Need to refactor schemas to better support Array and Object types.

## Axis/Property

We should probably better reify the axis/property concept and delegate to them to construct
the relevant bit of UI and link it with the data. Currently this is spread across path recorder,
`scan.scan`, and `ExperimentPanel`, which is manageable but as the complexity of what we allow on these
grows we should be better about this.

# Features Necessary Eventually

1. Large file/memmap support, collect many data points synchronously against camera like
   instruments
2. Stream directly to file

# Documentation

# Profiling
