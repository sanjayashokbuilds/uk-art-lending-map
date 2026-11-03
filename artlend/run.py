"""UK Art Lending Map: who lends against art in the UK, to whom, and who looks stretched.

Usage:
  export CH_API_KEY=your_key
  # pilot on a list of known dealers (one company number per line)
  python -m artlend.run --companies pilot.txt --deeds
  # full sweep of art-gallery and antiques companies
  python -m artlend.run --deeds --limit 2000
"""

import argparse
import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from .ch_client import CHClient
from .classify import classify, normalise_lender
from .deeds import pdf_text
from .flags import stress_flags

# 47781 retail sale in commercial art galleries; 47791 antiques; 90030 artistic creation
DEFAULT_SICS = ["47781", "47791"]
ART_SICS = {"47781", "47791", "90030", "46180"}
ART_NAME = re.compile(r"\b(art|arts|gallery|galleries|fine|antiques?|contemporary)\b", re.I)
OUT = Path("output")
DEEDS = Path("deeds")


def candidates(ch, args):
    if args.companies:
        nums = [l.strip().split(",")[0] for l in Path(args.companies).read_text().splitlines()]
        return [{"company_number": n.zfill(8) if n.isdigit() else n} for n in nums if n and not n.startswith("#")]
    seen, out = set(), []
    for sic in args.sic:
        start = 0
        while True:
            data = ch.get("/advanced-search/companies", {
                "sic_codes": sic, "company_status": "active",
                "size": 5000, "start_index": start,
            })
            items = (data or {}).get("items") or []
            for it in items:
                if it["company_number"] not in seen:
                    seen.add(it["company_number"])
                    out.append(it)
            start += len(items)
            if not items or start >= (data or {}).get("hits", 0):
                break
    return out[: args.limit] if args.limit else out


def deed_for(ch, number, charge, ocr):
    """Download and read the deed filed with a charge. Returns (text, source)."""
    for t in charge.get("transactions") or []:
        filing = (t.get("links") or {}).get("filing")
        if not filing or not t.get("filing_type", "").startswith("create-charge"):
            continue
        item = ch.get(filing)
        meta = ((item or {}).get("links") or {}).get("document_metadata")
        if not meta:
            continue
        cid = charge.get("charge_code") or filing.rsplit("/", 1)[-1]
        pdf = ch.download_pdf(meta, DEEDS / number / f"{cid}.pdf")
        if pdf:
            return pdf_text(pdf, ocr=ocr)
    return "", "none"


def parent_company(ch, number):
    for p in ch.get_all(f"/company/{number}/persons-with-significant-control"):
        if "corporate-entity" in p.get("kind", "") and not p.get("ceased_on"):
            reg = (p.get("identification") or {}).get("registration_number", "")
            return f"{p.get('name', '')} ({reg})" if reg else p.get("name", "")
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies", help="file of company numbers (pilot mode)")
    ap.add_argument("--sic", nargs="+", default=DEFAULT_SICS, help="SIC codes to sweep")
    ap.add_argument("--limit", type=int, default=0, help="max companies to check")
    ap.add_argument("--deeds", action="store_true", help="download and read charge deeds")
    ap.add_argument("--ocr", action="store_true", help="OCR scanned deeds (needs tesseract)")
    ap.add_argument("--outstanding-only", action="store_true", help="only read deeds for unpaid charges")
    args = ap.parse_args()

    ch = CHClient()
    OUT.mkdir(exist_ok=True)
    cands = candidates(ch, args)
    print(f"Checking {len(cands)} companies for charges...")

    charge_rows, borrower_rows = [], []
    for i, c in enumerate(cands, 1):
        num = c["company_number"]
        try:
            process_company(ch, args, c, num, i, cands, charge_rows, borrower_rows)
        except Exception as e:  # one bad company shouldn't kill a long run
            print(f"  skipped {num}: {type(e).__name__}: {str(e)[:120]}", flush=True)

    write_outputs(charge_rows, borrower_rows)


def process_company(ch, args, c, num, i, cands, charge_rows, borrower_rows):
    """Fetch one company's charges, read the deeds and score it."""
    charges = ch.get_all(f"/company/{num}/charges")
    if i % 25 == 0:
        print(f"  {i}/{len(cands)} checked, {len(borrower_rows)} with charges so far", flush=True)
    if not charges:
        return
    profile = ch.get(f"/company/{num}") or {}
    name = profile.get("company_name") or c.get("company_name", num)
    sics = set(profile.get("sic_codes") or c.get("sic_codes") or [])
    art_biz = bool(sics & ART_SICS) or bool(ART_NAME.search(name))
    officers = ch.get_all(f"/company/{num}/officers")
    own_names = [name] + [p.get("name", "") for p in profile.get("previous_company_names") or []]

    labels = defaultdict(int)
    for chg in charges:
        desc = (chg.get("particulars") or {}).get("description", "")
        text, source = "", "none"
        if args.deeds and not (args.outstanding_only and chg.get("status") != "outstanding"):
            text, source = deed_for(ch, num, chg, args.ocr)
        raw_lenders = [p.get("name", "") for p in chg.get("persons_entitled") or []]
        label, terms, snip = classify(text, desc, art_biz, own_names, raw_lenders)
        labels[label] += 1
        lenders = [normalise_lender(n) for n in raw_lenders]
        charge_rows.append({
            "company_number": num, "company_name": name,
            "charge_code": chg.get("charge_code", ""),
            "created_on": chg.get("created_on", ""), "status": chg.get("status", ""),
            "lenders": "; ".join(lenders),
            "fixed": (chg.get("particulars") or {}).get("contains_fixed_charge", ""),
            "floating_all": (chg.get("particulars") or {}).get("floating_charge_covers_all", ""),
            "art_label": label, "art_terms": "; ".join(terms),
            "evidence": snip[:300], "deed_text_source": source,
        })

    score, reasons = stress_flags(profile, charges, officers)
    borrower_rows.append({
        "company_number": num, "company_name": name,
        "status": profile.get("company_status", ""),
        "art_business": art_biz,
        "charges_total": len(charges),
        "charges_outstanding": sum(1 for x in charges if x.get("status") == "outstanding"),
        "art_named": labels["art_named"], "art_likely": labels["art_likely"],
        "stress_score": score, "stress_reasons": "; ".join(reasons),
        "parent": parent_company(ch, num),
    })


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def lender_table(charge_rows):
    agg = defaultdict(lambda: {"charges": 0, "art_named": 0, "art_likely": 0, "borrowers": set(), "latest": ""})
    for r in charge_rows:
        for l in filter(None, r["lenders"].split("; ")):
            a = agg[l]
            a["charges"] += 1
            a["art_named"] += r["art_label"] == "art_named"
            a["art_likely"] += r["art_label"] == "art_likely"
            a["borrowers"].add(r["company_number"])
            a["latest"] = max(a["latest"], r["created_on"])
    rows = [{"lender": k, "charges": v["charges"], "art_named": v["art_named"],
             "art_likely": v["art_likely"], "borrowers": len(v["borrowers"]),
             "latest_charge": v["latest"]} for k, v in agg.items()]
    return sorted(rows, key=lambda r: (-r["art_named"], -r["art_likely"], -r["borrowers"]))


def write_outputs(charge_rows, borrower_rows):
    lenders = lender_table(charge_rows)
    borrower_rows.sort(key=lambda r: (-r["stress_score"], -r["art_named"]))
    write_csv(OUT / "charges.csv", charge_rows)
    write_csv(OUT / "borrowers.csv", borrower_rows)
    write_csv(OUT / "lenders.csv", lenders)

    n = defaultdict(int)
    for r in charge_rows:
        n[r["art_label"]] += 1
    lines = [
        f"# UK Art Lending Map: run of {date.today()}", "",
        f"- Companies with charges: {len(borrower_rows)}",
        f"- Charges found: {len(charge_rows)}",
        f"- Deeds naming art directly: {n['art_named']}",
        f"- Stock/chattels charges on art businesses: {n['art_likely']}",
        f"- General all-assets charges: {n['general']}",
        f"- Not readable / not downloaded: {n['unknown']}", "",
        "## Top lenders", "",
        "| Lender | Charges | Naming art | Borrowers | Latest |", "|---|---|---|---|---|",
    ]
    for r in lenders[:15]:
        lines.append(f"| {r['lender']} | {r['charges']} | {r['art_named']} | {r['borrowers']} | {r['latest_charge']} |")
    lines += ["", "## Borrowers with real stress flags (score 2+)", "",
              "| Company | Outstanding | Score | Why |", "|---|---|---|---|"]
    for r in [b for b in borrower_rows if b["stress_score"] >= 2][:15]:
        lines.append(f"| {r['company_name']} | {r['charges_outstanding']} | {r['stress_score']} | {r['stress_reasons']} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print(f"Done. See {OUT}/report.md")


if __name__ == "__main__":
    main()
