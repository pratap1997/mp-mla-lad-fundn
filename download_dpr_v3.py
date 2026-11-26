# UP MLA-LAD Portal - DPR PDF Downloader v3
# Robust: short timeouts, skip stalls, URL-encode Hindi paths, resume from cache

import sys, os, json, re, time, csv, html, urllib.request, urllib.error
import urllib.parse, datetime, signal
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

# Force UTF-8 and immediate line buffering
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE      = 'https://mlaladsup.in'
WORKS_URL = f'{BASE}/Main/getNikayDistrictWise'
DROP_URL  = f'{BASE}/DropdownBinder/fillDropdown'
OUT_DIR   = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mla funds', 'Portal_Documents')
DPR_DIR   = os.path.join(OUT_DIR, 'DPR_PDFs')
LOG_PATH  = os.path.join(OUT_DIR, 'download_log.csv')
PHOTO_PATH= os.path.join(OUT_DIR, 'photo_urls.csv')
PROG_LOG  = os.path.join(OUT_DIR, 'progress.txt')   # human-readable live log

YEARS       = [('2','2023-24'), ('3','2024-25'), ('4','2025-26'), ('5','2026-27')]
API_TIMEOUT = 25    # seconds per API call before giving up on that MLA+year
DL_TIMEOUT  = 40    # seconds per PDF download
MAX_DL      = 8     # parallel download threads
RETRY       = 2

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

os.makedirs(DPR_DIR, exist_ok=True)

def log(msg):
    ts  = datetime.datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(PROG_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

class _T(HTMLParser):
    def __init__(self): super().__init__(); self.t = []
    def handle_data(self, d):
        if d.strip(): self.t.append(d.strip())
    def get(self): return ' '.join(self.t)

def sh(v):
    if not isinstance(v, str): return str(v) if v else ''
    p = _T(); p.feed(html.unescape(v)); return p.get().strip()

def encode_url(url):
    try:
        p = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((
            p.scheme, p.netloc,
            urllib.parse.quote(p.path, safe='/-_.~'),
            p.params, p.query, p.fragment
        ))
    except Exception:
        return url

def post(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HDRS_JSON, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return None   # caller handles None gracefully

def dl_file(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 500:
        return True, os.path.getsize(dest), 'cached'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    safe = encode_url(url)
    for attempt in range(1, RETRY + 1):
        try:
            req = urllib.request.Request(safe, headers=HDRS_DL)
            with urllib.request.urlopen(req, timeout=DL_TIMEOUT) as r:
                data = r.read()
            if len(data) < 300:
                return False, 0, 'too_small'
            with open(dest, 'wb') as f:
                f.write(data)
            return True, len(data), ''
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, 0, 'HTTP_404'
            if attempt < RETRY and e.code in (429, 500, 502, 503):
                time.sleep(4)
                continue
            return False, 0, f'HTTP_{e.code}'
        except Exception as e:
            if attempt < RETRY:
                time.sleep(3)
                continue
            return False, 0, str(e)[:80]
    return False, 0, 'max_retries'

def safe_fn(s, n=110):
    s = re.sub(r'[\\/:*?"<>|]', '_', str(s))
    s = re.sub(r'\s+', '_', s)
    return s[:n].strip('._') or 'file'

def get_seats(seat_type_id):
    r = post(DROP_URL, {"obj": {"cntrlId": "cmbSeat", "optMode": "bindMLA",
                                "seatTypeId": seat_type_id, "districtId": -1}})
    if not isinstance(r, list): return []
    return [(str(x.get('value','')), sh(str(x.get('text',''))))
            for x in r if str(x.get('value','')) not in ('','-1','0')]

def extract_links(row):
    dpr = photo = None
    for k, v in row.items():
        if not isinstance(v, str): continue
        if 'पीo आरo' in k or 'DPR' in k.upper():
            m = re.search(r'href=["\']([^"\']+\.pdf)["\']', v, re.I)
            if m:
                h = m.group(1).strip()
                if h and h not in ('', '#'):
                    dpr = (BASE + h) if h.startswith('/') else h
        if 'फोटो' in k:
            m = re.search(r'href=["\']([^"\'#][^"\']*)["\']', v, re.I)
            if m:
                h = m.group(1).strip()
                if h and len(h) > 4:
                    photo = (BASE + h) if h.startswith('/') else h
    return dpr, photo

def main():
    log('=' * 60)
    log('UP MLA-LAD DPR Downloader v3 — Robust + Resume')
    log('=' * 60)

    log('Fetching seat lists...')
    mla = get_seats('1')
    mlc = get_seats('2')
    log(f'  MLA: {len(mla)} | MLC: {len(mlc)}')

    all_seats = [('1','MLA', sid, name) for sid, name in mla] + \
                [('2','MLC', sid, name) for sid, name in mlc]

    total_combos = len(all_seats) * len(YEARS)
    log(f'Total API calls planned: {total_combos}')

    log_f   = open(LOG_PATH,   'w', newline='', encoding='utf-8-sig')
    photo_f = open(PHOTO_PATH, 'w', newline='', encoding='utf-8-sig')
    log_w   = csv.writer(log_f)
    photo_w = csv.writer(photo_f)
    log_w.writerow(['seat_type','seat_id','mla_name','year','district',
                    'work_desc','status','cost','dpr_url','local_path',
                    'success','bytes','error'])
    photo_w.writerow(['seat_id','mla_name','year','district','work_desc','photo_url'])

    ok = skip = fail = no_pdf = 0
    total_bytes = 0
    combo = 0
    pending = {}   # future -> row_meta

    def flush_pending(wait_all=False):
        nonlocal ok, skip, fail, total_bytes
        done = []
        check = list(pending.items())
        if wait_all:
            futs = [f for f, _ in check]
            if futs:
                wait(futs)
            check = list(pending.items())
        for fut, meta in check:
            if fut.done():
                success, sz, err = fut.result()
                meta.update({'success': success, 'bytes': sz, 'error': err})
                log_w.writerow([meta['seat_type'], meta['seat_id'], meta['mla_name'],
                                 meta['year'], meta['district'], meta['work_desc'],
                                 meta['status'], meta['cost'], meta['dpr_url'],
                                 meta['local_path'], success, sz, err])
                if success:
                    if err == 'cached': skip += 1
                    else: ok += 1
                    total_bytes += sz
                else:
                    fail += 1
                done.append(fut)
        for f in done:
            del pending[f]

    executor = ThreadPoolExecutor(max_workers=MAX_DL)

    try:
        for stype, house, sid, name in all_seats:
            for year_id, year_label in YEARS:
                combo += 1
                pct = combo / total_combos * 100

                # API call with hard timeout
                resp = post(WORKS_URL, {"obj": {
                    "optMode":    "getDPRDetails",
                    "districtId": -1,
                    "yearId":     year_id,
                    "seatId":     sid,
                    "seatTypeId": stype,
                }})

                rows = []
                if isinstance(resp, dict) and 'Table_0' in resp:
                    rows = resp['Table_0']
                elif isinstance(resp, list):
                    rows = resp

                if not rows:
                    if combo % 50 == 0:
                        log(f'[{combo}/{total_combos} {pct:.1f}%] {house} {name[:18]} {year_label} → 0 rows | ok={ok} skip={skip} fail={fail}')
                    continue

                mla_pdfs = 0
                for row in rows:
                    dpr_url, photo_url = extract_links(row)
                    district  = sh(str(row.get('जनपद ', row.get('जनपद',''))))
                    work_desc = sh(str(row.get('कार्य का विवरण','')))[:55]
                    status    = sh(str(row.get('वर्तमान स्थित','')))
                    cost      = sh(str(row.get('प्रस्तावित लागत (रुo में)1','')))

                    if photo_url:
                        photo_w.writerow([sid, name, year_label,
                                          district, work_desc, photo_url])

                    if not dpr_url:
                        no_pdf += 1
                        continue

                    url_path = urllib.parse.urlparse(dpr_url).path
                    fname    = urllib.parse.unquote(os.path.basename(url_path))
                    fname    = safe_fn(fname, 110)
                    if not fname.lower().endswith('.pdf'):
                        fname += '.pdf'
                    dest = os.path.join(DPR_DIR,
                                        safe_fn(year_label),
                                        safe_fn(district) or 'Unknown',
                                        fname)

                    meta = dict(seat_type=house, seat_id=sid, mla_name=name,
                                year=year_label, district=district,
                                work_desc=work_desc, status=status,
                                cost=cost, dpr_url=dpr_url, local_path=dest)

                    fut = executor.submit(dl_file, dpr_url, dest)
                    pending[fut] = meta
                    mla_pdfs += 1

                    if len(pending) > 60:
                        flush_pending(wait_all=False)

                # Always log when PDFs found for this MLA
                if mla_pdfs > 0 or combo % 20 == 0:
                    log(f'[{combo}/{total_combos} {pct:.1f}%] {house} {name[:18]:<18} {year_label} → {len(rows)} rows, {mla_pdfs} PDFs | ok={ok} skip={skip} fail={fail} | {total_bytes/1024/1024:.1f}MB')

                if combo % 10 == 0:
                    log_f.flush(); photo_f.flush()

                time.sleep(0.15)

        log('All API calls done. Waiting for pending downloads...')
        flush_pending(wait_all=True)

    except KeyboardInterrupt:
        log('Interrupted — flushing...')
        flush_pending(wait_all=True)
    finally:
        executor.shutdown(wait=False)
        log_f.flush(); log_f.close()
        photo_f.flush(); photo_f.close()

    log('=' * 60)
    log('DONE')
    log(f'  Combos     : {combo}')
    log(f'  No PDF link: {no_pdf}')
    log(f'  Downloaded : {ok}')
    log(f'  Cached     : {skip}')
    log(f'  Failed     : {fail}')
    log(f'  Total size : {total_bytes/1024/1024:.1f} MB')
    log(f'  Output     : {OUT_DIR}')

if __name__ == '__main__':
    main()
