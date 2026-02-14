"""
Deep Search service for the Refactoring Workbench.
Generates naming-convention variants from existing rules to find
related keywords across ASP.NET, WinForms, Angular, and SQL codebases.
"""

from typing import List


# Common prefixes used in ASP.NET / WinForms / SQL / Angular codebases
COMMON_PREFIXES = [
    "column", "col", "fld", "txt", "lbl", "btn", "tbl", "sp", "fn",
    "vw", "ddl", "chk", "rdb", "grd", "pnl", "hdn", "rpt", "frm",
    "get", "set", "is", "has", "prm", "param", "var", "tmp",
]


def _to_camel(word: str) -> str:
    """Convert to camelCase."""
    if not word:
        return word
    return word[0].lower() + word[1:]


def _to_pascal(word: str) -> str:
    """Convert to PascalCase."""
    if not word:
        return word
    return word[0].upper() + word[1:]


def _to_lower(word: str) -> str:
    return word.lower()


def _to_upper(word: str) -> str:
    return word.upper()


def _to_snake(word: str) -> str:
    """Convert to snake_case (basic: insert _ before uppercase letters)."""
    result = []
    for i, ch in enumerate(word):
        if ch.isupper() and i > 0 and not word[i - 1].isupper():
            result.append('_')
        result.append(ch.lower())
    return ''.join(result)


def generate_variants(search_keyword: str, replacement_keyword: str) -> List[dict]:
    """
    Generate naming-convention variants from a keyword pair.

    Given a rule like CNIC -> Aadhar, generates:
      - Case variants: cnic/aadhar, CNIC/AADHAR, Cnic/Aadhar
      - Prefix variants: columnCNIC/columnAadhar, fldCNIC/fldAadhar, etc.
      - Snake/underscore variants: _cnic/_aadhar

    Returns list of dicts: { original, suggestion, replacement, category }
    """
    suggestions = []
    seen = set()

    def _add(original: str, replacement: str, category: str):
        key = (original, replacement)
        if key not in seen and original != replacement:
            seen.add(key)
            suggestions.append({
                "original": original,
                "suggestion": f"{original} → {replacement}",
                "replacement": replacement,
                "category": category,
                "selected": True,
            })

    search = search_keyword.strip()
    replace = replacement_keyword.strip()

    if not search or not replace:
        return suggestions

    # -- Exact match (the rule itself) --
    _add(search, replace, "Exact")

    # -- Case variants --
    _add(_to_lower(search), _to_lower(replace), "Case Variant")
    _add(_to_upper(search), _to_upper(replace), "Case Variant")
    _add(_to_pascal(search), _to_pascal(replace), "Case Variant")
    _add(_to_camel(search), _to_camel(replace), "Case Variant")

    # -- Snake case --
    snake_search = _to_snake(search)
    snake_replace = _to_snake(replace)
    _add(snake_search, snake_replace, "Snake Case")
    _add(snake_search.upper(), snake_replace.upper(), "Snake Case")

    # -- Underscore prefix --
    _add(f"_{_to_camel(search)}", f"_{_to_camel(replace)}", "Underscore Prefix")
    _add(f"_{_to_lower(search)}", f"_{_to_lower(replace)}", "Underscore Prefix")

    # -- Common code prefixes (PascalCase join) --
    for prefix in COMMON_PREFIXES:
        prefixed_search = f"{prefix}{_to_pascal(search)}"
        prefixed_replace = f"{prefix}{_to_pascal(replace)}"
        _add(prefixed_search, prefixed_replace, f"Prefix: {prefix}*")

    # -- Common code prefixes (underscore join) --
    for prefix in ["column", "col", "tbl", "sp", "fn", "vw"]:
        _add(f"{prefix}_{_to_lower(search)}", f"{prefix}_{_to_lower(replace)}", f"Prefix: {prefix}_*")
        _add(f"{prefix}_{_to_upper(search)}", f"{prefix}_{_to_upper(replace)}", f"Prefix: {prefix}_*")

    return suggestions


def generate_from_rules(rules: list) -> List[dict]:
    """
    Generate Deep Search suggestions from a list of rule dicts.
    Each rule dict must have 'search_pattern' and 'replacement_text'.
    Returns all suggestions grouped by source rule.
    """
    all_suggestions = []

    for rule in rules:
        search = rule.get("search_pattern", "")
        replace = rule.get("replacement_text", "")
        rule_name = rule.get("name", f"{search} → {replace}")

        variants = generate_variants(search, replace)

        for v in variants:
            v["source_rule"] = rule_name
            v["source_rule_id"] = rule.get("id")

        all_suggestions.extend(variants)

    return all_suggestions
