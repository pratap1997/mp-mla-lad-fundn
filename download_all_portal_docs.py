# UP MLA-LAD Portal — Bulk Document Downloader
# Downloads ALL publicly available documents from mlaladsup.in:
# Category A: Static guideline PDFs (4 files)
# Category B: DPR PDFs for all works (via getDPRDetails API)
# Category C: Before-work photo URLs saved as CSV
# Output: Portal_Documents/ inside Desktop/Mla funds/

import sys, os, json, re, time, csv, html, urllib.request, urllib.error
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8')

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE        = 'https://mlaladsup.in'
WORKS_URL   = f'{BASE}/Main/getNikayDistrictWise'
OUT_DIR     = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mla funds', 'Portal_Documents')
GUIDE_DIR   = os.path.join(OUT_DIR, 'Guidelines')
DPR_DIR     = os.path.join(OUT_DIR, 'DPR_PDFs')
LOG_CSV     = os.path.join(OUT_DIR, 'download_log.csv')
PHOTO_CSV   = os.path.join(OUT_DIR, 'photo_urls.csv')

YEARS       = {'2': '2023-24', '3': '2024-25', '4': '2025-26', '5': '2026-27'}
MAX_WORKERS = 8    # parallel download threads
RETRY       = 3    # retries per file
DELAY       = 0.3  # polite delay between requests

HEADERS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*',
    'Referer': 'https://mlaladsup.in/',
}
HEADERS_DL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/pdf,*/*',
    'Referer': 'https://mlaladsup.in/',
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.t = []
    def handle_data(self, d):
        if d.strip(): self.t.append(d.strip())
    def get(self): return ' '.join(self.t)

def strip_html(v):
    if not isinstance(v, str): return str(v) if v is not None else ''
    p = _Text(); p.feed(html.unescape(v)); return p.get().strip()

def post_json(url, payload, attempt=1):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HEADERS_JSON, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        if attempt < RETRY:
            time.sleep(DELAY * 3)
            return post_json(url, payload, attempt + 1)
        return None

def download_file(url, dest_path, attempt=1):
    """Download a single file. Returns (success, bytes_saved, error_msg)."""
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 100:
        return True, os.path.getsize(dest_path), 'already_exists'
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(url, headers=HEADERS_DL)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            # Only save if it looks like a real file (not an error HTML page)
            if len(data) < 100:
                return False, 0, 'too_small'
            with open(dest_path, 'wb') as f:
                f.write(data)
            return True, len(data), ''
    except urllib.error.HTTPError as e:
        if attempt < RETRY and e.code in (500, 502, 503, 429):
            time.sleep(DELAY * 5)
            return download_file(url, dest_path, attempt + 1)
        return False, 0, f'HTTP_{e.code}'
    except Exception as e:
        if attempt < RETRY:
            time.sleep(DELAY * 3)
            return download_file(url, dest_path, attempt + 1)
        return False, 0, str(e)[:80]

def safe_filename(s, max_len=80):
    """Make a string safe for use as a filename."""
    s = re.sub(r'[\\/:*?"<>|]', '_', str(s))
    s = re.sub(r'\s+', '_', s)
    return s[:max_len].strip('._')

# ─── PHASE A — Static guideline PDFs ─────────────────────────────────────────

STATIC_DOCS = [
    (f'{BASE}/Uploads/Guideline_MLALADS_F1.pdf',               'Guideline_MLALADS_F1.pdf'),
    (f'{BASE}/Uploads/FAQ on Guidelines_MLALADS -Hindi.pdf',    'FAQ_Guidelines_Hindi.pdf'),
    (f'{BASE}/Uploads/FAQ on Guidelines_MLALADS.pdf',           'FAQ_Guidelines_English.pdf'),
    (f'{BASE}/Uploads/Hindi Pocket_MLALADS.pdf',                'Hindi_Pocket_Book.pdf'),
]

def download_static_docs():
    os.makedirs(GUIDE_DIR, exist_ok=True)
    results = []
    print('\n[A] Downloading static guideline PDFs...')
    for url, fname in STATIC_DOCS:
        dest = os.path.join(GUIDE_DIR, fname)
        enc_url = urllib.parse.quote(url, safe=':/?=&')
        ok, sz, err = download_file(enc_url, dest)
        status = '✅' if ok else '❌'
        print(f'  {status} {fname} ({sz:,} bytes) {err}')
        results.append({'category': 'Guideline', 'url': url, 'dest': dest,
                        'success': ok, 'bytes': sz, 'error': err})
    return results

# ─── PHASE B — DPR PDF bulk download ─────────────────────────────────────────

def get_mla_list():
    """Get all MLA seat IDs from dropdown."""
    print('\n  Fetching MLA list...')
    payload = {"obj": {"cntrlId": "cmbSeat", "optMode": "bindMLA",
                       "seatTypeId": "1", "districtId": -1}}
    drop_url = f'{BASE}/DropdownBinder/fillDropdown'
    resp = post_json(drop_url, payload)
    if isinstance(resp, list):
        return [(str(r.get('value', r.get('id', ''))),
                 strip_html(str(r.get('text', r.get('name', '')))))
                for r in resp if r.get('value') and str(r.get('value', '')) != '-1']
    return []

def extract_dpr_links(row):
    """
    Extract DPR PDF href and photo href from a getDPRDetails row.
    Returns: (dpr_url_or_none, photo_url_or_none, metadata_dict)
    """
    dpr_url   = None
    photo_url = None

    for k, v in row.items():
        if not isinstance(v, str): continue
        # DPR link column
        if 'डीo पीo आरo' in k or 'DPR' in k:
            m = re.search(r'href=["\']([^"\']+\.pdf)["\']', v, re.I)
            if m:
                href = m.group(1).strip()
                if href and href != '#':
                    dpr_url = BASE + href if href.startswith('/') else href
        # Photo column
        if 'फोटो' in k:
            m = re.search(r'href=["\']([^"\']+)["\']', v, re.I)
            if m:
                href = m.group(1).strip()
                if href and href != '#' and href != '':
                    photo_url = BASE + href if href.startswith('/') else href

    meta = {
        'work_type':    strip_html(str(row.get('कार्य का प्रकार', ''))),
        'work_desc':    strip_html(str(row.get('कार्य का विवरण', '')))[:60],
        'district':     strip_html(str(row.get('जनपद ', row.get('जनपद', '')))),
        'nikay':        strip_html(str(row.get('निकाय', ''))),
        'ward':         strip_html(str(row.get('वार्ड का नाम', ''))),
        'grant_type':   strip_html(str(row.get('अनुदान', ''))),
        'status':       strip_html(str(row.get('वर्तमान स्थित', ''))),
        'proposed_cost':strip_html(str(row.get('प्रस्तावित लागत (रुo में)1', ''))),
        'entry_date':   strip_html(str(row.get('दर्ज करने की तिथि', ''))),
    }
    return dpr_url, photo_url, meta

def fetch_dpr_for_mla(seat_id, mla_name, year_id):
    """Fetch getDPRDetails for one MLA, one year. Returns list of (dpr_url, photo_url, meta)."""
    payload = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                       "yearId": year_id, "seatId": seat_id, "seatTypeId": "1"}}
    resp = post_json(WORKS_URL, payload)
    if not resp or not isinstance(resp, dict):
        return []
    rows = resp.get('Table_0', [])
    results = []
    for row in rows:
        dpr_url, photo_url, meta = extract_dpr_links(row)
        meta['seat_id']   = seat_id
        meta['mla_name']  = mla_name
        meta['year_id']   = year_id
        meta['year_label']= YEARS.get(str(year_id), year_id)
        results.append((dpr_url, photo_url, meta))
    return results

def download_dpr_task(task):
    """Worker task: download one DPR PDF. task=(url, dest_path, meta)"""
    url, dest, meta = task
    ok, sz, err = download_file(url, dest)
    return ok, sz, err, url, dest, meta

def download_all_dprs():
    """Main DPR download orchestrator."""
    os.makedirs(DPR_DIR, exist_ok=True)

    # --- Step 1: Collect all DPR links via API ---
    print('\n[B] Fetching all DPR metadata via API...')
    print('    (This calls getDPRDetails for all 4 years × all 403 MLAs)')

    # First try the bulk call (seatId=-1) per year
    all_links   = []  # (dpr_url, photo_url, meta)
    photo_rows  = []

    for year_id, year_label in YEARS.items():
        print(f'  Year {year_label} — bulk fetch (seatId=-1)...')
        payload = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                           "yearId": year_id, "seatId": "-1", "seatTypeId": "1"}}
        resp = post_json(WORKS_URL, payload)
        rows = resp.get('Table_0', []) if isinstance(resp, dict) else []
        print(f'    → {len(rows)} rows')

        for row in rows:
            dpr_url, photo_url, meta = extract_dpr_links(row)
            meta['year_id']    = year_id
            meta['year_label'] = year_label
            meta['seat_id']    = ''
            meta['mla_name']   = strip_html(str(row.get('प्रस्तावक का नाम व पदनाम', '')))
            if dpr_url:
                all_links.append((dpr_url, photo_url, meta))
            if photo_url:
                photo_rows.append({'year': year_label, 'photo_url': photo_url,
                                   'district': meta['district'], 'work': meta['work_desc']})

        time.sleep(1)

    # Also try MLC (seatTypeId=2)
    for year_id, year_label in YEARS.items():
        payload = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                           "yearId": year_id, "seatId": "-1", "seatTypeId": "2"}}
        resp = post_json(WORKS_URL, payload)
        rows = resp.get('Table_0', []) if isinstance(resp, dict) else []
        if rows:
            print(f'  MLC Year {year_label}: {len(rows)} rows')
        for row in rows:
            dpr_url, photo_url, meta = extract_dpr_links(row)
            meta['year_id'] = year_id; meta['year_label'] = year_label
            meta['seat_id'] = ''; meta['mla_name'] = strip_html(str(row.get('प्रस्तावक का नाम व पदनाम', '')))
            meta['house'] = 'MLC'
            if dpr_url:
                all_links.append((dpr_url, photo_url, meta))
            if photo_url:
                photo_rows.append({'year': year_label, 'photo_url': photo_url,
                                   'district': meta['district'], 'work': meta['work_desc']})
        time.sleep(0.5)

    # Deduplicate by URL
    seen_urls = set()
    unique_links = []
    for item in all_links:
        url = item[0]
        if url not in seen_urls:
            seen_urls.add(url)
            unique_links.append(item)

    print(f'\n  Total DPR rows with actual PDF links : {len(unique_links)}')
    print(f'  Total photo links found              : {len(photo_rows)}')

    # Save photo URLs
    if photo_rows:
        with open(PHOTO_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=['year','district','work','photo_url'])
            w.writeheader()
            w.writerows(photo_rows)
        print(f'  Photo URLs saved → {PHOTO_CSV}')

    # --- Step 2: Build download task list ---
    tasks = []
    for dpr_url, photo_url, meta in unique_links:
        # Build local path: DPR_PDFs / year / district / filename
        year_safe    = safe_filename(meta.get('year_label', 'unknown'))
        district_safe= safe_filename(meta.get('district', 'unknown'))
        # Extract filename from URL
        url_path  = urllib.parse.urlparse(dpr_url).path
        fname_raw = os.path.basename(url_path)
        fname     = urllib.parse.unquote(fname_raw) if fname_raw else 'dpr.pdf'
        fname     = safe_filename(fname, max_len=120)
        if not fname.lower().endswith('.pdf'):
            fname += '.pdf'

        dest = os.path.join(DPR_DIR, year_safe, district_safe, fname)
        tasks.append((dpr_url, dest, meta))

    print(f'\n  Starting download of {len(tasks)} DPR PDFs...')
    print(f'  Using {MAX_WORKERS} parallel workers\n')

    # --- Step 3: Parallel download ---
    log_rows = []
    done = skipped = failed = 0
    total = len(tasks)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_dpr_task, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            ok, sz, err, url, dest, meta = future.result()
            if ok:
                if err == 'already_exists':
                    skipped += 1
                else:
                    done += 1
            else:
                failed += 1

            log_rows.append({
                'success':   ok,
                'bytes':     sz,
                'error':     err,
                'year':      meta.get('year_label'),
                'district':  meta.get('district'),
                'mla_name':  meta.get('mla_name'),
                'work_desc': meta.get('work_desc'),
                'status':    meta.get('status'),
                'url':       url,
                'dest':      dest,
            })

            if i % 100 == 0 or i == total:
                pct = i / total * 100
                print(f'  [{i:>5}/{total}] {pct:5.1f}% — ✅{done} ⏭️{skipped} ❌{failed}')

    return log_rows, done, skipped, failed

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    import datetime
    os.makedirs(OUT_DIR, exist_ok=True)
    print('=' * 70)
    print('UP MLA-LAD Portal — Full Document Downloader')
    print(f'Started: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Output : {OUT_DIR}')
    print('=' * 70)

    all_log = []

    # Phase A — Static guidelines
    guide_results = download_static_docs()
    all_log.extend(guide_results)

    # Phase B — DPR PDFs
    dpr_log, done, skipped, failed = download_all_dprs()
    for r in dpr_log:
        all_log.append({
            'category': 'DPR_PDF',
            'url':      r['url'],
            'dest':     r['dest'],
            'success':  r['success'],
            'bytes':    r['bytes'],
            'error':    r['error'],
            'year':     r.get('year'),
            'district': r.get('district'),
            'mla_name': r.get('mla_name'),
            'work_desc':r.get('work_desc'),
            'status':   r.get('status'),
        })

    # Write master log
    if all_log:
        fieldnames = ['category','success','bytes','year','district','mla_name',
                      'work_desc','status','error','url','dest']
        with open(LOG_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            w.writeheader()
            w.writerows(all_log)
        print(f'\n  📋 Download log saved → {LOG_CSV}')

    # Summary
    total_bytes = sum(r.get('bytes', 0) or 0 for r in all_log)
    print('\n' + '=' * 70)
    print('DOWNLOAD COMPLETE')
    print('=' * 70)
    print(f'  Guideline PDFs : {len(guide_results)} files')
    print(f'  DPR PDFs new   : {done}')
    print(f'  DPR PDFs skipped (cached) : {skipped}')
    print(f'  DPR PDFs failed: {failed}')
    print(f'  Total size     : {total_bytes/1024/1024:.1f} MB')
    print(f'  Output folder  : {OUT_DIR}')
    print(f'  Finished: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

if __name__ == '__main__':
    main()
