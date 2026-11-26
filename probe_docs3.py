"""
Final probe: find the actual DPR PDF download URL from ViewDPR page
and decode the anchor id pattern from getDPRDetails
"""
import sys, json, re, urllib.request, html, time
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

HEADERS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': '*/*',
    'Referer': 'https://mlaladsup.in/',
}
HEADERS_GET = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://mlaladsup.in/',
}
BASE = 'https://mlaladsup.in'
WORKS_URL = f'{BASE}/Main/getNikayDistrictWise'

def get(url, extra_headers=None):
    h = dict(HEADERS_GET)
    if extra_headers: h.update(extra_headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8', errors='replace'), r.url
    except Exception as e:
        return f'ERROR: {e}', url

def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HEADERS_JSON, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return f'ERROR: {e}'

# ── 1. Get a small sample from getDPRDetails and decode the anchor ────
print('[1] Decode DPR anchor structure from getDPRDetails:')
payload = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                   "yearId": "3", "seatId": "240010310", "seatTypeId": "1"}}
resp = post_json(WORKS_URL, payload)
if isinstance(resp, dict) and 'Table_0' in resp:
    rows = resp['Table_0'][:5]
    for i, row in enumerate(rows):
        print(f'\n  Row {i+1}:')
        for k, v in row.items():
            print(f'    {k}: {str(v)[:200]}')

# ── 2. Decode column definitions (Col_0) ─────────────────────
print('\n[2] Col_0 definitions:')
if isinstance(resp, dict) and 'Col_0' in resp:
    for col in resp['Col_0']:
        print(f'  {col}')

# ── 3. ViewDPR page — find JS that builds PDF URL ─────────────
print('\n[3] ViewDPR page JS analysis:')
vr, final_url = get(f'{BASE}/Main/ViewDPR?workId=240025851')
# Find JS functions
js_funcs = re.findall(r'function\s+\w+[^{]*\{[^}]*\}', vr, re.DOTALL)
ajax_calls = re.findall(r'(?:ajax|url|href|window\.open|location)\s*[=:(]\s*["\']([^"\']+)["\']', vr, re.I)
# Look for DPR file path patterns
file_paths = re.findall(r'["\']([^"\']*(?:DPR|dpr|pdf|PDF|File|file|Upload|upload)[^"\']*)["\']', vr)
# Look for all script sections
scripts = re.findall(r'<script[^>]*>(.*?)</script>', vr, re.DOTALL)
print(f'  AJAX/URL refs: {ajax_calls[:20]}')
print(f'  File paths: {[p for p in file_paths if len(p) > 3][:20]}')
print(f'  Num scripts: {len(scripts)}')
for i, s in enumerate(scripts):
    if 'DPR' in s or 'dpr' in s or 'pdf' in s.lower() or 'download' in s.lower():
        print(f'\n  === Script {i} (DPR-related) ===')
        print(s[:1000])

# ── 4. Try to get DPR PDF via the anchor id GUID ─────────────
print('\n[4] DPR download via GUID:')
# From probe: id="9713863B-D452-4E8D-8352-DC80BE6A845B_DPRLink"
# Try various URL patterns
sample_guid = '9713863B-D452-4E8D-8352-DC80BE6A845B'
for url_pattern in [
    f'{BASE}/Main/GetDPRFile?id={sample_guid}',
    f'{BASE}/Main/DownloadDPR?id={sample_guid}',
    f'{BASE}/Main/ViewDPRFile?id={sample_guid}',
    f'{BASE}/DPR/Download?id={sample_guid}',
    f'{BASE}/FileDownload/DPR?id={sample_guid}',
    f'{BASE}/Uploads/DPR/{sample_guid}.pdf',
    f'{BASE}/UploadedFiles/DPR/{sample_guid}.pdf',
]:
    content, fu = get(url_pattern)
    status = 'PDF!' if '%PDF' in content[:10] else f'{len(content)} chars'
    if 'ERROR' in content:
        status = content[:60]
    print(f'  {url_pattern.split(BASE)[1]} → {status}')

# ── 5. Try getWorkDetailById or similar ──────────────────────
print('\n[5] More optModes with workId=240025851:')
for mode in ['getWorkById','getWorkDetailById','getWorkInfo','getWorkData',
             'getWorkDPRById','getDPRByWorkId','getWorkDetailNew']:
    payload2 = {"obj": {"optMode": mode, "workId": "240025851",
                        "districtId": -1, "yearId": "3",
                        "seatId": "240010310", "seatTypeId": "1"}}
    r = post_json(WORKS_URL, payload2)
    if r and r != {} and 'ERROR' not in str(r)[:20]:
        print(f'  {mode} → DATA: {str(r)[:150]}')
    else:
        print(f'  {mode} → empty/error')

# ── 6. Check /Main/GetDPRFile or /Main/shasanadesh for order PDFs ───
print('\n[6] Shasanadesh API — look for fund order PDFs:')
payload3 = {"obj": {"optMode": "getShasanadesh", "districtId": -1,
                    "yearId": "-1", "seatId": "-1", "seatTypeId": "1"}}
r = post_json(WORKS_URL, payload3)
print(f'  getShasanadesh: {str(r)[:200]}')

# Try dedicated controller
sh_page, _ = get(f'{BASE}/Main/shasanadesh')
# Look for JSON data embedded in page
json_data = re.findall(r'var\s+\w+\s*=\s*(\[.+?\]);', sh_page, re.DOTALL)
print(f'  Embedded JSON arrays in shasanadesh: {len(json_data)}')
for jd in json_data[:3]:
    try:
        parsed = json.loads(jd)
        print(f'    Array of {len(parsed)}: {str(parsed[:2])[:200]}')
    except: pass
# look for PDF links in page
pdfs = re.findall(r'href=["\']([^"\']*\.pdf)["\']', sh_page, re.I)
print(f'  PDF hrefs: {pdfs}')

print('\n[DONE]')
