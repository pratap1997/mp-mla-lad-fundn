"""
Deep probe of getDPRDetails endpoint + shasanadesh + all pages with data
"""
import sys, json, re, urllib.request, html
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

def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': HEADERS['User-Agent'], 'Accept': '*/*',
        'Referer': 'https://mlaladsup.in/'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f'ERROR: {e}'

def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return f'ERROR: {e}'

class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.t=[]
    def handle_data(self,d):
        if d.strip(): self.t.append(d.strip())
    def get(self): return ' '.join(self.t)

def strip_html(v):
    if not isinstance(v,str): return v
    p=_Text(); p.feed(html.unescape(v)); return p.get()

def find_links(text):
    links = set()
    for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']', text, re.I):
        u = m.group(1)
        if u.startswith('/'): u = BASE + u
        elif not u.startswith('http'): continue
        links.add(u)
    # Also find file= style params
    for m in re.finditer(r'["\']([^"\']*\.(?:pdf|xlsx|xls|doc|docx|zip))["\']', text, re.I):
        u = m.group(1)
        if u.startswith('/'): u = BASE + u
        elif u.startswith('http'): pass
        else: continue
        links.add(u)
    return links

# ── 1. Full getDPRDetails probe ───────────────────────────────
print('\n[1] getDPRDetails — seatId=240010310, year=3:')
payload = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                   "yearId": "3", "seatId": "240010310", "seatTypeId": "1"}}
resp = post_json(WORKS_URL, payload)
print(f'  Type: {type(resp).__name__}')
if isinstance(resp, dict):
    for k, v in resp.items():
        print(f'  Key: {k} -> type={type(v).__name__} len={len(v) if hasattr(v,"__len__") else "N/A"}')
        if isinstance(v, list) and v:
            print(f'    First item: {json.dumps(v[0], ensure_ascii=False)[:300]}')
elif isinstance(resp, list) and resp:
    print(f'  List of {len(resp)}, first: {json.dumps(resp[0], ensure_ascii=False)[:300]}')
else:
    print(f'  raw: {str(resp)[:200]}')

# ── 2. getDPRDetails with seatId=-1 (all MLAs) ───────────────
print('\n[2] getDPRDetails — seatId=-1, all MLAs, year=3:')
payload2 = {"obj": {"optMode": "getDPRDetails", "districtId": -1,
                    "yearId": "3", "seatId": "-1", "seatTypeId": "1"}}
resp2 = post_json(WORKS_URL, payload2)
if isinstance(resp2, dict):
    for k, v in resp2.items():
        cnt = len(v) if hasattr(v,'__len__') else 'N/A'
        print(f'  Key={k}, count={cnt}')
        if isinstance(v, list) and v:
            print(f'    Sample: {json.dumps(v[0], ensure_ascii=False)[:300]}')
elif isinstance(resp2, list):
    print(f'  List len={len(resp2)}')
    if resp2: print(f'  Sample: {json.dumps(resp2[0], ensure_ascii=False)[:300]}')
else:
    print(f'  {str(resp2)[:200]}')

# ── 3. Shasanadesh page ───────────────────────────────────────
print('\n[3] /Main/shasanadesh:')
sh = get(f'{BASE}/Main/shasanadesh')
if 'ERROR' not in sh:
    links = find_links(sh)
    pdfs  = [l for l in links if '.pdf' in l.lower()]
    print(f'  PDFs found: {len(pdfs)}')
    for p in sorted(pdfs):
        print(f'    {p}')
    # Look for JSON data or API calls in page
    apis = re.findall(r'(?:url|URL)\s*:\s*["\']([^"\']+)["\']', sh)
    print(f'  API references: {apis[:10]}')
else:
    print(f'  {sh[:100]}')

# ── 4. /Main/ViewDPR with a work ID ──────────────────────────
print('\n[4] /Main/ViewDPR with workId=240025851:')
vr = get(f'{BASE}/Main/ViewDPR?workId=240025851')
if 'ERROR' not in vr:
    links = find_links(vr)
    pdfs  = [l for l in links if '.pdf' in l.lower()]
    print(f'  Page size: {len(vr)} chars, PDFs: {len(pdfs)}')
    for p in pdfs[:5]: print(f'    {p}')
    # Print a snippet to understand structure
    print(f'  Snippet: {vr[:500]}')
else:
    print(f'  {vr}')

# ── 5. expenseSummaryDetails ──────────────────────────────────
print('\n[5] /main/expenseSummaryDetails:')
ex = get(f'{BASE}/main/expenseSummaryDetails')
if 'ERROR' not in ex:
    links = find_links(ex)
    pdfs  = [l for l in links if '.pdf' in l.lower()]
    apis  = re.findall(r'(?:url|URL|ajax)\s*:\s*["\']([^"\']+)["\']', ex, re.I)
    print(f'  PDFs: {len(pdfs)}, API refs: {apis[:5]}')
    for p in pdfs[:5]: print(f'    {p}')
else:
    print(f'  {ex[:100]}')

# ── 6. IAWisePhysical / DistrictWiseWorkCounts ────────────────
for path in ['/main/IAWisePhysical', '/main/DistrictWiseWorkCounts',
             '/main/MLAWiseWorkCounts', '/Main/MLAWiseFundRelease',
             '/main/DistrictWiseFundRelease']:
    r = get(f'{BASE}{path}')
    if 'ERROR' not in r:
        links = find_links(r)
        pdfs  = [l for l in links if '.pdf' in l.lower()]
        apis  = re.findall(r'"(/[^"]+)"', r)
        internal = [a for a in apis if 'Main' in a or 'Download' in a or 'File' in a or 'DPR' in a]
        print(f'\n[6] {path}: PDFs={len(pdfs)}, internal APIs={internal[:8]}')

# ── 7. Static uploads directory listing ──────────────────────
print('\n[7] Static /Uploads/ probe:')
up = get(f'{BASE}/Uploads/')
if 'ERROR' not in up:
    files = re.findall(r'href="([^"]+\.(?:pdf|xlsx|xls|doc|docx|zip))"', up, re.I)
    print(f'  Files: {files}')
else:
    print(f'  {up[:100]}')

# ── 8. mlaProfile page ───────────────────────────────────────
print('\n[8] /main/mlaProfile:')
mp = get(f'{BASE}/main/mlaProfile')
if 'ERROR' not in mp:
    apis = re.findall(r'(?:url|URL|ajax|href)\s*[=:]\s*["\']([^"\']+)["\']', mp, re.I)
    opt_modes = re.findall(r'optMode.*?["\'](\w+)["\']', mp)
    print(f'  APIs: {apis[:10]}')
    print(f'  optModes: {opt_modes}')
else:
    print(f'  {mp[:100]}')

print('\n[DONE]')
