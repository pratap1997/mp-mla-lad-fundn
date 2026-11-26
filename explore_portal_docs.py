"""
Explore mlaladsup.in — find ALL downloadable documents:
  - Download section links
  - Annual Reports
  - Guidelines / Pocket Books
  - DPR PDFs linked from works
  - Fund release order PDFs
  - Profile documents
"""
import sys, json, re, urllib.request, urllib.error, html
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': '*/*',
    'Referer': 'https://mlaladsup.in/',
}
BASE = 'https://mlaladsup.in'
WORKS_URL = f'{BASE}/Main/getNikayDistrictWise'

def get(url, is_json=False):
    req = urllib.request.Request(url, headers={
        'User-Agent': HEADERS['User-Agent'],
        'Accept': '*/*',
        'Referer': 'https://mlaladsup.in/',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8', errors='replace')
            return json.loads(raw) if is_json else raw
    except Exception as e:
        return f'ERROR: {e}'

def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return f'ERROR: {e}'

def find_links(html_text, base=BASE):
    """Extract all href/src links from HTML."""
    links = set()
    for m in re.finditer(r'(?:href|src|data-src|action)=["\']([^"\']+)["\']', html_text, re.I):
        url = m.group(1).strip()
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = base + url
        elif url.startswith('http'):
            pass
        else:
            continue
        links.add(url)
    return links

print('='*60)
print('Portal Document Discovery')
print('='*60)

# ── 1. Home page ─────────────────────────────────────────────
print('\n[1] Home page links:')
home = get(BASE + '/')
if 'ERROR' not in str(home):
    links = find_links(home)
    doc_links = [l for l in links if any(x in l.lower() for x in
                 ['.pdf','.xlsx','.xls','.doc','.docx','.zip','.rar','.csv'])]
    page_links = [l for l in links if 'mlaladsup.in' in l and '.' not in l.split('/')[-1]]
    print(f'  Total links: {len(links)}')
    print(f'  Doc files  : {len(doc_links)}')
    for d in sorted(doc_links):
        print(f'    {d}')
    print(f'  Page links :')
    for p in sorted(page_links)[:30]:
        print(f'    {p}')

# ── 2. Download section ───────────────────────────────────────
print('\n[2] /Download page:')
dl = get(BASE + '/Download')
if 'ERROR' not in str(dl):
    links = find_links(dl)
    doc_links = [l for l in links if any(x in l.lower() for x in
                 ['.pdf','.xlsx','.xls','.doc','.docx','.zip','.rar'])]
    print(f'  Doc links: {len(doc_links)}')
    for d in sorted(doc_links):
        print(f'    {d}')

# ── 3. Annual Report ─────────────────────────────────────────
print('\n[3] Annual Report / वार्षिक रिपोर्ट:')
for path in ['/AnnualReport', '/AnnualReport/Index', '/Main/AnnualReport',
             '/Report/Annual', '/Download/AnnualReport']:
    r = get(BASE + path)
    if 'ERROR' not in str(r) and len(r) > 200:
        links = find_links(r)
        docs  = [l for l in links if '.pdf' in l.lower()]
        print(f'  {path} → {len(docs)} PDFs')
        for d in docs[:10]:
            print(f'    {d}')
        break

# ── 4. Guidelines / Pocket Book ──────────────────────────────
print('\n[4] Guidelines / Pocket Book:')
for path in ['/Guideline', '/Guidelines', '/PocketBook', '/Download/Guideline',
             '/Main/Guideline', '/DikshaGuideline']:
    r = get(BASE + path)
    if 'ERROR' not in str(r) and len(r) > 200:
        links = find_links(r)
        docs  = [l for l in links if any(x in l.lower() for x in ['.pdf','.doc'])]
        print(f'  {path} → {len(docs)} docs')
        for d in docs[:10]:
            print(f'    {d}')

# ── 5. DPR PDF endpoint probe ─────────────────────────────────
print('\n[5] DPR PDF API probe:')
# Known DPR pattern from previous work: /DPRFile/ViewDPR?workId=...
# Try a known work ID from our data
dpr_paths = [
    '/DPRFile/ViewDPR',
    '/Main/ViewDPR',
    '/Work/DPR',
    '/WorkFile/GetDPR',
]
for path in dpr_paths:
    r = get(BASE + path + '?workId=240025851')
    if 'ERROR' not in str(r)[:50]:
        print(f'  {path} → responded ({len(r)} chars)')
    else:
        print(f'  {path} → {str(r)[:60]}')

# ── 6. Fund release order PDFs ───────────────────────────────
print('\n[6] Fund release / निधि जारी API:')
payload = {"obj": {"optMode": "MLAWiseFundRelease", "yearId": "3", "seatId": "-1", "seatTypeId": "1", "districtId": -1}}
resp = post_json(WORKS_URL, payload)
if isinstance(resp, list) and resp:
    sample = resp[0]
    print(f'  Sample keys: {list(sample.keys())[:15]}')
    # Look for any URL/link columns
    for k, v in sample.items():
        if isinstance(v, str) and ('http' in v or '.pdf' in v.lower() or 'href' in v.lower()):
            print(f'    URL col [{k}]: {v[:120]}')

# ── 7. Work detail — look for DPR link column ─────────────────
print('\n[7] Work detail DPR column probe (seatId=240010310, year=3):')
payload = {"obj": {"optMode": "getWorkdetail", "districtId": -1,
                   "yearId": "3", "seatId": "240010310", "seatTypeId": "1"}}
resp = post_json(WORKS_URL, payload)
if isinstance(resp, list) and resp:
    sample = resp[0]
    print(f'  Sample keys: {list(sample.keys())}')
    for k, v in sample.items():
        if isinstance(v, str) and len(v) > 5:
            print(f'    [{k}]: {v[:100]}')
elif isinstance(resp, dict):
    print(f'  dict keys: {list(resp.keys())}')
    for k, v in resp.items():
        if isinstance(v, list) and v:
            print(f'    list key [{k}], first item: {v[0]}')
            break
else:
    print(f'  Response: {str(resp)[:200]}')

# ── 8. Try getWorkDetailWithDPR or similar ────────────────────
print('\n[8] Other optModes with DPR:')
for mode in ['getWorkDetailWithDPR','getDPRList','getDPRDetails','getWorkDPR',
             'WorkDPRDetail','DPRDetail']:
    payload = {"obj": {"optMode": mode, "districtId": -1,
                       "yearId": "3", "seatId": "240010310", "seatTypeId": "1"}}
    resp = post_json(WORKS_URL, payload)
    if isinstance(resp, (list, dict)) and resp:
        print(f'  {mode} → DATA! {str(resp)[:100]}')
    else:
        print(f'  {mode} → {str(resp)[:60]}')

# ── 9. Probe /DPR and /Document controllers ───────────────────
print('\n[9] /DPR controller probe:')
for path in ['/DPR', '/DPR/Index', '/DPR/GetList', '/Document', '/Document/List',
             '/FileUpload', '/FileUpload/GetFiles', '/WorkDocument/GetFiles']:
    r = get(BASE + path)
    snippet = str(r)[:80].replace('\n','')
    print(f'  {path} → {snippet}')

print('\n[DONE]')
