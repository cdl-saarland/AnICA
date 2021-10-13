
import iwho

from .abstractblock import *


class JSONReferenceManager:
    """TODO"""

    def __init__(self, iwho_ctx):
        self.iwho_ctx = iwho_ctx

    def introduce_json_references(self, json_dict):
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

