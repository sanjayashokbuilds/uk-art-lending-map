"""Decide whether a charge is secured on art, and explain why.

Evidence comes from two places, strongest first:
  1. the charge deed itself (the PDF filed with form MR01)
  2. the short description Companies House stores with the charge

Strong terms name art directly. Weak terms (stock, chattels, goods) only
count when the borrower is an art business, because every shop's deed says
"stock".
"""

import re

# "fine art" is mostly part of company names ("X Fine Art Limited",
# "Westbury (Fine Art) Ltd", "Fine Art Luxembourg"), so it only counts
# when it isn't followed by a company-name word or wrapped in brackets.
_NAME_WORDS = (r"limited|ltd|plc|llp|luxembourg|gallery|galleries|publishing|"
               r"services|company|co\b|group|partners|holdings|society|cafes?")
STRONG = [
    r"works? of art", r"art ?works?",
    rf"(?<!\()fine art(?!\s*\)|\s+(?:{_NAME_WORDS}))",
    r"paintings?", r"sculptures?", r"drawings", r"objets? d'art",
    r"art collection", r"collection of art", r"schedule of (?:art|works)",
    r"consigned (?:art|works)", r"artists?'? (?:prints|editions)",
    r"lithographs?", r"watercolou?rs?", r"oil on canvas", r"bronzes?",
]
WEAK = [
    r"stock[- ]in[- ]trade", r"\bstock\b", r"inventory", r"chattels",
    r"\bgoods\b", r"consignment", r"antiques",
]
ART_LENDER = re.compile(r"\b(art|fine art|arts)\b", re.I)

_STRONG_RE = [re.compile(p, re.I) for p in STRONG]
_WEAK_RE = [re.compile(p, re.I) for p in WEAK]


def _hits(text, regexes):
    found = {}
    for rx in regexes:
        for m in rx.finditer(text):
            term = m.group(0).lower()
            if term not in found:
                lo, hi = max(0, m.start() - 90), min(len(text), m.end() + 90)
                found[term] = " ".join(text[lo:hi].split())
    return found


def _strip_names(text, names):
    """Blank out the borrower's and lenders' own names so 'Offer Waterman Fine
    Art Limited' doesn't count as the deed mentioning fine art."""
    for n in names or []:
        n = (n or "").strip()
        if len(n) < 4:
            continue
        base = re.sub(r"\b(limited|ltd|plc|llp)\.?$", "", n, flags=re.I).strip()
        for variant in {n, base}:
            if variant:
                text = re.sub(re.escape(variant), " ", text, flags=re.I)
    return text


def classify(deed_text="", description="", art_business=True, ignore_names=(), lenders=()):
    """Return (label, matched_terms, snippet).

    label is one of:
      art_named     the deed or description names artworks directly
      art_likely    stock/chattels wording on an art business, or an art-specialist lender
      general       an all-assets charge with no art wording
      unknown       no text to read (deed not downloaded or unreadable)
    """
    text = f"{description or ''}\n{deed_text or ''}"
    if not text.strip():
        return "unknown", [], ""
    text = _strip_names(text, list(ignore_names) + list(lenders))
    strong = _hits(text, _STRONG_RE)
    if strong:
        term, snip = next(iter(strong.items()))
        return "art_named", sorted(strong), snip
    art_lender = [l for l in lenders if ART_LENDER.search(l or "")]
    if art_lender:
        return "art_likely", ["art-specialist lender"], f"lender: {art_lender[0]}"
    weak = _hits(text, _WEAK_RE)
    if weak and art_business:
        term, snip = next(iter(weak.items()))
        return "art_likely", sorted(weak), snip
    if not (deed_text or "").strip():
        return "unknown", [], ""
    return "general", [], ""


_ROLE = re.compile(r"\(.*?\)|\b(?:as|in its capacity as)\b.*$", re.I)
_SUFFIX = re.compile(r"\b(?:limited|ltd|plc|llp|lp|inc|n\.?a|s\.?a|ag)\.?$", re.I)


def normalise_lender(name):
    """'ATHENA ART FINANCE CORP. (AS SECURITY AGENT)' -> 'ATHENA ART FINANCE CORP'"""
    n = _ROLE.sub("", (name or "").replace(",", " "))
    n = " ".join(n.split()).strip(" .-")
    prev = None
    while prev != n:
        prev = n
        n = _SUFFIX.sub("", n).strip(" .-")
    return n.upper()
