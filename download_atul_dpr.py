import sys
import json
import os
import re
import urllib.request
import urllib.error
import time
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://mlaladsup.in"
SEAT_ID = 240010268
SEAT_TYPE_ID = 1
MLA_NAME = "44 Sri Atul Pradhan"
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "DPR_Atul_Pradhan_9to10Lakh")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/pdf,application/octet-stream,*/*',
    'Referer': 'https://mlaladsup.in/'
}

def clean_text(val):
    if not val:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(val))
    return re.sub(r'\s+', ' ', text).strip()

def extract_href(html_val):
    if not html_val:
        return ""
    soup = BeautifulSoup(str(html_val), 'html.parser')
    a = soup.find('a')
    if a:
        href = a.get('href', '').strip()
        if href and href not in ['', '#section', '#', 'javascript:void(0)']:
            if href.startswith('/'):
                return BASE_URL + href
            elif href.startswith('http'):
                return href
    return ""

def safe_filename(work_id, work_desc, cost):
    desc_clean = re.sub(r'[^\w\u0900-\u097F ]', '', clean_text(work_desc))[:40].strip()
    return f"WID_{work_id}_{cost}L_{desc_clean}.pdf"

def download_pdf(url, filepath, work_id):
    if not url or url.strip() == "":
        return False, "No URL"
    try:
        # Encode spaces and special chars in the URL path only
        from urllib.parse import quote
        # Split into scheme+host and path
        if '/Uploads/Files/' in url:
            base, path = url.split('/Uploads/Files/', 1)
            encoded_url = base + '/Uploads/Files/' + quote(path, safe='/-.')
        else:
            encoded_url = url
        req = urllib.request.Request(encoded_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if len(content) < 500:
                return False, f"File too small: {len(content)} bytes"
            with open(filepath, 'wb') as f:
                f.write(content)
            return True, f"{len(content)} bytes"
    except Exception as e:
        return False, str(e)

# Load cached data
cache_file = os.path.join("raw_data", f"mla_{SEAT_TYPE_ID}_{SEAT_ID}.json")
print(f"Loading data from: {cache_file}")
with open(cache_file, encoding='utf-8') as f:
    data = json.load(f)
rows = data.get('Table_0', [])
print(f"Total works for {MLA_NAME}: {len(rows)}")

# Discover keys
cost_key = None
dpr_key = None
for k in rows[0].keys():
    if 'लागत' in k and 'आगणित' in k:
        cost_key = k
    if 'डीoपीoआरo' in k and 'प्रेषित' in k:
        dpr_key = k

print(f"Cost key: {repr(cost_key)}")
print(f"DPR key:  {repr(dpr_key)}")

# Filter 9 <= cost <= 10 Lakhs
target_works = []
for r in rows:
    cost_raw = r.get(cost_key, None)
    try:
        c = float(cost_raw) if cost_raw is not None else 0.0
    except (ValueError, TypeError):
        c = 0.0

    if 9.0 <= c <= 10.0:
        dpr_href = extract_href(r.get(dpr_key, ''))
        target_works.append({
            'work_id': r.get('कार्य आईoडीo'),
            'cost_lakhs': c,
            'desc': clean_text(r.get('कार्य का विवरण', '')),
            'work_type': clean_text(r.get('कार्य का प्रकार', '')),
            'district': clean_text(r.get('जनपद', '')),
            'block': clean_text(r.get('ब्लॉक/निकाय ', '')),
            'year': r.get('वित्तीय वर्ष', ''),
            'dpr_url': dpr_href,
            'dpr_raw': str(r.get(dpr_key, ''))
        })

print(f"\nWorks between 9-10 Lakhs: {len(target_works)}")

# Separate by DPR availability
with_dpr = [w for w in target_works if w['dpr_url']]
without_dpr = [w for w in target_works if not w['dpr_url']]
print(f"  With DPR PDF URL:    {len(with_dpr)}")
print(f"  Without DPR PDF URL: {len(without_dpr)}")

# Download DPR PDFs
print(f"\n{'='*60}")
print(f"Downloading DPR PDFs to: {DOWNLOAD_DIR}")
print(f"{'='*60}\n")

results = []
for i, w in enumerate(with_dpr, 1):
    fname = safe_filename(w['work_id'], w['desc'], w['cost_lakhs'])
    fpath = os.path.join(DOWNLOAD_DIR, fname)

    if os.path.exists(fpath) and os.path.getsize(fpath) > 500:
        print(f"[{i}/{len(with_dpr)}] SKIP (cached): {fname}")
        results.append({**w, 'status': 'cached', 'filename': fname})
        continue

    success, msg = download_pdf(w['dpr_url'], fpath, w['work_id'])
    status = 'downloaded' if success else 'failed'
    icon = '✓' if success else '✗'
    print(f"[{i}/{len(with_dpr)}] {icon} WID={w['work_id']} | Cost={w['cost_lakhs']}L | {status}: {msg}")
    if not success:
        print(f"      URL was: {w['dpr_url']}")
    results.append({**w, 'status': status, 'filename': fname if success else ''})
    time.sleep(0.3)

# Summary report
ok = [r for r in results if r['status'] in ('downloaded', 'cached')]
failed = [r for r in results if r['status'] == 'failed']
print(f"\n{'='*60}")
print(f"DOWNLOAD SUMMARY")
print(f"{'='*60}")
print(f"Total works 9-10L:      {len(target_works)}")
print(f"With DPR PDF:           {len(with_dpr)}")
print(f"Without DPR PDF:        {len(without_dpr)}")
print(f"Successfully downloaded: {len(ok)}")
print(f"Failed:                  {len(failed)}")

# Save manifest CSV
manifest_path = os.path.join(DOWNLOAD_DIR, "manifest.csv")
import csv
with open(manifest_path, 'w', newline='', encoding='utf-8-sig') as f:
    fieldnames = ['work_id', 'cost_lakhs', 'year', 'district', 'block', 'work_type', 'desc', 'dpr_url', 'status', 'filename']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    all_records = results + [{**w, 'status': 'no_dpr', 'filename': ''} for w in without_dpr]
    for r in all_records:
        writer.writerow({k: r.get(k, '') for k in fieldnames})

print(f"\nManifest saved: {manifest_path}")
print(f"PDFs folder:    {DOWNLOAD_DIR}")

if failed:
    print(f"\nFailed downloads:")
    for r in failed:
        print(f"  WID={r['work_id']}: {r['dpr_url']}")
