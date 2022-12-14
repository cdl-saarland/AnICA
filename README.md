# AnICA - Analyzing Inconsistencies in Microarchitectural Code Analyzers

AnICA is a tool for discovering inconsistencies in microarchitectural code analyzers such as
[llvm-mca](https://llvm.org/docs/CommandGuide/llvm-mca.html),
[uiCA](https://uops.info/uiCA.html),
[OSACA](https://www.perf-lab.hpc.fau.de/software/osaca/),
[IACA](https://www.intel.com/content/www/us/en/developer/articles/tool/architecture-code-analyzer.html),
[Ithemal](https://github.com/ithemal/Ithemal), and
[DiffTune](https://github.com/ithemal/DiffTune).
It uses differential testing in combination with an Abstract-Interpretation-inspired generalization algorithm to produce concise results.

There is a webapp-based user interface to explore AnICA campaigns.
An installation of the UI contains a full AnICA installation, you might
therefore consider to just install the UI.

## Context: The AnICA Project

**This repo is a part of the AnICA project.** Here are more related resources, for some context:
- [The project page](https://compilers.cs.uni-saarland.de/projects/anica/) provides general information on the project.
- [AnICA](https://github.com/cdl-saarland/AnICA) (this repository), the repo for the implementation of the core AnICA algorithm. Start there if you want to work with AnICA without the artifact VM and don't want to use the browser-based user interface.
- [AnICA-UI](https://github.com/cdl-saarland/AnICA-UI), the repo for the accompanying browser-based user interface for inspecting discovered inconsistencies. Start there if you want to work with AnICA without the artifact VM and you want to use the UI.
- [iwho](https://github.com/cdl-saarland/iwho), a subcomponent of AnICA that provides a convenient abstraction around instructions, which in this project greatly eases the task of randomly sampling valid basic blocks. Start there if you only want to use the instruction schemes abstraction, independent of AnICA.
- [AnICA-Artifact](https://github.com/cdl-saarland/AnICA-Artifact), which provides the scripts used to generate the AnICA research artifact.
- [The pre-built artifact](https://doi.org/10.5281/zenodo.6818170) on Zenodo, including a Vagrant VM and a guide to reproduce our results.

## Maturity

This is a research prototype, expect things to break!


## Installation

These steps are for installing AnICA on its own. If you install AnICA as part
of the AnICA UI, follow the steps there instead of the ones here. In
particular, AnICA UI and AnICA should use the same virtual python environment.

Make sure that you have `llvm-mc` on your path (most likely by installing [LLVM](https://llvm.org/)).
It is used by the IWHO subcomponent (at `lib/iwho`) to handle basic instruction (dis)assembly tasks.
Furthermore, you need a python3 setup with the `venv` standard module available.

1. Get the repository and its submodule(s):
    ```
    git clone <repo> anica
    cd anica
    git submodule update --init --recursive
    ```
2. Set up the virtual environment for AnICA and install python dependencies and
   the AnICA package itself there:
   ```
   ./setup_venv.sh
   ```
   Whenever you run AnICA commands from a shell, you need to have activated
   the virtual environment in this shell before:
   ```
   source ./env/anica/bin/activate
   ```


## Generating Documentation

The API documentation can be built with [pdoc3](https://pdoc3.github.io/pdoc/).
After installing pdoc3 (`pip install pdoc3`) in the virtual environment, run the following command to generate html documentation in the `html` directory:
```
pdoc --html anica --force
```


## Usage
This section explains how several tasks that one might want to do with AnICA are done.
Every AnICA command has a `--help` option documenting its command line interface.

### Set up a Configuration Environment
There are a lot of things that can be configured on AnICA.
The first step is therefore to choose a fresh directory `$BASE_DIR` to house your AnICA configurations and to go there.
With a shell with the environment created during installation activated, run the following commands to create initial configuration files:
```
cd $BASE_DIR
anica-make-configs .
```
You will now find a `configs` sub directory, with three more subdirectories `abstraction`, `campaign`, and `predictors`.
Each contains at least one example file to configure an aspect of AnICA.

- The configurations in `campaign` each specify a series of AnICA campaigns.
  A campaign config refers to an abstraction config to be used and specifies the predictors under test as well as the termination criterion and whether only instructions that are supported by all predictors under test should be considered.
  Campaigns can terminate dependent on the number of discoveries made, on the passed time, or on the number of batches where no new discoveries were found.
  If multiple of these are specified, the first condition among them that is satisfied after a batch terminates the campaign.

- The `abstraction_config_path` field in the campaign config refers to a file in the `configs/abstraction` sub directory (relative paths that start with a `.` in any config file are interpreted relative to the config file).
  The abstraction configs in here describe how AnICA discovers and generalizes interesting basic blocks.
  There are numerous settings that are each described by a '.doc' field in the default file.

- An important field is the `registry_path` in the `predmanager` component of an abstraction config.
  It needs to point to a predictor registry that is located in the `configs/predictors` sub directory.
  Here, the available predictors are declared and configured.
  The default `pred_registry.json` only contains trivial test predictors, see (and copy+adjust from) the `pred_registry_template.json` for using actual predictors.
  The keys used here are the ones that are also used in the campaign config to refer to the predictors.

The next step is therefore to add and adjust relevant predictors to `configs/predictors/pred_registry.json`, with inspiration from `configs/predictors/pred_registry_template.json`.

Once all relevant predictors are specified in the `pred_registry.json`, you can generate filter files that contain all instructions that a predictor does not support (i.e. where it fails to produce a strictly positive cycle prediction):
```
anica-check-predictors -w --config abstraction/default.json
```
The corresponding files need to be specified beforehand in the `pred_registry.json`, if you follow the ones in the `pred_registry_template.json`, the filter files will be in `configs/predictors/filters/`.
They are used in AnICA if indicated so in the campaign config.


### Run AnICA Campaigns
Make sure that you are in your AnICA configuration environment and that the AnICA virtual environment is activated.
Then, choose (or adjust) a campaign configuration file in `./configs/campaign` (and, if necessary, the other config files it references) so that it specifies the campaign(s) you want to run.

Optionally, you can check your campaign config first:
```
anica-discover -c ./configs/campaign/<your-config>.json ./results/ --check-config
```
If successful, it estimates the time required for all campaigns that have a time-based termination condition.
The check-config command does create subdirectories in the specified `./results` directory, you might want to remove them before running the actual campaigns.

Finally, you can run your campaigns for real.
This can take a while (and, depending on your configuration, might never terminate).
```
anica-discover -c ./configs/campaign/<your-config>.json ./results/
```
The campaign results are written to subdirectories of the specified `./results` directory (or any other directory you specify).
You can now add metrics to them and import them to the AnICA UI for inspection.


### Generalize a Specific Basic Block
Make sure that you are in your AnICA configuration environment and that the AnICA virtual environment is activated.
Then, choose (or adjust) an abstraction configuration file in `./configs/abstraction` (and, if necessary, the other config files it references) so that it specifies the generalization parameters you want to use.

Write the basic block that you want to generalize in textual assembly form to a file.

Run the generalization as follows:
```
anica-generalize -c ./configs/abstraction/<your-config>.json -o ./results <your-asm-file>.s <first-predictor-key> <second-predictor-key>
```
The generalization results are written to subdirectories of the specified `./results` directory (or any other directory you specify).
You can now import them to the AnICA UI for inspection.

If you provide the `-i` flag, you enter the "text adventure mode", where you can interactively select which generalization steps should be performed.
Check `--help` for more possible arguments.


### Add a new Throughput Predictor Configuration
If you want to use a throughput predictor witha provided wrapper with new command line options, you just need to add a new entry to the json dict in `predictors/pred_registry.json` in your AnICA config environment with a suitable unique key.
You may take inspiration from the `predictors/pred_registry_template.json` template collection.

### Add a new Throughput Predictor
To evaluate a new throughput predictor, you need to implement a new wrapper for it in the `iwho.predictors` package.
Be sure to base your wrapper on one or more of the existing ones, and to add the new one to the available classes in `lib/iwho/iwho/predictors/__init__.py`.
Lastly, you need to add a corresponding entry to the predictor registry in your configuration environment.

### Add a new Feature Kind
If you want to expand AnICA to reason about new aspects of instruction schemes, you will need to add a new feature to the `InsnFeatureManager`.
It is located in the `anica.insnfeaturemanager` module.

You need to expand the `extract_feature` function there with a case that extracts the desired information from any given `InsnScheme`.

A shortcut for this implementation is possible if you only want to extract the feature from the uops.info xml file.
Then, you can just expand the `extract_features` function in `lib/iwho/scripts/scheme_extractor_uops_info.py` to add a value for the feature to the results dictionary (and regenerate the instruction schemes there with `lib/iwho/build_schemes.sh`).
The default case in the `InsnfeatureManager` tries to look up any unknown feature there.

With the `extract_feature` case in place, you can add an entry for the feature in the `insn_feature_manager.features` list in your abstraction configuration, and optionally also to the `_default_features` in the `anica.insnfeaturemanager` module.


### Add a new Feature Abstraction
If you want to expand AnICA with a new way of representing subsets of instruction schemes, you need to implement a new abstract feature.

Start by implementing a new subclass of `AbstractFeature` in `anica.abstractblock` (and feel free to take inspiration from the existing ones).
Additionally, you need to extend the `lookup()` and `init_abstract_features()` methods in the `InsnFeatureManager` (in the `anica.insnfeaturemanager` module).
The latter determines the interaction with `insn_feature_manager.features` entries in your abstraction config and needs to initialize an object of your `AbstractFeature` implementation.
The former queries for a set of `InsnScheme`s that match an instance of your `AbstractFeature`.
For decent performance, your `lookup` implementation should use an index whose construction you can implement in the `_build_index()` method.
Take inspiration from the documentation there and the existing abstract features.


## Directory Overview

* `./anica` - This directory contains the python modules that constitute the AnICA library.
  The most notable modules are `anica.discovery`, which contains the core algorithms, and `anica.abstractblock` containing the implementation of the basic block abstraction.

* `./tool` - This directory provides the entry-point python scripts to use AnICA.

* `./scripts` - Here are several more entry-point scripts for specific tasks in the development and evaluation of AnICA.

* `./configs` - Here are (default) files to configure the behavior of AnICA. It is recommended to not change them here, but to use an individual configuration environment created with the `anica-make-configs` command.

* `./lib` - This directory contains custom dependencies for AnICA.
  Specifically, this is the iwho library, which is used to work with instructions, instruction schemes, and basic blocks.

* `./tests` - This directory contains the testing for the AnICA module.
  Running the scripts in there should not yield unexpected failures.

* `./case_studies` - This directory contains some assembly files that trigger inconsistencies that AnICA found.

* `./setup_venv.sh` - This script sets up a python virtual environment at `./env/anica/` and installs AnICA's dependencies in it.
  Make sure to activate the environment with `source ./env/anica/bin/activate` when using any AnICA-related scripts.
  Using a virtual environment is not strictly necessary, but strongly recommended.

* `./requirements.txt` - This file lists required python modules for using AnICA. It can be installed using `pip3 -r requirements.txt` (which the `setup_venv.sh` script does, in a virtual environment).



