# mantid-profiler

Use [psrecord](https://github.com/astrofrog/psrecord) and [Plotly.js](https://plot.ly/javascript/) to profile a Mantid workflow.

It monitors CPU and RAM usage, and reports the time span of each algorithm (currently, only algorithms are recorded).

![screenshot of AlignAndFocusPowderFromFiles](screenshot.png)

## Pixi

[direnv](https://pixi.prefix.dev/latest/integration/third_party/direnv/)
automatically activates the pixi environment as soon as you enter the root directory of the repository,
by parsing an `.envrc` file that you create there.
We recommend the following contents for the `.envrc` file:

```
watch_file pixi.lock  # invokes the shell-hook whenever pixi.lock changes
eval "$(pixi shell-hook --change-ps1 false)"
eval "$(register-python-argcomplete mantidprofiler)"  # register argcomplete
```

## Usage

To profile the `SNSPowderReduction.py` workflow:
```
python SNSPowderReduction.py & mantidprofiler $!
```

Executable `mantidprofiler` is available in the pixi environment, but sometimes
you need to run the script in a different environment, one supporting Mantid.

For the "mantid-developer" conda environment:
```
conda activate mantid-developer
(mantid-developer) python SNSPowderReduction.py & pixi run --manifest-path /path/to/repository/mantid-profiler/pyproject.toml mantidprofiler $!
```

For the pixi environment:
```
pixi run --manifest-path /path/to/repo/mantid/pixi.toml SNSPowderReduction.py & pixi run --manifest-path /path/to/repo/mantid-profiler/pyproject.toml mantidprofiler $!
```

The script attaches to the last spawned process, so you can also use the profiler if you are working with `MantidPlot`:
```
./MantidPlot & mantidprofiler $!
```

## Requires

- `psutil`
- You need to build Mantid with the `-DPROFILE_ALGORITHM_LINUX=ON` `CMake` flag to get the timing output from the algorithms.

## Results

After running on the `SNSPowderReduction.py` workflow, the profiler produces a `profile.html` file to be viewed with an internet browser.
![SNS Powder Reduction profile](http://www.nbi.dk/~nvaytet/SNSPowderReduction_12.png)

You can interact with a demo profile [here](http://www.nbi.dk/~nvaytet/SNSPowderReduction_12.html).

**Controls:**

- Mouse wheel to zoom (horizontal zoom only)
- Left click to select zoom region (horizontal zoom only)
- Double-click to reset axes
- Hold shift and mouse click to pan

## More options for mantid-profiler.py

- `-h`, `--help`          show this help message and exit
- `--outfile OUTFILE`    name of output html file (default: `profile.html`)
- `--infile INFILE`      name of input file containing algorithm timings (default: `algotimeregister.out`)
- `--logfile LOGFILE`    name of output file containing process monitor data (default: `mantidprofile.txt`)
- `--diskfile DISKFILE`  name of output file containing process disk usage data (default: `mantiddisk.txt`)
- `--interval INTERVAL`  how long to wait between each sample (in seconds). By default the process is sampled as often as possible. (default: None)
- `--noclean`             remove files upon successful completion (default: False)
- `--height HEIGHT`      height for html plot (default: 800)
- `--bytes`               Report disk speed in GBps rather than Gbps (default: False)
- `--mintime MINTIME`    minimum duration for an algorithm to appear inthe profiling graph (in seconds). (default: 0.1)

## Notes for developers

The version number for releases is stored in `pyproject.toml` and everything else reads this information.
To change the version number for a release, either edit the file by hand or `pixi project version minor` to bump the minor version number.

## Similar projects

[viztracer](https://github.com/gaogaotiantian/viztracer) creates similar information for generic python software

## Related Documentation

- [Mantid's AlgoTimeRegister](https://docs.mantidproject.org/api/python/mantid/api/AlgoTimeRegister.html) explains the under-the-hood of the timing mechanism.
- [Mantid developer profiler documentation](https://developer.mantidproject.org/AlgorithmProfiler.html) provides additional information as to how it works with mantid.
- [Mantid User Properties File](https://docs.mantidproject.org/concepts/PropertiesFile.html#algorithm-profiling-settings) has some fields to be noted.


## Contact

Neil Vaytet, European Spallation Source

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/mantidproject/mantid-profiler/main.svg)](https://results.pre-commit.ci/latest/github/mantidproject/mantid-profiler/main)
