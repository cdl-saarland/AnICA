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
TODO

### Generalize a specific basic block
TODO

### Add a new Throughput Predictor
TODO

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
  The most notable modules are `discovery.py`, which contains the core algorithms, and `abstractblock.py` containing the implementation of the basic block abstraction.

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



## TODO List

### Key Functionality
  - [X] implement cost budgets or some other termination criterion
  - [X] implement mechanism for dropping constraints
  - [X] implement the core generalization algorithm

### Functional Extensions
  - [ ] at least for the insn part, we could rather easily sample from  gamma(new) \ gamma(old), maybe that's a good idea
  - [ ] think about making the required interesting ratio relative to the interestingness ratio of the current state (probably not a good idea, since it could lead to a decay of the result quality)
  - [ ] maybe relax the aliasing domain to be operand-position independent?
  - [ ] look into sampling constraint solvers if sampling turns out to be an issue
  - [X] add a discovery overview inspector
  - [X] add a satsumption implementation for comparing two abstract blocks (rather than a concrete and an abstract one)
  - [X] randomize generalization and try different randomizations per run
  - [X] add an "at most 2^k uops used (on SKL)" domain, "no info about uops used" should be right under top
  - [X] revisit the TODOs in the aliasing sampling
  - [X] omit obviously blocked insns from sampling
  - [X] slice witness traces without the optional instructions
  - [X] maybe give highest priority to the present feature and go to TOP in the absinsn once it is set to TOP
  - [X] check whether using an SMT solver for subsumption is necessary and reasonable
  - [X] make AbstractionConfig configurable
  - [X] make iwho.Context configurable
  - [X] implement an editdistance domain for mnemonics
  - [X] add a domain that can express that an instruction may not use memory / has to use memory
  - [X] test whether the aliasing component can find something
  - [X] make AbstractionConfig less of a god class
  - [X] AbstractBlock.sample needs some software engineering, probably extract the aliasing portion to its own class to make it more manageable
  - [X] add an ISA extension/category domain
  - [X] add a timeout to all predictor subprocess calls
  - [X] a fancy witness exploration gui
  - [X] add a way of restricting the insn schemes provided by iwho.Context
  - [X] replace the powerset domain for uop combinations with a subset domain of uops
  - [X] use "type signature" as an insn feature
  - [X] look into whether our discoveries cover also not-interesting samples
  - [X] revisit and adjust the aliasing assumptions in the AbstractionConfig
  - [X] add more predictors
    - [X] DiffTune
    - [X] CQA?
    - [X] measurements
    - [X] Ithemal
    - [X] OSACA

# Fancy Quality-of-Life Extensions
  - [ ] add mouseover hints in the gui that explain the meaning of components of the abstract blocks
  - [ ] add js functions to generate a running script for each test case
  - [ ] make `llvm-mc` findable for iwho

### Meta Features
  - [ ] make sampling deterministic (for the same seed)
  - [ ] profile running times of the components and check for bottlenecks
  - [ ] document everything
  - [X] write this README
  - [X] improve database scheme to make comparing measurements faster


