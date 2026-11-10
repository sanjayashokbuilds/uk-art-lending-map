# uk-art-lending-map

When a UK company borrows against its assets, the loan gets registered at Companies House as a charge, and the deed behind it is filed too. Galleries and dealers that borrow against their stock leave that trail, but as far as I can tell nobody reads it.

So I built something that does. It pulls every charge on UK art galleries, dealers and antiques businesses, reads the deeds (OCR for the scanned ones), and works out which loans are actually secured on art.

## What I found

Full write-up: [`reports/art_report.md`](reports/art_report.md). Every named work: [`reports/artworks.csv`](reports/artworks.csv).

- **308 charges secured directly on art**, out of 1,872 charges across 568 art businesses.
- **It's a small club.** 39 borrowers in total, and the top 5 hold 79% of the art-secured charges. Names like Hazlitt Gooden & Fox, Thos. Agnew's and Richard Green come up again and again.
- **The high-street banks have mostly left.** NatWest is the biggest lender in the data (121 art charges) but its last one was in 2010 and none are still open. Bank of Scotland's last was in 2020.
- **What's open now is mostly specialist and private-bank lending.** Sotheby's Financial Services (lending to Ivor Braka, Anthony d'Offay and others, most recently in 2026), DHB Bank (Bernard Jacobson, 2025 and 2026) and Lloyds (Richard Green, 2025).
- **Some charges name the exact works pledged.** More than 40 of them, by artists including Henry Moore, Elizabeth Frink, David Hockney, John Piper and Burne-Jones, each with the lender and the date.

Only 39 art-secured charges are still open and 8 were created in the last five years, so most of this is history. The history is still the interesting part: you can see who used to lend against art in the UK and who does now.

## How a charge gets labelled

| Label | Meaning |
|---|---|
| `art_named` | the deed or charge description names artworks directly ("works of art", "paintings", "schedule of artworks"...) |
| `art_likely` | only stock/chattels wording, but the borrower is an art business |
| `general` | an all-assets charge with no art wording |
| `unknown` | no deed downloaded, or a scan that wasn't OCR'd |

## Run it

```bash
pip install -r requirements.txt
export CH_API_KEY=your_companies_house_key

# quick test on 50 art-gallery companies
python -m artlend.run --sic 47781 --limit 50 --deeds

# full sweep (art galleries + antiques), reading scanned deeds too
brew install tesseract poppler && pip install pytesseract pdf2image
python -m artlend.run --deeds --ocr

# artwork-level view and the report above
python artworks.py
```

Or pass your own list of company numbers with `--companies list.txt`.

Raw results land in `output/` (`report.md`, `lenders.csv`, `borrowers.csv`, `charges.csv`). Everything is cached in `.cache/`, so reruns are free and stay inside the Companies House rate limit.

## Notes

- All of this is public data from the Companies House API.
- A charge only shows that a loan was secured on an asset. It says nothing about whether the borrower is in difficulty.
- The tool also flags borrowers with open charges plus overdue filings. Those flags are rough, so they stay in `output/` and aren't published here.
- Deeds from before April 2013 often aren't filed, and about 40% of charges had no readable deed, so the real numbers are higher than these.

Tests: `python -m pytest -q`
