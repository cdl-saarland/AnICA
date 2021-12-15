TODO write this

## Usage

TODO

## Design and Rationale

### Campaign Structure
A **campaign** is a run of the AnICA discovery algorithm for a (non-empty) set of basic block throughput predictors.

Each campaign is subdivided into **batches**.
In each batch, a fixed number of basic blocks (TODO option in the abstraction config) is sampled randomly.
Campaigns can only terminate (regularly) right after completly processing a batch.





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
  - [ ] write this README
  - [ ] document everything
  - [X] improve database scheme to make comparing measurements faster


