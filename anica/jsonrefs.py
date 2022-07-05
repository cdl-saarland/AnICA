""" Tools for handling json serialization of AnICA datastructures.
"""

import iwho

from .abstractblock import *


class JSONReferenceManager:
    """ This class encapsulates means of mapping references to certain AnICA
    objects to strings that can be mapped to meaningful references again in
    future program executions.

    We don't want to just serialize the referenced objects, because they are
    large and usually deduplicated in the anica/iwho libraries.

    The json life cycle of AnICA datastructures should be as follows:

                        +----------------+
                        | data structure |
               +------> +----------------+ -------+
               |                                  |
         from_json_dict                      to_json_dict
               |                                  |
               +---- +----------------------+ <---+
                     | dict with references |
               +---> +----------------------+ ----+
               |                                  |
    resolve_json_references             introduce_json_references
               |                                  |
               +--- +------------------------+ <--+
                    | dict with string reprs |
               +--> +------------------------+ ---+
               |                                  |
        load from string                     dump as string
               |                                  |
               +-------- +-------------+ <--------+
                         | string/file |
                         +-------------+
    """

    def __init__(self, iwho_ctx):
        self.iwho_ctx = iwho_ctx

    def introduce_json_references(self, json_dict):
        """ Replace references to internal datatstructures in the json dict by
        unique identifiers.
        """
        if isinstance(json_dict, tuple) or isinstance(json_dict, list):
            return tuple((self.introduce_json_references(x) for x in json_dict))
        if isinstance(json_dict, dict):
            return { k: self.introduce_json_references(x) for k,x in json_dict.items() }
        if isinstance(json_dict, iwho.InsnScheme.OperandKind):
            return f"$OperandKind:{json_dict.value}"
        if isinstance(json_dict, iwho.InsnScheme):
            return f"$InsnScheme:{str(json_dict)}"
        if isinstance(json_dict, AbstractFeature.SpecialValue):
            return f"$SV:{json_dict.name}"
        return json_dict

    def resolve_json_references(self, json_dict):
        """ Replace the unique identifiers introduced by
        `introduce_json_references` by references to internal datatstructures.
        """
        if isinstance(json_dict, tuple) or isinstance(json_dict, list):
            return tuple((self.resolve_json_references(x) for x in json_dict))
        if isinstance(json_dict, dict):
            return { k: self.resolve_json_references(x) for k,x in json_dict.items() }
        if isinstance(json_dict, str):
            json_str = json_dict

            search_str = '$InsnScheme:'
            if json_str.startswith(search_str):
                scheme_str = json_str[len(search_str):]
                return self.iwho_ctx.str_to_scheme[scheme_str]

            search_str = '$OperandKind:'
            if json_str.startswith(search_str):
                opkind_val = int(json_str[len(search_str):])
                for ev in iwho.InsnScheme.OperandKind:
                    if opkind_val == ev.value:
                        return ev

            search_str = '$SV:'
            if json_str.startswith(search_str):
                val = json_str[len(search_str):]
                return AbstractFeature.SpecialValue[val]

            return json_str
        return json_dict

