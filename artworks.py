"""Turn output/charges.csv into an artwork-level table and a focused report.

Reads the existing sweep output only. No API calls, no rerun.

    python artworks.py

Writes output/artworks.csv and output/art_report.md
"""
import collections
import csv
import re
from datetime import date, timedelta
from pathlib import Path

SRC = Path("output/charges.csv")
OUT_CSV = Path("output/artworks.csv")
OUT_MD = Path("output/art_report.md")

RECENT_CUTOFF = (date.today() - timedelta(days=5 * 365)).isoformat()
OPEN = {"outstanding", "part-satisfied"}

# "Work of art by elizabeth frink k/a horse 1979."
# "Bronze sculpture by dame elisabeth frink known as boar."
# "Modern british oil painting by john piper known as leeds."
ART_WORD = (r"(?:works?\s+of\s+art|painting|sculpture|drawing|watercolou?r|bronze|print|"
            r"canvas|panel|gouache|pastel|tapestry|carving|figure|maquette|relief)")
WORK = re.compile(
    rf"(?P<medium>\b(?:[A-Za-z0-9][A-Za-z0-9' \-]{{0,40}}?\s)?{ART_WORD})\s+by\s+"
    r"(?P<artist>(?:[A-Za-z.'\-]+\s+){0,5}?[A-Za-z.'\-]+)\s+"
    r"(?:k/a|known\s+as|entitled|titled)\s+"
    r"(?P<title>[^;]{1,100}?)\.?\s*(?=;|$)",
    re.I,
)


def clean(s):
    return " ".join(s.replace("|", "/").split())


def nice(s):
    s = re.sub(r"\.?\s*see the (?:mortgage|charge|instrument).*$", "", clean(s), flags=re.I)
    return s.strip(" .").title()


def is_open(r):
    return r["status"].strip().lower() in OPEN


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def main():
    with SRC.open(newline="", encoding="utf-8") as f:
        charges = [r for r in csv.DictReader(f) if r["art_label"] == "art_named"]

    # one row per named artwork; charges without a specific work keep one row
    works = []
    charges_with_work = 0
    for r in charges:
        found = list(WORK.finditer(r["evidence"]))
        charges_with_work += bool(found)
        base = {
            "created_on": r["created_on"],
            "status": r["status"],
            "borrower": clean(r["company_name"]),
            "company_number": r["company_number"],
            "lender": clean(r["lenders"]),
            "charge_code": r["charge_code"],
        }
        if found:
            for m in found:
                works.append({**base, "artist": nice(m["artist"]), "title": nice(m["title"]),
                              "medium": clean(m["medium"]).capitalize(), "pledged": "specific work"})
        else:
            works.append({**base, "artist": "", "title": "", "medium": "",
                          "pledged": clean(r["art_terms"]) or "art (general)"})

    works.sort(key=lambda w: w["created_on"], reverse=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(works[0].keys()) if works else ["none"])
        w.writeheader()
        w.writerows(works)

    named = [w for w in works if w["artist"]]
    recent = [r for r in charges if r["created_on"] >= RECENT_CUTOFF]
    open_ = [r for r in charges if is_open(r)]

    by_lender = collections.defaultdict(list)
    by_borrower = collections.defaultdict(list)
    for r in charges:
        by_lender[clean(r["lenders"])].append(r)
        by_borrower[clean(r["company_name"])].append(r)

    def summary(group, other_key):
        rows = []
        for name, rs in sorted(group.items(), key=lambda kv: -len(kv[1])):
            others = sorted({clean(r[other_key]) for r in rs})
            rows.append([name, len(rs), sum(is_open(r) for r in rs),
                         max(r["created_on"] for r in rs), ", ".join(others)[:120]])
        return rows

    top_borrowers = sorted(by_borrower.items(), key=lambda kv: -len(kv[1]))
    top5_share = sum(len(rs) for _, rs in top_borrowers[:5]) / max(len(charges), 1)

    artists = collections.Counter(w["artist"] for w in named)

    md = [
        f"# UK Art Lending Map: loans secured on named artworks",
        "",
        f"Source: Companies House charges registered against UK art dealers, galleries and "
        f"antiques businesses. Only charges whose description or deed names art directly are counted.",
        "",
        "## Headline numbers",
        "",
        f"- Art-secured charges: **{len(charges)}**",
        f"- Still open: **{len(open_)}**",
        f"- Created since {RECENT_CUTOFF[:7]}: **{len(recent)}**",
        f"- Borrowers: **{len(by_borrower)}**, lenders: **{len(by_lender)}**",
        f"- Top 5 borrowers hold **{top5_share:.0%}** of all art-secured charges",
        f"- Charges naming a specific work: **{charges_with_work}**, "
        f"covering **{len(named)}** works by **{len(artists)}** artists",
        "",
        "## Lenders",
        "",
        md_table(["Lender", "Art charges", "Open", "Latest", "Borrowers"],
                 summary(by_lender, "company_name")),
        "",
        "## Borrowers",
        "",
        md_table(["Borrower", "Art charges", "Open", "Latest", "Lenders"],
                 summary(by_borrower, "lenders")),
        "",
        f"## Art-secured charges since {RECENT_CUTOFF[:7]}",
        "",
        md_table(["Date", "Borrower", "Lender", "Status", "Pledged"],
                 [[w["created_on"], w["borrower"], w["lender"], w["status"],
                   f"{w['artist']}, *{w['title']}*" if w["artist"] else w["pledged"]]
                  for w in works if w["created_on"] >= RECENT_CUTOFF]),
        "",
        "## Most-pledged artists",
        "",
        md_table(["Artist", "Works pledged"], artists.most_common(15)),
        "",
        "## Notes",
        "",
        "- A charge is a public record that a loan was secured on an asset. It says nothing about "
        "whether the borrower is in difficulty.",
        "- Specific works are only listed where the charge itself names them; most deeds describe "
        "art in general terms.",
        "- Full list of works: `output/artworks.csv`.",
    ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"{len(charges)} art-secured charges | {len(open_)} open | {len(recent)} since {RECENT_CUTOFF[:7]}")
    print(f"{len(named)} named works by {len(artists)} artists | top 5 borrowers = {top5_share:.0%}")
    print(f"Wrote {OUT_CSV} and {OUT_MD}")


if __name__ == "__main__":
    main()
