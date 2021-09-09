""" This file provides classes to represent abstractions of basic blocks, i.e.
representations of sets of 'conrete' basic blocks.

Those abstractions have methods to sample from the represented concrete blocks,
as well as ways to systematically extend the set of represented concrete
blocks.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy, copy
from enum import Enum
import itertools
import math
import random
import textwrap
from typing import Optional, Union, Sequence

import editdistance
import iwho

from .configurable import store_json_config

import logging
logger = logging.getLogger(__name__)

class SamplingError(Exception):
    """ Something went wrong with sampling
    """

    def __init__(self, message):
        super().__init__(message)

# TODO document json funcitonality, mention that acfg.introduce_json_references
# and acfg.resolve_json_references should be used

class Expandable(ABC):
    """Abstract base class for objects representing an element of a partially
    ordered set with methods to expand the object, i.e. to change it to an
    element that is larger.
    """

    @abstractmethod
    def get_possible_expansions(self):
        """ Return a list of possible expansions for `apply_expansion()`.

        The list contains tuples of an expansion and a value that corresponds
        to its estimated benefit in the amount of freedom that it would give
        the sampling.
        """

        pass

    @abstractmethod
    def apply_expansion(self, expansion):
        """ Apply an expansion from `get_possible_expansions()`. """
        pass

class AbstractFeature(Expandable, ABC):
    """ Abstract base class for the most atomic abstraction component.

    Several of these are used to abstract instructions and aliasing relations.
    """
    class SpecialValue(Enum):
        """ Special values for minimal and maximal values that may be used in
        implementations of this interface.
        """
        BOTTOM=0
        TOP=1

        def __str__(self):
            return str(self.name)

    BOTTOM = SpecialValue.BOTTOM
    TOP = SpecialValue.TOP

    @abstractmethod
    def __deepcopy__(self, memo):
        pass

    @abstractmethod
    def to_json_dict(self):
        pass

    @abstractmethod
    def is_top(self) -> bool:
        pass

    @abstractmethod
    def is_bottom(self) -> bool:
        pass

    @abstractmethod
    def set_to_top(self):
        pass

    @abstractmethod
    def subsumes(self, other: "AbstractFeature") -> bool:
        pass

    @abstractmethod
    def subsumes_feature(self, feature) -> bool:
        pass

    @abstractmethod
    def join(self, feature):
        pass

class EditDistanceAbstractFeature(AbstractFeature):
    def __init__(self, max_dist):
        self.top = False
        self.base = None
        self.curr_dist = 0
        self.max_dist = max_dist

    def __eq__(self, other):
        if not isinstance(other, EditDistanceAbstractFeature):
            return False
        return self.top == other.top and self.base == other.base and self.curr_dist == other.curr_dist

    def __hash__(self):
        return hash((self.top, self.base, self.curr_dist))

    def _normalize(self):
        if not self.top and self.curr_dist > self.max_dist:
            self.set_to_top()

    def __deepcopy__(self, memo):
        new_one = EditDistanceAbstractFeature(max_dist=self.max_dist)
        new_one.top = self.top
        new_one.base = self.base # no need to copy at all
        new_one.curr_dist = self.curr_dist
        return new_one

    def to_json_dict(self):
        return {
                'top': self.top,
                'base': self.base,
                'curr_dist': self.curr_dist,
                'max_dist': self.max_dist,
            }

    @staticmethod
    def from_json_dict(json_dict):
        res = EditDistanceAbstractFeature(max_dist=json_dict['max_dist'])
        res.top = json_dict['top']
        res.base = json_dict['base']
        res.curr_dist = json_dict['curr_dist']
        return res

    def __str__(self) -> str:
        if self.is_top():
            return "TOP"
        if self.is_bottom():
            return "BOTTOM"
        return f"'{self.base}' + at most {self.curr_dist} edits"

    def get_possible_expansions(self):
        if self.is_top():
            return []
        return [(self.curr_dist + 1, 0)]

    def apply_expansion(self, expansion):
        self.curr_dist = expansion
        self._normalize()

    def is_top(self) -> bool:
        return self.top

    def is_bottom(self) -> bool:
        return not self.top and self.base is None

    def set_to_top(self):
        self.top = True
        self.base = None
        self.curr_dist = None

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, EditDistanceAbstractFeature)
        # that's an approximation
        return self.is_top() or other.is_bottom() or (self.base == other.base
                and self.curr_dist >= other.curr_dist)

    def subsumes_feature(self, feature) -> bool:
        assert False, "not yet implemented"

    def join(self, feature):
        if feature is None:
            return
        if self.is_top():
            return
        if self.is_bottom():
            self.base = feature
            self.curr_dist = 0
            return
        if self.base != feature:
            d = editdistance.eval(self.base, feature)
            if d > self.curr_dist:
                self.curr_dist = d
                self._normalize()
        return


class LogUpperBoundAbstractFeature(AbstractFeature):
    def __init__(self, max_ub):
        self.val = AbstractFeature.BOTTOM
        self.max_ub = max_ub

    def __eq__(self, other):
        if not isinstance(other, LogUpperBoundAbstractFeature):
            return False
        return self.val == other.val

    def __hash__(self):
        return hash(self.val)

    def __deepcopy__(self, memo):
        new_one = LogUpperBoundAbstractFeature(max_ub=self.max_ub)
        new_one.val = self.val
        return new_one

    def to_json_dict(self):
        return {
                'val': self.val,
                'max_ub': self.max_ub,
            }

    @staticmethod
    def from_json_dict(json_dict):
        res = LogUpperBoundAbstractFeature(max_ub=json_dict['max_ub'])
        res.val = json_dict['val']
        return res

    def __str__(self) -> str:
        if self.is_top():
            return "TOP"
        if self.is_bottom():
            return "BOTTOM"
        return f"at most {2**self.val - 1}"

    def get_possible_expansions(self):
        if self.is_top():
            return []
        if self.is_bottom() or self.val >= self.max_ub:
            return [(AbstractFeature.TOP, 0)]
        return [(self.val + 1, 0)]

    def apply_expansion(self, expansion):
        self.val = expansion

    def is_top(self) -> bool:
        return self.val == AbstractFeature.TOP

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def set_to_top(self):
        self.val = AbstractFeature.TOP

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, LogUpperBoundAbstractFeature)
        return self.is_top() or other.is_bottom() or (self.val >= other.val)

    def subsumes_feature(self, feature) -> bool:
        assert False, "not yet implemented"

    def join(self, feature):
        if feature is None:
            self.set_to_top() # TODO this might be inconsistent...
            return
        if self.is_top():
            return
        log_feature = math.floor(math.log2(len(feature) + 1))
        if self.is_bottom():
            self.val = log_feature
            return
        self.val = max(self.val, log_feature)
        return


class SingletonAbstractFeature(AbstractFeature):
    def __init__(self):
        self.val = AbstractFeature.BOTTOM

    def __eq__(self, other):
        if not isinstance(other, SingletonAbstractFeature):
            return False
        return self.val == other.val

    def __hash__(self):
        return hash(self.val)

    def __deepcopy__(self, memo):
        new_one = SingletonAbstractFeature()
        new_one.val = self.val # no need to copy at all
        return new_one

    def to_json_dict(self):
        return self.val

    @staticmethod
    def from_json_dict(json_dict):
        res = SingletonAbstractFeature()
        res.val = json_dict
        return res

    def __str__(self) -> str:
        return str(self.val)

    def get_possible_expansions(self):
        if self.is_top():
            return []
        return [(AbstractFeature.TOP, 0)]

    def apply_expansion(self, expansion):
        self.val = expansion

    def is_top(self) -> bool:
        return self.val == AbstractFeature.TOP

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def get_val(self):
        if isinstance(self.val, AbstractFeature.SpecialValue):
            return None
        else:
            return self.val

    def set_to_top(self):
        self.val = AbstractFeature.TOP

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SingletonAbstractFeature)
        return (self.val == other.val or
                other.val == AbstractFeature.BOTTOM or
                self.val == AbstractFeature.TOP)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_top():
            return True
        if self.is_bottom():
            return False
        return self.val == feature

    def join(self, feature):
        if feature is None:
            return
        if self.is_top():
            return
        if self.is_bottom():
            self.val = feature
            return
        if self.val != feature:
            self.set_to_top()
        return


class SubSetAbstractFeature(AbstractFeature):
    """ Represents all sets of items that are a (non-strict) superset of
    self.val.
    """
    def __init__(self):
        self.val = AbstractFeature.BOTTOM

    def __eq__(self, other):
        if not isinstance(other, SubSetAbstractFeature):
            return False
        return self.val == other.val

    def __hash__(self):
        if isinstance(self.val, set):
            return hash(frozenset(self.val))
        else:
            return hash(self.val)

    def __deepcopy__(self, memo):
        new_one = SubSetAbstractFeature()
        new_one.val = copy(self.val) # no need to deepcopy
        return new_one

    def to_json_dict(self):
        if self.is_bottom():
            return self.val
        return tuple(self.val)

    @staticmethod
    def from_json_dict(json_dict):
        res = SubSetAbstractFeature()
        if isinstance(json_dict, AbstractFeature.SpecialValue):
            res.val = json_dict
        else:
            assert isinstance(json_dict, list) or isinstance(json_dict, tuple)
            res.val = set(json_dict)
        return res

    def get_possible_expansions(self):
        if self.is_top():
            return []
        if self.is_bottom():
            return [(AbstractFeature.TOP, 0)]
        res = []
        for v in self.val:
            res.append((v, 1))
        return res

    def apply_expansion(self, expansion):
        if expansion == AbstractFeature.TOP:
            self.set_to_top()
            return
        self.val.remove(expansion)

    def __str__(self) -> str:
        if self.is_bottom():
            return "BOTTOM"
        if self.is_top():
            return "TOP"
        return "{" + ", ".join(sorted(map(str, self.val))) + "}"

    def is_top(self) -> bool:
        return (not self.is_bottom()) and len(self.val) == 0

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def set_to_top(self):
        self.val = set()

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SubSetAbstractFeature)
        if other.is_bottom():
            return True
        if self.is_bottom():
            return False
        return self.val.issubset(other.val)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_bottom():
            return False
        return self.val.issubset(set(feature))

    def join(self, feature):
        if feature is not None:
            if self.is_bottom():
                self.val = set(feature)
            else:
                self.val.intersection_update(feature)


class SubSetOrDefinitelyNotAbstractFeature(AbstractFeature):
    r""" An abstract domain for representing all sets of items that are a
    (non-strict) superset of a set of feature values and the set of items where
    no feature value applies.

    Intended for things like this:

                                   +-----+
                                   | TOP |
                                   +-----+
                                  /       \
                   +-------------+         \
                   | definitely  |          \
                   | uses memory |           +-----+
                   +-------------+                  \
                  /       |       \                  \
         +--------+  +----------+  +--------+       +--------------+
         | reads  |  | accesses |  | writes |       | does not use |
         | memory |  |  k bits  |  | memory |       |    memory    |
         +--------+  +----------+  +--------+       +--------------+
           |    \    /    |     \     /   |               |
           |     +==+     |      +===+    |               |
           |    /    \    |     /     \   |               |
 +--------------+ +----------------+ +---------------+    |
 | reads k bits | | reads & writes | | writes k bits |    |
 |  of memory   | |     memory     | |   of memory   |    |
 +--------------+ +----------------+ +---------------+    +
                \         |         /                    /
                +------------------+                    /
                |  reads & writes  |              +----+
                | k bits of memory |             /
                +------------------+            /
                                    \          /
                                     +--------+
                                     | BOTTOM |
                                     +--------+
    """

    def __init__(self):
        self.subfeature = SubSetAbstractFeature()

        self.is_in_subfeature = SingletonAbstractFeature()

    def __eq__(self, other):
        if not isinstance(other, SubSetOrDefinitelyNotAbstractFeature):
            return False
        return self.subfeature == other.subfeature and self.is_in_subfeature == other.is_in_subfeature

    def __hash__(self):
        return hash((self.subfeature, self.is_in_subfeature))

    def __deepcopy__(self, memo):
        new_one = self.__class__()
        new_one.subfeature = deepcopy(self.subfeature, memo)
        new_one.is_in_subfeature = deepcopy(self.is_in_subfeature, memo)
        return new_one

    def to_json_dict(self):
        return {
                "subfeature": self.subfeature.to_json_dict(),
                "is_in_subfeature": self.is_in_subfeature.to_json_dict(),
            }

    @staticmethod
    def from_json_dict(json_dict):
        res = SubSetOrDefinitelyNotAbstractFeature()
        res.subfeature = SubSetAbstractFeature.from_json_dict(json_dict['subfeature'])
        res.is_in_subfeature = SingletonAbstractFeature.from_json_dict(json_dict['is_in_subfeature'])
        return res

    def get_possible_expansions(self):
        if self.is_top():
            return []
        if self.is_bottom() or self.is_in_subfeature.val == False or self.subfeature.is_top():
            return [(AbstractFeature.TOP, 0)]

        return self.subfeature.get_possible_expansions()

    def apply_expansion(self, expansion):
        if expansion == AbstractFeature.TOP:
            self.set_to_top()
            return
        self.subfeature.apply_expansion(expansion)

    def __str__(self) -> str:
        if self.is_bottom():
            return "BOTTOM"
        if self.is_top():
            return "TOP"
        if self.is_in_subfeature.val == True:
            if self.subfeature.is_top():
                return "definitely something"
            return "at least " + str(self.subfeature)
        assert self.is_in_subfeature.val == False
        return "definitely not"

    def is_top(self) -> bool:
        return self.is_in_subfeature.is_top()

    def is_bottom(self) -> bool:
        return self.is_in_subfeature.is_bottom()

    def set_to_top(self):
        self.is_in_subfeature.set_to_top()
        self.subfeature.set_to_top()

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, self.__class__)
        if other.is_bottom():
            return True
        if self.is_bottom():
            return False
        if self.is_top():
            return True
        if other.is_top():
            return False

        if self.is_in_subfeature.val == False:
            return other.is_in_subfeature.val == False

        if self.is_in_subfeature.val == True and other.is_in_subfeature.val == False:
            return False

        assert self.is_in_subfeature.val == True and other.is_in_subfeature.val == True

        return self.subfeature.subsumes(other.subfeature)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_bottom():
            return False
        if self.is_top():
            return True

        if self.is_in_subfeature.val == False:
            return len(feature) == 0

        return self.subfeature.subsumes_feature(feature)

    def join(self, feature):
        if feature is not None:
            if len(feature) == 0:
                self.is_in_subfeature.join(False)
                self.subfeature.set_to_top()
            else:
                self.is_in_subfeature.join(True)
                self.subfeature.join(feature)

class AbstractInsn(Expandable):
    """ An instance of this class represents a set of (concrete) InsnSchemes
    that share certain features.
    """

    def __init__(self, actx: "AbstractionContext"):
        self.actx = actx
        self.features = actx.insn_feature_manager.init_abstract_features()

    def __eq__(self, other):
        if not isinstance(other, AbstractInsn):
            return False
        return self.features == other.features

    def __hash__(self):
        return hash(frozenset(self.features.items()))

    def __deepcopy__(self, memo):
        new_one = AbstractInsn(self.actx)
        new_one.features = deepcopy(self.features, memo)
        return new_one

    def to_json_dict(self):
        res = dict()
        for k, v in self.features.items():
            res[k] = v.to_json_dict()
        return res

    @staticmethod
    def from_json_dict(actx, json_dict):
        res = AbstractInsn(actx)
        init_features = res.features
        assert set(init_features.keys()) == set(json_dict.keys())
        json_features = dict()
        for k, v in json_dict.items():
            cls = type(init_features[k])
            json_features[k] = cls.from_json_dict(v)
        res.features = json_features
        return res

    def __str__(self) -> str:
        if all(map(lambda x: x[1].is_top(), self.features.items())):
            return "TOP"
        return "\n".join((f"{k}: {v}" for k, v in self.features.items()))

    def havoc(self):
        for k, v in self.features.items():
            v.set_to_top()

    def is_top(self):
        return all(map(lambda x: x[1].is_top(), self.features.items()))

    def compute_benefit(self, expansion):
        """ Compute the increase in fitting insn schemes if we would apply this
        `expansion` (as a ratio (len(fitting_after) / len(fitting_before))).

        This should always be >= 1 (since expansions should only expand, i.e.
        allow for more insn schemes).
        """
        num_prev_feasible_schemes = len(self.actx.insn_feature_manager.compute_feasible_schemes(self.features))

        assert num_prev_feasible_schemes > 0, "Computing benefit for an AbstractInsn without feasible schemes!"

        absfeature_dict = { k: v for k, v in self.features.items() }

        replace_k, inner_expansion = expansion
        replace_feature = deepcopy(self.features[replace_k])
        replace_feature.apply_expansion(inner_expansion)
        absfeature_dict[replace_k] = replace_feature

        feasible_schemes = self.actx.insn_feature_manager.compute_feasible_schemes(absfeature_dict)
        return len(feasible_schemes) / num_prev_feasible_schemes

    def get_possible_expansions(self):
        exact_scheme_entry = self.features.get('exact_scheme', None)
        if exact_scheme_entry is not None and not exact_scheme_entry.is_top():
            # The exact scheme is more specific than the other features (it
            # implies all of them). It is therefore pointless and harmful to
            # expand another feature first, as it will not affect the sampling
            # at all, but might very well lead to a situation where expanding
            # the scheme later on will no longer be allowed.
            # An alternative, more general way of dealing with this (also for
            # other co-dependent features) would be to join the original with
            # the sampled experiments rather than using the expanded abstract
            # block, or to make sure that blocks not covered by the original
            # block are sampled.
            expansion = ('exact_scheme', AbstractFeature.TOP)
            benefit = self.compute_benefit(expansion)
            return [(expansion, benefit)]

        res = []
        for key, af in self.features.items():
            for inner_expansion, benefit in af.get_possible_expansions():
                expansion = (key, inner_expansion)
                benefit = self.compute_benefit(expansion)
                res.append((expansion, benefit))
        return res

    def apply_expansion(self, expansion):
        key, inner_expansion = expansion
        self.features[key].apply_expansion(inner_expansion)

    def subsumes(self, other: "AbstractInsn") -> bool:
        """ Check if all concrete instruction instances represented by other
        are also represented by self.
        """
        for k, abs_feature in self.features.items():
            other_feature = other.features[k]
            if not abs_feature.subsumes(other_feature):
                return False

        return True

    def join(self, insn_scheme: Union[iwho.InsnScheme, None]):
        """ Update self so that it additionally represents all instances of
        insn_scheme (and possibly, due to over-approximation, even more
        insn instances).

        If insn_scheme is None, the instruction is considered "not present" in
        the basic block.
        """

        insn_features = self.actx.insn_feature_manager.extract_features(insn_scheme)

        for k, v in insn_features.items():
            self.features[k].join(v)

    def sample(self, insn_scheme_blacklist: Sequence[iwho.InsnScheme]=[]) -> iwho.InsnScheme:
        """ Randomly choose one from the set of concrete instruction schemes
        represented by this abstract instruction.

        No scheme from the insn_scheme_blacklist will be chosen.
        """
        feasible_schemes = self.actx.insn_feature_manager.compute_feasible_schemes(self.features)

        feasible_schemes.difference_update(insn_scheme_blacklist)

        if len(feasible_schemes) == 0:
            raise SamplingError(f"No InsnScheme is feasible for AbstractInsn {self}")
        return random.choice(tuple(feasible_schemes))

    def precompute_sampler(self, insn_scheme_blacklist: Sequence[iwho.InsnScheme]=[]):
        feasible_schemes = self.actx.insn_feature_manager.compute_feasible_schemes(self.features)
        feasible_schemes.difference_update(insn_scheme_blacklist)

        if len(feasible_schemes) == 0:
            raise SamplingError(f"No InsnScheme is feasible for AbstractInsn {self}")
        return PrecomputedSamplerAbsInsn(feasible_schemes)

def _lists2tuples(obj):
    if isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(( _lists2tuples(x) for x in obj ))
    return obj


class AbstractAliasInfo(Expandable):
    """ An object of this class represents the aliasing relationships between
    (operands of) instructions of a basic block.
    """

    def __init__(self, actx):
        self.actx = actx
        # A mapping from pairs of (instruction index, operand index) pairs to a
        # boolean SingletonAbstractFeature.
        # An entry for (op1, op2) means "if op1 and op2 allow for aliasing,
        # then {they alias, they don't alias, anything goes}.
        self._aliasing_dict = dict()

        # The semantics of entries not present in the above map changes over
        # the lifetime of the Abstraction, through the value of the following
        # flag. In the beginning, before any concrete Block is joined in,
        # nothing will be present, which should be interpreted as a BOTTOM
        # value for everything. When joining the first concrete Block in, the
        # map gets entries for all the observed relationships, and any
        # non-present relationship that might be encountered later should be
        # considered TOP.
        # In a valid state, an object of this class with entries in the
        # _aliasing_dict will have is_bot set to False.
        self.is_bot = True

    def __eq__(self, other):
        if not isinstance(other, AbstractAliasInfo):
            return False
        return self.is_bot == other.is_bot and self._aliasing_dict == other._aliasing_dict

    def __hash__(self):
        return hash((self.is_bot, frozenset(self._aliasing_dict.items())))

    def to_json_dict(self):
        res = dict()
        res['aliasing_dict'] = [ (k, x.to_json_dict()) for k, x in self._aliasing_dict.items() ]
        res['is_bot'] = self.is_bot
        return res

    @staticmethod
    def from_json_dict(actx, json_dict):
        res = AbstractAliasInfo(actx)
        aliasing = dict()
        for k, v in json_dict['aliasing_dict']:
            key = _lists2tuples(k)
            aliasing[key] = SingletonAbstractFeature.from_json_dict(v)
        res._aliasing_dict = aliasing
        res.is_bot = json_dict['is_bot']
        return res

    def __deepcopy__(self, memo):
        new_one = AbstractAliasInfo(self.actx)
        new_one._aliasing_dict = { k: deepcopy(v, memo) for k, v in self._aliasing_dict.items() } # no need to duplicate the keys here
        new_one.is_bot = self.is_bot
        return new_one

    def get_possible_expansions(self):
        """ Implements Expandable """
        res = []

        for key, av in self._aliasing_dict.items():
            for inner_expansion, benefit in av.get_possible_expansions():
                expansion = (key, inner_expansion)
                res.append((expansion, benefit))

        return res

    def apply_expansion(self, expansion):
        """ Implements Expandable """
        key, inner_expansion = expansion
        av = self._aliasing_dict[key]
        av.apply_expansion(inner_expansion)

    def get_component(self, idx1, idx2):
        """ Obtain (and create if necessary) an AbstractFeature for the given
        pair of instruction/operand indices. The order of idx1 and idx2 does
        not matter.
        """
        key = tuple(sorted((idx1, idx2)))
        res = self._aliasing_dict.get(key, None)
        if res is None and self.is_bot:
            res = SingletonAbstractFeature()
            self._aliasing_dict[key] = res
        return res

    def do_compaction(self):
        """ If self is not BOTTOM: clear explicit TOP components from the dict,
        as non-present entries are considered TOP anyway.
        """
        if self.is_bot:
            return
        new_aliasing = { k: v  for k, v in self._aliasing_dict.items() if not v.is_top() }
        self._aliasing_dict = new_aliasing

    def __str__(self) -> str:
        entries = []
        for ((iidx1, oidx1), (iidx2,oidx2)), absval in self._aliasing_dict.items():
            if absval.is_top():
                # skip TOP entries, as they make the output quite large
                continue
            elif absval.is_bottom():
                valtxt = "BOTTOM"
            elif absval.val is False:
                valtxt = "must not alias"
            elif absval.val is True:
                valtxt = "must alias"
            else:
                assert False
            entries.append(f"{iidx1}:{oidx1} - {iidx2}:{oidx2} : {valtxt}")

        entries.sort()
        return "\n".join(entries)

    def subsumes(self, other: "AbstractAliasInfo") -> bool:
        """ Check whether self subsumes all aliasing relationships represented
        by other.
        """

        if other.is_bot:
            return True

        if self.is_bot:
            return False

        # all items not present are considered TOP and subsume everything
        for k, sv in self._aliasing_dict.items():
            if sv.is_top():
                continue
            ov = other._aliasing_dict.get(k, None)
            if ov is None or not sv.subsumes(ov):
                return False

        return True

    def join(self, bb):
        """ Update self so that it additionally represents at least the
        aliasing of bb.
        """
        bb_insns = list(bb.insns)

        # identify all operand indices in bb that we care about
        all_indices = []
        for insn_idx, ii in enumerate(bb_insns):
            if ii is None:
                continue
            for operand, (op_key, op_scheme) in ii.get_operands():
                if self.actx.iwho_augmentation.skip_for_aliasing(op_scheme):
                    continue
                idx = (insn_idx, op_key)
                all_indices.append((idx, operand))

        # for each combination of such operand indices, update the
        # corresponding entry in the dict
        for (idx1, op1), (idx2, op2) in itertools.combinations(all_indices, 2):
            ad = self.get_component(idx1, idx2)
            if ad is None or ad.is_top():
                continue

            # if operand schemes are not compatible, this entry is ignored
            op_scheme1 = bb_insns[idx1[0]].scheme.get_operand_scheme(idx1[1])
            op_scheme2 = bb_insns[idx2[0]].scheme.get_operand_scheme(idx2[1])
            if not self.actx.iwho_augmentation.is_compatible(op_scheme1, op_scheme2):
                if ad.is_bottom():
                    # This is to avoid bottom entries for incompatible operand
                    # combinations when initializing. Those would not be
                    # unsound, but they are pointless and cause work.
                    ad.set_to_top()
                continue

            if self.actx.iwho_augmentation.must_alias(op1, op2):
                ad.join(True)
            elif not self.actx.iwho_augmentation.may_alias(op1, op2):
                ad.join(False)
            else:
                ad.set_to_top()

        # if this is the first join, this switches the interpretation of
        # non-present entries in the abs_aliasing dict.
        self.is_bot = False

        # components could have gone to TOP, we don't need them in the dict
        self.do_compaction()

    def is_top(self):
        return (not self.is_bot) and all(map(lambda x: x[1].is_top(), self._aliasing_dict.items()))

    def havoc(self):
        """Clear all constraints."""
        self.is_bot = False
        self._aliasing_dict = dict()

    def _compute_partitions(self, insn_schemes: Sequence[iwho.InsnScheme]):
        """ Extract aliasing constraints into a more workable form.

        Returns two mappings from op_indices to sets of op_indices: (same, not_same)
          - same is a mapping from instruction operands to sets of instruction
            operands with which they should alias
          - not_same is a mapping from instruction operands to sets of
            instruction operands with which they should not alias

        Helper function for sampling.
        """
        same = defaultdict(set)
        not_same = defaultdict(set)

        for (insn_op1, insn_op2), should_alias in self._aliasing_dict.items():
            iidx1, op_key1 = insn_op1
            iidx2, op_key2 = insn_op2
            # Do not enter information for operands that are not present.
            op_scheme1 = insn_schemes[iidx1].get_operand_scheme(op_key1)
            op_scheme2 = insn_schemes[iidx2].get_operand_scheme(op_key2)
            if (op_scheme1 is None or op_scheme2 is None):
                continue

            if (self.actx.iwho_augmentation.skip_for_aliasing(op_scheme1) or
                    self.actx.iwho_augmentation.skip_for_aliasing(op_scheme1)):
                # we also don't want this information if we skip the operand scheme
                continue

            # if operand schemes are not compatible, this entry is ignored
            if not self.actx.iwho_augmentation.is_compatible(op_scheme1, op_scheme2):
                continue

            if should_alias.val is True:
                same[insn_op1].add(insn_op2)
                same[insn_op2].add(insn_op1)
            elif should_alias.val is False:
                not_same[insn_op1].add(insn_op2)
                not_same[insn_op2].add(insn_op1)

        return same, not_same

    def _choose_fixed_operands(self, chosen_operands, insn_schemes, same, not_same):
        """ Go through all insn_schemes and pin each fixed operand.

        Results are entered into the chosen_operands dict, which is also
        returned.

        Helper function for sampling.
        """
        ctx = self.actx.iwho_ctx

        for iidx, ischeme in enumerate(insn_schemes):
            for op_key, op_scheme in ischeme.operand_keys:
                if self.actx.iwho_augmentation.skip_for_aliasing(op_scheme) or not op_scheme.is_fixed():
                    continue
                idx = (iidx, op_key)
                fixed_op = op_scheme.fixed_operand

                # Check if an earlier choice already implies an operand here.
                prev_choice = chosen_operands.get(idx, None)
                if prev_choice is not None:
                    if prev_choice != fixed_op:
                        raise SamplingError(f"InsnScheme {ischeme} requires different operands for {op_key} from aliasing with fixed operands: {prev_choice} and {fixed_op}")
                    else:
                        # No need to go through the same dict, they have been
                        # set when the prev_choice was set.
                        continue

                # choose the fixed operand
                chosen_operands[idx] = fixed_op

                # for all operands that are supposed to alias, choose an
                # appropriate operand as well
                for k in same[idx]:
                    # try to find an adjusted version of the fixed operand that
                    # works for this operand (usually, this would do nothing or
                    # change the operand width).
                    adjusted_fixed_op = ctx.adjust_operand(fixed_op, insn_schemes[k[0]].get_operand_scheme(k[1]))
                    if adjusted_fixed_op is None:
                        raise SamplingError(f"InsnScheme {insn_schemes[k[0]]} requires an incompatible operand for {k[1]} from aliasing with a fixed operand: {fixed_op}")

                    # Check if an earlier choice already implies an operand here.
                    prev_choice = chosen_operands.get(k, None)
                    if prev_choice is not None and not self.actx.iwho_augmentation.must_alias(prev_choice, adjusted_fixed_op):
                        raise SamplingError(f"InsnScheme {insn_schemes[k[0]]} requires different operands for {k[1]} from aliasing with fixed operands: {prev_choice} and {adjusted_fixed_op}")

                    chosen_operands[k] = adjusted_fixed_op

        # Validate that we don't violate a must-not-alias constraint.
        # If we did, those InsnSchemes are not suitable for sampling with this
        # aliasing info.
        for k, v in chosen_operands.items():
            for nk in not_same[k]:
                nv = chosen_operands.get(nk)
                if nv is None:
                    continue
                if self.actx.iwho_augmentation.may_alias(v, nv):
                    raise SamplingError(f"Fixed operand requirements violate an aliasing constraint: operand {k[1]} of {insn_schemes[k[0]]} and operand {nk[1]} of {insn_schemes[nk[0]]} may not alias.")

        return chosen_operands

    def _choose_remaining_operands(self, chosen_operands, insn_schemes, same, not_same):
        """ Choose/sample fitting operands for the insn_schemes that are not
        yet specified by chosen_operands.

        The result is entered into chosen_operands, which is also returned.

        Helper function for sampling.
        """
        # in here, backtracking would be necessary

        ctx = self.actx.iwho_ctx

        for iidx, ischeme in enumerate(insn_schemes):
            for op_key, op_scheme in ischeme.operand_keys:
                idx = (iidx, op_key)
                # we already chose an operand here
                if chosen_operands.get(idx, None) is not None:
                    continue

                allowed_operands = set(self.actx.iwho_augmentation.allowed_operands(op_scheme))
                if not self.actx.iwho_augmentation.skip_for_aliasing(op_scheme):

                    # collect all opschemes that need to have an aliasing
                    # operand and collect all already selected operands that
                    # are not allowed to alias
                    same_opschemes = []
                    notsame_operands = set()
                    for k in itertools.chain((idx,), same[idx]):
                        same_opschemes.append(insn_schemes[k[0]].get_operand_scheme(k[1]))

                        for inner_k in not_same[k]:
                            already_chosen = chosen_operands.get(inner_k, None)
                            if already_chosen is not None:
                                notsame_operands.add(already_chosen)

                    # Remove operands that can't be used in all `same` operands
                    ruled_out_by_same_constraints = []
                    for ao in allowed_operands:
                        for curr_opscheme in same_opschemes:
                            ao_adjusted = ctx.adjust_operand(ao, curr_opscheme)
                            if ao_adjusted is None:
                                ruled_out_by_same_constraints.append(ao)
                    allowed_operands.difference_update(ruled_out_by_same_constraints)

                    # Remove operands that are already used as `notsame` operands
                    ruled_out_by_notsame_constraints = []
                    for ao in allowed_operands:
                        for curr_operand in notsame_operands:
                            if self.actx.iwho_augmentation.may_alias(ao, curr_operand):
                                ruled_out_by_notsame_constraints.append(ao)
                    allowed_operands.difference_update(ruled_out_by_notsame_constraints)

                if len(allowed_operands) == 0:
                    raise SamplingError(f"InsnScheme {ischeme} has no allowed operands left for operand '{op_key}' ({op_scheme})")

                # choose one from the allowed_operands
                chosen = random.choice(list(allowed_operands))
                chosen_operands[idx] = chosen

                if not self.actx.iwho_augmentation.skip_for_aliasing(op_scheme):
                    # also choose this one for the entries in the same set
                    # If the same/not_same sets do not describe a valid
                    # partition, this could ignore an inconsistent constraint.
                    for k in same[idx]:
                        chosen_operand = ctx.adjust_operand(chosen, insn_schemes[k[0]].get_operand_scheme(k[1]))
                        assert chosen_operand is not None, "This should have been ruled out by the above `ruled_out_by_` code!"
                        chosen_operands[k] = chosen_operand

        return chosen_operands

    def sample(self, insn_schemes: Sequence[iwho.InsnScheme]) -> iwho.BasicBlock:
        """ Instantiate the given list of InsnSchemes with operands such that
        the aliasing constraints represented by self are not violated.

        Raises a SamplingError if this fails (which might happen due to
        contradicting constraints or because this implementation does not
        backtrack wrong sampling decisions).
        """
        if self.is_bot:
            raise SamplingError(f"Trying to sample a basic block with BOTTOM as aliasing information")

        # for each operand, determine which operands should and which ones
        # shouldn't alias
        same, not_same = self._compute_partitions(insn_schemes)

        chosen_operands = dict()

        # go through all insn_schemes and pin each fixed operand
        chosen_operands = self._choose_fixed_operands(chosen_operands, insn_schemes, same, not_same)

        # remaining unchosen operands are not determined by fixed operands
        chosen_operands = self._choose_remaining_operands(chosen_operands, insn_schemes, same, not_same)

        # split the index of the chosen_operands mapping such that we can just
        # pass the inner dicts to InsnSchemes.instantate()
        op_maps = defaultdict(dict)
        for (iidx, op_key), chosen_operand in chosen_operands.items():
            op_maps[iidx][op_key] = chosen_operand

        # instantiate the schemes with the chosen operands
        bb = iwho.BasicBlock(self.actx.iwho_ctx)
        for iidx, ischeme in enumerate(insn_schemes):
            op_map = op_maps[iidx]
            try:
                instance = ischeme.instantiate(op_map)
            except iwho.InstantiationError as e:
                msg = "Failed to sample abstract block:\n" + textwrap.indent(str(self), '  ')
                msg += "\n"
                msg += "chosen InsnSchemes:\n" + "\n".join(map(str, insn_schemes))
                raise SamplingError(msg) from e

            bb.append(instance)

        return bb

class AbstractBlock(Expandable):
    """ An instance of this class represents a set of (concrete) BasicBlocks.
    """

    def __init__(self, actx: "AbstractionContext", bb: iwho.BasicBlock):
        self.actx = actx
        self.abs_insns = [ ]
        self.abs_aliasing = AbstractAliasInfo(self.actx)

        if bb is not None:
            self.join(bb)

    def __eq__(self, other):
        if not isinstance(other, AbstractBlock):
            return False
        return self.abs_insns == other.abs_insns and self.abs_aliasing == other.abs_aliasing

    def __hash__(self):
        return hash((tuple(self.abs_insns), self.abs_aliasing))

    @staticmethod
    def make_top(actx, num_insns):
        res = AbstractBlock(actx, None)
        for x in range(num_insns):
            ai = AbstractInsn(actx)
            ai.havoc()
            res.abs_insns.append(ai)
        res.abs_aliasing.havoc()
        return res

    def to_json_dict(self):
        res = dict()
        res['abs_insns'] = [ ai.to_json_dict() for ai in self.abs_insns ]
        res['abs_aliasing'] = self.abs_aliasing.to_json_dict()
        return res

    def dump_json(self, filename, **kwargs):
        actx = self.actx
        out_data = dict()
        out_data['config'] = actx.get_config()
        out_data['ab'] = actx.json_ref_manager.introduce_json_references(self.to_json_dict())

        for k, v in kwargs.items():
            out_data[k] = v

        store_json_config(out_data, filename)

    @staticmethod
    def from_json_dict(actx, json_dict):
        res = AbstractBlock(actx, bb=None)
        res.abs_insns = []
        for sub_dict in json_dict['abs_insns']:
            res.abs_insns.append(AbstractInsn.from_json_dict(actx, sub_dict))
        res.abs_aliasing = AbstractAliasInfo.from_json_dict(actx, json_dict['abs_aliasing'])
        return res

    def __deepcopy__(self, memo):
        new_one = AbstractBlock(self.actx, bb=None)
        new_one.abs_insns = deepcopy(self.abs_insns, memo)
        new_one.abs_aliasing = deepcopy(self.abs_aliasing, memo)
        return new_one

    def get_possible_expansions(self):
        """ Implements Expandable """
        res = []

        for ai_idx, ai in enumerate(self.abs_insns):
            for inner_expansion, benefit in ai.get_possible_expansions():
                expansion = (0, ai_idx, inner_expansion)
                res.append((expansion, benefit))

        for inner_expansion, benefit in self.abs_aliasing.get_possible_expansions():
                expansion = (1, inner_expansion)
                res.append((expansion, benefit))

        return res

    def apply_expansion(self, expansion):
        """ Implements Expandable """
        component = expansion[0]
        if component == 0: # Insn component
            key, inner_expansion = expansion[1:]
            ai = self.abs_insns[key]
            ai.apply_expansion(inner_expansion)
        else: # Aliasing component
            assert component == 1
            inner_expansion = expansion[1]
            self.abs_aliasing.apply_expansion(inner_expansion)

    def __str__(self) -> str:
        def format_insn(x):
            idx, abs_insn = x
            return "{:2}:\n{}".format(idx, textwrap.indent(str(abs_insn), '  '))

        # instruction part
        insn_part = "\n".join(map(format_insn, enumerate(self.abs_insns)))
        res = "AbstractInsns:\n" + textwrap.indent(insn_part, '  ')

        # aliasing part
        aliasing_str = str(self.abs_aliasing)
        res += "\nAliasing:\n" + textwrap.indent(aliasing_str, '  ')

        return res

    def subsumes(self, other: "AbstractBlock") -> bool:
        """ Check if all concrete basic blocks represented by other are also
        represented by self.
        """
        # check if all abstract insns are subsumed
        for self_ai, other_ai in zip(self.abs_insns, other.abs_insns):
            if not self_ai.subsumes(other_ai):
                return False

        if len(other.abs_insns) > len(self.abs_insns):
            # If other has more instructions than self, we need to check
            # whether one of the additional ones is not BOTTOM (since
            # non-present instructions are implicitly BOTTOM).
            # Since AbstractInsn right now has no is_bottom() method and this
            # case appears to be rather exotic, we use this hack here instead:
            bottom = AbstractInsn(self.actx)
            for other_ai in other.abs_insns[len(self.abs_insns):]:
                if not bottom.subsumes(other_ai):
                    return False

        return self.abs_aliasing.subsumes(other.abs_aliasing)

    def join(self, bb):
        """ Update self so that it additionally represents bb (and possibly,
        due to over-approximation, even more basic blocks).
        """
        bb_insns = list(bb.insns)
        assert len(bb_insns) >= len(self.abs_insns)

        while len(bb_insns) > len(self.abs_insns):
            self.abs_insns.append(AbstractInsn(self.actx))

        assert(len(bb_insns) == len(self.abs_insns))

        for a, b in zip(self.abs_insns, bb_insns):
            scheme = b.scheme
            a.join(scheme)

        self.abs_aliasing.join(bb)

    def sample(self, insn_scheme_blacklist: Sequence[iwho.InsnScheme]=[]) -> iwho.BasicBlock:
        """ Randomly sample a basic block that is represented by self.

        No scheme from the insn_scheme_blacklist will be chosen.

        May throw a SamplingError in case sampling is not possible. This could
        be because the constraints are actually contradictory (rather uncommon)
        or because the polynomial sampling algorithm took a wrong path trying
        to solve the NP-hard sampling problem.
        """
        insn_schemes = []
        for ai in self.abs_insns:
            insn_scheme = ai.sample(insn_scheme_blacklist=insn_scheme_blacklist)
            insn_schemes.append(insn_scheme)

        return self.abs_aliasing.sample(insn_schemes)

    def precompute_sampler(self, insn_scheme_blacklist: Sequence[iwho.InsnScheme]=[]):
        res = AbstractBlock(self.actx, bb=None)

        sampler_absinsns = []
        for ai in self.abs_insns:
            sampler_absinsns.append(ai.precompute_sampler(insn_scheme_blacklist))

        res.abs_insns = sampler_absinsns
        res.abs_aliasing = self.abs_aliasing

        return res


class PrecomputedSamplerAbsInsn:
    def __init__(self, allowed_schemes):
        self.allowed_schemes = tuple(allowed_schemes)

    def sample(self, **kwargs) -> iwho.InsnScheme:
        return random.choice(self.allowed_schemes)
