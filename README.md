TODO write this

## TODO

### Key Functionality
  - [ ] implement cost budgets or some other termination criterion
  - [X] implement mechanism for dropping constraints
  - [X] implement the core generalization algorithm

### Functional Extensions
  - [ ] add a domain that can express that an instruction may not use memory / has to use memory
  - [ ] test whether the aliasing component can find something
  - [ ] revisit the TODOs in the aliasing sampling
  - [ ] add mouseover hints in the gui that explain the meaning of components of the abstract blocks
  - [ ] make AbstractionConfig configurable
  - [ ] make AbstractionConfig less of a god class
  - [ ] AbstractBlock.sample needs some software engineering, probably extract the aliasing portion to its own class to make it more manageable
  - [ ] make iwho.Context configurable
  - [ ] revisit and adjust the aliasing assumptions in the AbstractionConfig
  - [ ] check whether using an SMT solver for subsumption is necessary and reasonable
  - [ ] add more predictors
    - [ ] Ithemal
    - [ ] DiffTune
    - [ ] OSACA
    - [ ] CQA?
    - [ ] measurements
  - [ ] look into sampling constraint solvers if sampling turns out to be an issue
  - [X] add an ISA extension/category domain
  - [X] add a timeout to all predictor subprocess calls
  - [X] a fancy witness exploration gui
  - [X] add a way of restricting the insn schemes provided by iwho.Context
  - [X] replace the powerset domain for uop combinations with a subset domain of uops
  - [X] use "type signature" as an insn feature

### Meta Features
  - [ ] make sampling deterministic (for the same seed)
  - [ ] profile running times of the components and check for bottlenecks
  - [ ] write this README
  - [ ] document everything
  - [X] improve database scheme to make comparing measurements faster


