TODO write this

## TODO

### Key Functionality
  - [X] implement mechanism for dropping constraints
  - [X] implement the core generalization algorithm

### Functional Extensions
  - [X] replace the powerset domain for uop combinations with a subset domain of uops
  - [ ] make AbstractionConfig configurable
  - [ ] make AbstractionConfig less of a god class
  - [ ] AbstractBlock.sample needs some software engineering, probably extract the aliasing portion to its own class to make it more manageable
  - [ ] add a way of restricting the insn schemes provided by iwho.Context
  - [ ] make iwho.Context configurable
  - [ ] use "type signature" as an insn feature
  - [ ] revisit and adjust the aliasing assumptions in the AbstractionConfig
  - [ ] check whether using an SMT solver for subsumption is necessary and reasonable
  - [ ] look into sampling constraint solvers if sampling turns out to be an issue
  - [ ] add more predictors
    - [ ] Ithemal
    - [ ] DiffTune
    - [ ] OSACA
    - [ ] CQA?
    - [ ] measurements
  - [ ] a fancy witness exploration gui

### Meta Features
  - [ ] improve database scheme to make comparing measurements faster
  - [ ] make sampling deterministic (for the same seed)
  - [ ] profile running times of the components and check for bottlenecks
  - [ ] write this README
  - [ ] document everything


