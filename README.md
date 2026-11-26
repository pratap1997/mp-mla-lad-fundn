# MP/MLA-LAD Fund Scraper & Documents

Scrapers, datasets, and official portal documents for **Uttar Pradesh (UP) MLA-LAD Fund (`mlaladsup.in`)** and **Rajasthan RDPRWMS (`rdprwms.rajasthan.gov.in`)**.

## Key Datasets & Workbooks

- **`UP_MLA_LAD_Fund_YearWise.xlsx` / `.csv`** — Year-wise × MLA-wise financial summary (2023-24, 2024-25, 2025-26, 2026-27) for all 403 Vidhan Sabha MLAs and 109 Vidhan Parishad MLCs, including Opening Balance, Allocated Funds, Sanctioned Amount, Expenditure, Remaining Balance, Committed Amount, Physical Progress, and Fund Release installments.
- **`UP_MLA_Physical_Progress.csv`** — Work completion counts (proposed, sanctioned, started, not started, completed, incomplete) per MLA per year.
- **`MLA_LADS_UP_All_Works_and_Summary.xlsx`** — 145,195 individual works + 512 MLA summary (also available as compressed `MLA_LADS_UP_All_Works.csv.zip` and `MLA_LADS_UP_Summary.csv`).
- **`Rajasthan_RDPRWMS/`** — Rajasthan RDPRWMS portal scrape (2,600 MLA-LAD rows, 17 schemes, 13 years).
- **`Portal_Documents/Guidelines/`** — Official UP MLA-LADS Guidelines, Hindi/English FAQs, and Hindi Pocket Book PDFs.
- **`DPR_Atul_Pradhan_9to10Lakh/`** — 54 DPR PDFs + summary for MLA #44 Atul Pradhan (works costing 9–10 Lakhs).

## Scripts

- `scrape_up_yearwise_fund.py` — Scrapes year-wise MLA/MLC fund & physical progress data from `mlaladsup.in`.
- `run_full_scraper.py` — Scrapes all individual works for all 512 UP MLAs/MLCs.
- `download_dpr_v3.py` — Bulk DPR PDF downloader (`getDPRDetails` API, resumes from cache, URL-encodes Hindi paths).
- `download_atul_dpr.py` — Targeted DPR PDF downloader for MLA #44 Atul Pradhan (9–10 Lakh works).
- `scrape_rajasthan.py` — Scrapes Rajasthan RDPRWMS scheme/year-wise data.
