# UP MLA-LAD Portal - Fast DPR PDF Downloader v4
# getDPRDetails returns all rows for a year regardless of seatId,
# so we fetch 1 year at a time (4 calls total) + gc.collect() to keep RAM low,
# deduplicate PDF URLs, and download in parallel with URL-encoded Hindi paths.

import sys, os, json, re, time, csv, html, gc
import urllib.request, urllib.error, urllib.parse, datetime
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE       = 'https://mlaladsup.in'
WORKS_URL  = f'{BASE}/Main/getNikayDistrictWise'
OUT_DIR    = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mla funds', 'Portal_Documents')
DPR_DIR    = os.path.join(OUT_DIR, 'DPR_PDFs')
LOG_PATH   = os.path.join(OUT_DIR, 'download_log.csv')
PHOTO_PATH = os.path.join(OUT_DIR, 'photo_urls.csv')
PROG_LOG   = os.path.join(OUT_DIR, 'progress.txt')

YEARS      = [('2', '2023-24'), ('3', '2024-25'), ('4', '2025-26'), ('5', '2026-27')]
SEAT_TYPES = [('1', 'MLA'), ('2', 'MLC')]
API_TIMEOUT = 180
DL_TIMEOUT  = 45
MAX_DL      = 10
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
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(PROG_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


class _T(HTMLParser):
    def __init__(self):
        super().__init__()
        self.t = []

    def handle_data(self, d):
        if d.strip():
            self.t.append(d.strip())

    def get(self):
        return ' '.join(self.t)


def sh(v):
    if not isinstance(v, str):
        return str(v) if v else ''
    p = _T()
    p.feed(html.unescape(v))
    return p.get().strip()


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


def safe_fn(s, n=110):
    s = re.sub(r'[\\/:*?"<>|]', '_', str(s))
    s = re.sub(r'\s+', '_', s)
    return s[:n].strip('._') or 'file'


def post(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HDRS_JSON, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        log(f'  API error: {e}')
        return None


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


def extract_links(row):
    dpr = photo = None
    for k, v in row.items():
        if not isinstance(v, str):
            continue
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
    log('UP MLA-LAD DPR Downloader v4 — Bulk Year-by-Year')
    log('=' * 60)

    seen_urls = set()
    log_f = open(LOG_PATH, 'w', newline='', encoding='utf-8-sig')
    photo_f = open(PHOTO_PATH, 'w', newline='', encoding='utf-8-sig')
    log_w = csv.writer(log_f)
    photo_w = csv.writer(photo_f)
    log_w.writerow(['house', 'mla_name', 'year', 'district',
                    'work_desc', 'status', 'cost', 'dpr_url', 'local_path',
                    'success', 'bytes', 'error'])
    photo_w.writerow(['house', 'mla_name', 'year', 'district', 'work_desc', 'photo_url'])

    total_ok = total_skip = total_fail = total_no_pdf = 0
    total_bytes = 0

    try:
        for year_id, year_label in YEARS:
            for stype, house in SEAT_TYPES:
                log(f'Fetching {year_label} | {house} (seatId=-1)...')
                resp = post(WORKS_URL, {"obj": {
                    "optMode": "getDPRDetails",
                    "districtId": -1,
                    "yearId": year_id,
                    "seatId": "-1",
                    "seatTypeId": stype,
                }})
                rows = resp.get('Table_0', []) if isinstance(resp, dict) else []
                del resp
                gc.collect()
                log(f'  Received {len(rows)} rows for {year_label} | {house}')
                if not rows:
                    continue

                tasks = []
                for row in rows:
                    dpr_url, photo_url = extract_links(row)
                    district = sh(str(row.get('जनपद ', row.get('जनपद', ''))))
                    work_desc = sh(str(row.get('कार्य का विवरण', '')))[:60]
                    status = sh(str(row.get('वर्तमान स्थित', '')))
                    cost = sh(str(row.get('प्रस्तावित लागत (रुo में)1', '')))
                    mla_name = sh(str(row.get('प्रस्तावक का नाम व पदनाम', '')))

                    if photo_url:
                        photo_w.writerow([house, mla_name, year_label, district, work_desc, photo_url])

                    if not dpr_url:
                        total_no_pdf += 1
                        continue
                    if dpr_url in seen_urls:
                        continue
                    seen_urls.add(dpr_url)

                    url_path = urllib.parse.urlparse(dpr_url).path
                    fname = urllib.parse.unquote(os.path.basename(url_path))
                    fname = safe_fn(fname, 110)
                    if not fname.lower().endswith('.pdf'):
                        fname += '.pdf'
                    dest = os.path.join(DPR_DIR, safe_fn(year_label), safe_fn(district) or 'Unknown', fname)

                    tasks.append((dpr_url, dest, {
                        'house': house, 'mla_name': mla_name, 'year': year_label,
                        'district': district, 'work_desc': work_desc,
                        'status': status, 'cost': cost,
                        'dpr_url': dpr_url, 'local_path': dest,
                    }))

                del rows
                gc.collect()

                log(f'  Unique new PDFs to download for {year_label} | {house}: {len(tasks)}')
                if not tasks:
                    continue

                with ThreadPoolExecutor(max_workers=MAX_DL) as ex:
                    futs = {ex.submit(dl_file, u, d): m for u, d, m in tasks}
                    for i, fut in enumerate(as_completed(futs), 1):
                        m = futs[fut]
                        ok, sz, err = fut.result()
                        log_w.writerow([m['house'], m['mla_name'], m['year'], m['district'],
                                        m['work_desc'], m['status'], m['cost'], m['dpr_url'],
                                        m['local_path'], ok, sz, err])
                        if ok:
                            if err == 'cached':
                                total_skip += 1
                            else:
                                total_ok += 1
                            total_bytes += sz
                        else:
                            total_fail += 1

                        if i % 200 == 0 or i == len(tasks):
                            log_f.flush()
                            photo_f.flush()
                            log(f'  [{year_label} {house}] {i}/{len(tasks)} | ok={total_ok} skip={total_skip} fail={total_fail} | {total_bytes/1024/1024:.1f} MB')

                del tasks
                gc.collect()
    finally:
        log_f.flush()
        log_f.close()
        photo_f.flush()
        photo_f.close()

    log('=' * 60)
    log('DOWNLOAD COMPLETE')
    log(f'  No PDF link : {total_no_pdf}')
    log(f'  Downloaded  : {total_ok}')
    log(f'  Cached      : {total_skip}')
    log(f'  Failed      : {total_fail}')
    log(f'  Total size  : {total_bytes/1024/1024:.1f} MB')
    log('=' * 60)


if __name__ == '__main__':
    main()
