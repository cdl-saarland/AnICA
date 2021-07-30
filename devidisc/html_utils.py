


def prettify_absinsn(absinsn, hl_feature=None, skip_top=False):
    if absinsn.is_top():
        res = "TOP"
        if hl_feature is not None:
            res = '<div class="highlightedcomponent">' + res + '</div>'
    else:
        list_entries = []
        for k, v in absinsn.features.items():
            if skip_top and v.is_top():
                continue
            entry = f"{k}: {v}"
            if hl_feature is not None and hl_feature[0] == k:
                entry = '<div class="highlightedcomponent">' + entry + "</div>"
            entry = "<li>" + entry + "</li>"
            list_entries.append(entry)
        res = "\n".join(list_entries)
        res = '<ul class="featurelist">' + res + "</ul>"
    return res


def prettify_absblock(absblock, hl_expansion=None, skip_top=False):
    res = ""
    res += "<b>Abstract Instructions:</b>\n"
    res += "<table class=\"ai_table\">\n"
    for idx, ai in enumerate(absblock.abs_insns):
        res += "<tr class=\"ai_tr\">"
        res += f"<th class=\"ai_th\">{idx}</th>\n"
        hl_feature = None
        if hl_expansion is not None and hl_expansion[0] == 0 and hl_expansion[1] == idx:
            hl_feature = hl_expansion[2]

        insn_str = prettify_absinsn(ai, hl_feature, skip_top=skip_top)
        res += f"<td class=\"ai_td\">{insn_str}</td>\n"
        res += "</tr>"

    res += "</table>\n"

    # abstract aliasing

    highlight_key = None
    if hl_expansion is not None and hl_expansion[0] == 1:
        highlight_key = absblock.actx.json_ref_manager.resolve_json_references(hl_expansion[1])[0]

    entries = []
    abs_alias_dict = absblock.abs_aliasing._aliasing_dict
    for ((iidx1, oidx1), (iidx2,oidx2)), absval in abs_alias_dict.items():
        highlighted = highlight_key == ((iidx1, oidx1), (iidx2,oidx2))
        if absval.is_top():
            if highlighted:
                valtxt = "TOP"
            else:
                continue
        elif absval.is_bottom():
            valtxt = "BOTTOM"
        elif absval.val is False:
            valtxt = "must not alias"
        elif absval.val is True:
            valtxt = "must alias"
        else:
            assert False

        div = "", ""
        if highlighted:
            div = '<div class="highlightedcomponent">', "</div>"
        entries.append((f"<tr><td>{div[0]}{iidx1}:{oidx1} - {iidx2}:{oidx2}{div[1]}</td> <td>{div[0]} {valtxt} {div[1]} </td></tr>\n", f"{iidx1}:{oidx1} - {iidx2}:{oidx2}"))

    if len(entries) > 0:
        res += "<b>Abstract Aliasing:</b>"
        entries.sort(key=lambda x: x[1])
        res += "\n<table>"
        res += "\n" + "\n".join(map(lambda x: x[0], entries))
        res += "</table>"
    elif not skip_top:
        res += "<b>Abstract Aliasing:</b> TOP"

    return res
