# UP MLA-LAD Portal - Bulk DPR PDF Downloader
# Fetches DPR metadata per-MLA (small payloads) then downloads PDFs immediately
# Memory-efficient: processes one MLA at a time, never loads all data at once

import sys, os, json, re, time, csv, html, urllib.request, urllib.error
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE      = 'https://mlaladsup.in'
WORKS_URL = f'{BASE}/Main/getNikayDistrictWise'
DROP_URL  = f'{BASE}/DropdownBinder/fillDropdown'
OUT_DIR   = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mla funds', 'Portal_Documents')
DPR_DIR   = os.path.join(OUT_DIR, 'DPR_PDFs')
LOG_CSV   = os.path.join(OUT_DIR, 'download_log.csv')
PHOTO_CSV = os.path.join(OUT_DIR, 'photo_urls.csv')

YEARS       = [('2','2023-24'), ('3','2024-25'), ('4','2025-26'), ('5','2026-27')]
MAX_DL_THREADS = 6
RETRY       = 3

HDRS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': '*/*',
    'Referer': 'https://mlaladsup.in/',
}
HDRS_DL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/pdf,*/*',
    'Referer': 'https://mlaladsup.in/',
}

# ── helpers ───────────────────────────────────────────────────

class _T(HTMLParser):
    def __init__(self): super().__init__(); self.t=[]
    def handle_data(self,d):
        if d.strip(): self.t.append(d.strip())
    def get(self): return ' '.join(self.t)

def sh(v):
    if not isinstance(v,str): return str(v) if v else ''
    p=_T(); p.feed(html.unescape(v)); return p.get().strip()

def post(url, payload, attempt=1):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HDRS_JSON, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        if attempt < RETRY:
            time.sleep(3)
            return post(url, payload, attempt+1)
        return None

def encode_url(url):
    """Properly encode a URL that may contain Hindi text, spaces, brackets."""
    try:
        parsed = urllib.parse.urlparse(url)
        # Encode path: quote everything except safe URL path chars
        enc_path = urllib.parse.quote(parsed.path, safe='/-_.~')
        # Reconstruct
        return urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, enc_path,
            parsed.params, parsed.query, parsed.fragment
        ))
    except Exception:
        return url

def dl_file(url, dest, attempt=1):
    if os.path.exists(dest) and os.path.getsize(dest) > 500:
        return True, os.path.getsize(dest), 'cached'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    safe_url = encode_url(url)
    req = urllib.request.Request(safe_url, headers=HDRS_DL)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
        if len(data) < 200:
            return False, 0, 'too_small'
        with open(dest, 'wb') as f:
            f.write(data)
        return True, len(data), ''
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, 0, 'HTTP_404'
        if attempt < RETRY and e.code in (500,502,503,429):
            time.sleep(5)
            return dl_file(url, dest, attempt+1)
        return False, 0, f'HTTP_{e.code}'
    except Exception as e:
        if attempt < RETRY:
            time.sleep(3)
            return dl_file(url, dest, attempt+1)
        return False, 0, str(e)[:60]

def safe_fn(s, n=100):
    s = re.sub(r'[\\/:*?"<>|]', '_', str(s))
    s = re.sub(r'\s+', '_', s)
    return s[:n].strip('._') or 'file'

def extract_links(row):
    dpr_url = photo_url = None
    for k, v in row.items():
        if not isinstance(v, str): continue
        if 'पीo आरo' in k or 'DPR' in k.upper():
            m = re.search(r'href=["\']([^"\']+\.pdf)["\']', v, re.I)
            if m:
                h = m.group(1).strip()
                if h and h not in ('','#'):
                    dpr_url = (BASE + h) if h.startswith('/') else h
        if 'फोटो' in k:
            m = re.search(r'href=["\']([^"\'#][^"\']*)["\']', v, re.I)
            if m:
                h = m.group(1).strip()
                if h and len(h) > 4:
                    photo_url = (BASE + h) if h.startswith('/') else h
    return dpr_url, photo_url

def get_seat_ids(seat_type_id='1'):
    resp = post(DROP_URL, {"obj": {"cntrlId":"cmbSeat","optMode":"bindMLA",
                                   "seatTypeId": seat_type_id,"districtId":-1}})
    if not isinstance(resp, list): return []
    return [(str(r.get('value','')), sh(str(r.get('text',''))))
            for r in resp if str(r.get('value','')) not in ('','-1','0')]

# ── main ──────────────────────────────────────────────────────

def main():
    os.makedirs(DPR_DIR, exist_ok=True)

    print('='*65)
    print('UP MLA-LAD Portal — DPR PDF Downloader (Memory-Efficient)')
    print(f'Started: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    print('='*65)

    # Get MLA + MLC seat lists
    print('\nFetching seat lists...')
    mla_seats = get_seat_ids('1')
    mlc_seats = get_seat_ids('2')
    print(f'  Vidhan Sabha MLAs : {len(mla_seats)}')
    print(f'  Vidhan Parishad MLCs: {len(mlc_seats)}')

    all_seats = [('1', sid, name) for sid, name in mla_seats] + \
                [('2', sid, name) for sid, name in mlc_seats]

    # Open log file for streaming writes
    log_f = open(LOG_CSV, 'w', newline='', encoding='utf-8-sig')
    photo_f = open(PHOTO_CSV, 'w', newline='', encoding='utf-8-sig')
    log_w = csv.writer(log_f)
    photo_w = csv.writer(photo_f)
    log_w.writerow(['seat_type','seat_id','mla_name','year','district',
                    'work_desc','status','cost','dpr_url','local_path',
                    'success','bytes','error'])
    photo_w.writerow(['seat_id','mla_name','year','district','work_desc','photo_url'])

    total_ok = total_skip = total_fail = total_no_pdf = 0
    total_bytes = 0
    grand_total = len(all_seats) * len(YEARS)
    combo = 0

    # Use a small thread pool just for downloads (not API calls — keep those serial)
    dl_executor = ThreadPoolExecutor(max_workers=MAX_DL_THREADS)
    pending_futures = {}   # future -> (log_row_dict)

    def flush_futures(wait_all=False):
        nonlocal total_ok, total_skip, total_fail, total_bytes
        done_keys = []
        for fut, row in list(pending_futures.items()):
            if wait_all or fut.done():
                ok, sz, err = fut.result()
                row['success'] = ok
                row['bytes']   = sz
                row['error']   = err
                log_w.writerow([row['seat_type'], row['seat_id'], row['mla_name'],
                                 row['year'], row['district'], row['work_desc'],
                                 row['status'], row['cost'], row['dpr_url'],
                                 row['local_path'], ok, sz, err])
                if ok:
                    if err == 'cached': total_skip += 1
                    else:               total_ok   += 1
                    total_bytes += sz
                else:
                    total_fail += 1
                done_keys.append(fut)
        for k in done_keys:
            del pending_futures[k]

    try:
        for seat_type_id, seat_id, mla_name in all_seats:
            house = 'MLA' if seat_type_id == '1' else 'MLC'

            for year_id, year_label in YEARS:
                combo += 1
                pct = combo / grand_total * 100

                # Fetch DPR metadata for this MLA × year
                resp = post(WORKS_URL, {"obj": {
                    "optMode": "getDPRDetails",
                    "districtId": -1,
                    "yearId": year_id,
                    "seatId": seat_id,
                    "seatTypeId": seat_type_id,
                }})

                rows = []
                if isinstance(resp, dict) and 'Table_0' in resp:
                    rows = resp['Table_0']
                elif isinstance(resp, list):
                    rows = resp

                # Process each DPR row
                mla_pdfs = 0
                for row in rows:
                    dpr_url, photo_url = extract_links(row)
                    district  = sh(str(row.get('जनपद ', row.get('जनपद',''))))
                    work_desc = sh(str(row.get('कार्य का विवरण','')))[:60]
                    status    = sh(str(row.get('वर्तमान स्थित','')))
                    cost      = sh(str(row.get('प्रस्तावित लागत (रुo में)1','')))

                    if photo_url:
                        photo_w.writerow([seat_id, mla_name, year_label,
                                          district, work_desc, photo_url])

                    if not dpr_url:
                        total_no_pdf += 1
                        continue

                    # Build local file path
                    url_path = urllib.parse.urlparse(dpr_url).path
                    fname    = urllib.parse.unquote(os.path.basename(url_path))
                    fname    = safe_fn(fname, 120)
                    if not fname.lower().endswith('.pdf'):
                        fname += '.pdf'
                    yr_safe  = safe_fn(year_label)
                    dist_safe= safe_fn(district) if district else 'Unknown'
                    dest     = os.path.join(DPR_DIR, yr_safe, dist_safe, fname)

                    log_row = {
                        'seat_type': house, 'seat_id': seat_id,
                        'mla_name': mla_name, 'year': year_label,
                        'district': district, 'work_desc': work_desc,
                        'status': status, 'cost': cost,
                        'dpr_url': dpr_url, 'local_path': dest,
                    }

                    # Submit download
                    fut = dl_executor.submit(dl_file, dpr_url, dest)
                    pending_futures[fut] = log_row
                    mla_pdfs += 1

                    # Flush completed downloads to keep memory low
                    if len(pending_futures) > 50:
                        flush_futures(wait_all=False)

                # Progress line every 10 combos or when PDFs found
                if combo % 10 == 0 or mla_pdfs > 0:
                    print(f'  [{combo:>4}/{grand_total}] {pct:4.1f}% | '
                          f'{house} {seat_id} {mla_name[:20]:<20} '
                          f'yr={year_label} pdfs={mla_pdfs} | '
                          f'ok={total_ok} skip={total_skip} fail={total_fail}')

                # Flush log periodically
                if combo % 20 == 0:
                    log_f.flush()
                    photo_f.flush()

                time.sleep(0.2)   # polite delay between API calls

        # Wait for all pending downloads to finish
        print('\n  Waiting for all pending downloads to complete...')
        flush_futures(wait_all=True)
        dl_executor.shutdown(wait=True)
        # Flush any remaining
        flush_futures(wait_all=True)

    except KeyboardInterrupt:
        print('\n  Interrupted — flushing results...')
        flush_futures(wait_all=True)
    finally:
        log_f.flush(); log_f.close()
        photo_f.flush(); photo_f.close()

    # Final summary
    print('\n' + '='*65)
    print('DOWNLOAD COMPLETE')
    print('='*65)
    print(f'  Seat×Year combos processed : {combo}')
    print(f'  Rows with no PDF link      : {total_no_pdf}')
    print(f'  PDFs downloaded (new)      : {total_ok}')
    print(f'  PDFs skipped (cached)      : {total_skip}')
    print(f'  PDFs failed                : {total_fail}')
    print(f'  Total downloaded size      : {total_bytes/1024/1024:.1f} MB')
    print(f'  Log  → {LOG_CSV}')
    print(f'  Finished: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}')

if __name__ == '__main__':
    main()
