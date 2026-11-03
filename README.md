# uk-art-lending-map

When a UK company borrows against its assets, the loan gets registered at Companies House as a charge, and the deed behind it is filed too. Galleries and dealers that borrow against their stock leave that trail, but as far as I can tell nobody reads it.

This pulls the charges on UK art businesses, reads the deeds, and works out:

- **who lends against art in the UK** and how active each lender is
- **who borrows**, and how much is still outstanding
- **who looks stretched**: lots of open charges plus overdue accounts, director exits or insolvency notices. Stock from those businesses can end up forced onto the market.

Every result shows its evidence (the matched wording from the deed, or the filing behind a flag), so it can be checked by hand.

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
```

Or pass your own list of company numbers with `--companies list.txt`.

Results land in `output/`: `report.md`, `lenders.csv`, `borrowers.csv`, `charges.csv`. Everything is cached in `.cache/`, so reruns are free and stay inside the Companies House rate limit.

## Notes

- All of this is public data from the Companies House API.
- A stress flag is a reason to look closer, not a claim that a business is in trouble. Output files aren't committed to this repo for that reason.
- Deeds from before April 2013 often aren't filed, so older charges mostly come out as `unknown`.

Tests: `python -m pytest -q`
