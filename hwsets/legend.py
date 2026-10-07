# code lists printed in the book before its sets: finishes, manufacturers, options. a lookup, no model call
import re, collections

# "CLR Clear Anodized", "NGP National Guard Products", "LAR Length as Required"
ENTRY = re.compile(r"^\s*([A-Z]{1,5}\d?|[A-Z]{1,2}\d{1,3}[A-Z]?|\d{3}[A-Z]?)\s{1,}([A-Z][A-Za-z][A-Za-z0-9 .,&'()/-]{1,50})\s*$")
HEADING = re.compile(r"^\s*(?:Code\s*:?\s*(?:Description|Name)\s*:?|(?:MANUFACTURER|FINISH|OPTION|HARDWARE|ABBREVIATION)S?\s*(?:LIST|CODES?|KEY)?\s*:?)\s*$", re.I)
KIND_WORDS = {
    "finish": re.compile(r"anodiz|bronze|chrome|brass|nickel|stainless|primed|prime|paint|aluminum|aluminium|black|grey|gray|blue|white|clear|sheen|mill|finish|satin|bright|dull|oil|coat|lacquer|zinc|steel", re.I),
    "option": re.compile(r"required|hold|exit|width|holes|wire|fail|connect|function|less|with|without|request|sunk|open|closed|delay|monitor|rated|electri|key|cylinder|strike|lever|trim|mount|handed|concealed", re.I),
    "mfr": re.compile(r"\b(?:inc|corp|co|ltd|llc|products|manufacturing|industries|hardware|company|group|technologies|controls|signaling|systems|access|security|door|lock|section)\b|^[A-Z][a-z]+(?: [A-Z][a-z]+)?$", re.I),
}


# which list a block of entries is, from its heading if it has one, else from the words in its names
def classify(heading, entries):
    h = (heading or "").lower()
    for kind, word in (("mfr", "manufacturer"), ("option", "option"), ("finish", "finish")):
        if word in h:
            return kind
    votes = collections.Counter()
    for _, name in entries:
        for kind, rx in KIND_WORDS.items():
            if rx.search(name):
                votes[kind] += 1
                break
    return votes.most_common(1)[0][0] if votes else "option"


# the pages just before the first set and the first set page -> {"finish": {code: name}, "mfr": {...}, "option": {...}}
#   in:  gerrard pages 11 to 17, which print "Code Description / AL Aluminum / CLR Clear Anodized ..." and "Code Name / DE Detex ..."
#   out: {"finish": {"AL": "Aluminum", "CLR": "Clear Anodized", ...}, "mfr": {"DE": "Detex", ...}, "option": {}}
def read_legends(texts, runs, back=6):
    legend = {"finish": {}, "mfr": {}, "option": {}}
    if not runs:
        return legend
    first = runs[0][0]
    lines = [l for i in range(max(0, first - back), first + 1) for l in texts[i]]
    block, heading, last_heading = [], None, None
    for l in lines + [""]:
        m = ENTRY.match(l)
        if m and not re.match(r"^\s*(?:\d{1,3}|__)\s", l):
            block.append((m.group(1), m.group(2).strip()))
            continue
        # a block ends at a line that is not an entry. three entries make a list, and legend names are
        # mixed case ("Hager Companies"), where all-caps prose that starts with a short word is not
        if len(block) >= 3 and sum(not name.isupper() for _, name in block) >= len(block) / 2:
            kind = classify(heading, block)
            for code, name in block:
                legend[kind].setdefault(code, name)
        block = []
        if HEADING.match(l):
            heading = l.strip()
        elif l.strip():
            heading = None
    return legend


# add the full names to a component: mfr_name, finish_name, and the option codes found in its catalog number
#   in:  {"catalog": "780-112HD x LAR", "finish": "CLR", "mfr": "HA"} with gerrard's legend
#   out: the same component plus {"mfr_name": "Hager", "finish_name": "Clear Anodized", "option_names": {"LAR": "Length as Required"}}
def resolve(comp, legend):
    comp["mfr_name"] = legend["mfr"].get(comp.get("mfr") or "")
    comp["finish_name"] = legend["finish"].get(comp.get("finish") or "")
    opts = {}
    if legend["option"] and comp.get("catalog"):
        for tok in re.split(r"[\s,/]+", comp["catalog"]):
            if tok in legend["option"]:
                opts[tok] = legend["option"][tok]
    comp["option_names"] = opts or None
    return comp
