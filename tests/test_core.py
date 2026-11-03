from datetime import date

from artlend.classify import classify, normalise_lender
from artlend.flags import stress_flags
from artlend import run


def test_art_named_from_deed():
    label, terms, snip = classify("all the Works of Art listed in Schedule 2", "", True)
    assert label == "art_named"
    assert "works of art" in terms
    assert "Schedule 2" in snip


def test_weak_terms_need_art_business():
    assert classify("the Chargor's stock and chattels", "", True)[0] == "art_likely"
    assert classify("the Chargor's stock and chattels", "", False)[0] == "general"


def test_unknown_without_text():
    assert classify("", "", True)[0] == "unknown"


def test_normalise_lender():
    assert normalise_lender("Athena Art Finance Corp. (as Security Agent)") == "ATHENA ART FINANCE CORP"
    assert normalise_lender("HSBC UK BANK PLC") == "HSBC UK BANK"
    assert normalise_lender("Lloyds Bank Limited as Security Trustee") == "LLOYDS BANK"


def test_stress_flags():
    profile = {"company_status": "active", "accounts": {"overdue": True},
               "confirmation_statement": {"overdue": False}}
    charges = [{"status": "outstanding", "created_on": "2026-06-01"}] * 3
    officers = [{"resigned_on": "2026-02-01"}, {"resigned_on": "2026-03-01"}]
    score, reasons = stress_flags(profile, charges, officers, today=date(2026, 11, 3))
    assert score == 2 + 1 + 1 + 1
    assert "accounts overdue" in reasons


class FakeCH:
    """Stands in for Companies House so the pipeline can run offline."""

    def get(self, path, params=None):
        if path == "/company/00000001":
            return {"company_name": "TEST FINE ART LTD", "sic_codes": ["47781"],
                    "company_status": "active", "accounts": {"overdue": False}}
        if path.startswith("/company/00000001/filing-history"):
            return {"links": {"document_metadata": "https://doc/x"}}
        return None

    def get_all(self, path, **kw):
        if path == "/company/00000001/charges":
            return [{"charge_code": "000000010001", "status": "outstanding",
                     "created_on": "2025-01-10",
                     "persons_entitled": [{"name": "Athena Art Finance Corp."}],
                     "particulars": {"description": "", "contains_fixed_charge": True},
                     "transactions": [{"filing_type": "create-charge-with-deed",
                                       "links": {"filing": "/company/00000001/filing-history/AB"}}]}]
        return []

    def download_pdf(self, meta, dest):
        return "fake.pdf"


def test_pipeline_offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run, "CHClient", FakeCH)
    monkeypatch.setattr(run, "pdf_text", lambda p, ocr=False: ("fixed charge over the Paintings in Schedule 1", "text"))
    (tmp_path / "pilot.txt").write_text("1\n")
    monkeypatch.setattr("sys.argv", ["run", "--companies", "pilot.txt", "--deeds"])
    run.OUT = tmp_path / "output"
    run.main()
    report = (tmp_path / "output" / "report.md").read_text()
    assert "Deeds naming art directly: 1" in report
    assert "ATHENA ART FINANCE CORP" in report


def test_company_names_are_not_art_evidence():
    # real false positives from the first run
    assert classify("Company name in full: Offer Waterman Fine Art Limited. Please give a description",
                    "", True, ["OFFER WATERMAN FINE ART LIMITED"])[0] != "art_named"
    assert classify("certify that a charge created by Bourne Fine Art Limited on 1 April 2011",
                    "", True, ["FAS EDINBURGH LTD"])[0] != "art_named"
    assert classify("Westbury (Fine Art) Limited a Rent Deposit Deed", "", True, [])[0] != "art_named"
    assert classify("Property k/a 'colyton antiques' market place", "", False, [])[0] != "art_named"


def test_real_art_deeds_still_match():
    assert classify("CHATTEL MORTGAGE OF WORKS OF ART This CHATTEL MORTGAGE is given",
                    "", True, ["MODERN MASTERS LIMITED"])[0] == "art_named"
    assert classify("", "Legal mortgage over works of art owned by the chargor", True,
                    ["BERNARD JACOBSON LIMITED"])[0] == "art_named"


def test_art_specialist_lender():
    label, terms, _ = classify("Contains fixed charge(s). Contains negative pledge.", "", True,
                               ["BERNARD JACOBSON LIMITED"], ["FINE ART LUXEMBOURG"])
    assert label == "art_likely" and terms == ["art-specialist lender"]


def test_dealer_with_open_charges_is_not_stressed():
    charges = [{"status": "outstanding", "created_on": "2026-06-01"}] * 4
    score, _ = stress_flags({"company_status": "active"}, charges, [], today=date(2026, 11, 3))
    assert score == 0


def test_deed_text_cache(tmp_path, monkeypatch):
    from artlend import deeds
    calls = []
    monkeypatch.setattr(deeds, "_extract", lambda p, o, m: (calls.append(1) or ("works of art " * 30, "ocr")))
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    assert deeds.pdf_text(pdf, ocr=True)[1] == "ocr"
    assert deeds.pdf_text(pdf, ocr=True) == ("works of art " * 30, "ocr")
    assert len(calls) == 1
