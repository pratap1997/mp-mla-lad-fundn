import sys, urllib.request, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
url = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'
req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')

soup = BeautifulSoup(html, 'html.parser')

# Print all forms
forms = soup.find_all('form')
print(f"Forms found: {len(forms)}")
for f in forms:
    print(f"  Action: {f.get('action')}, Method: {f.get('method')}")

# Find select/dropdowns
selects = soup.find_all('select')
print(f"\nDropdowns found: {len(selects)}")
for s in selects:
    sid = s.get('id', s.get('name'))
    opts = [(o.get('value',''), o.get_text(strip=True)) for o in s.find_all('option')]
    print(f"  [{sid}] - {len(opts)} options:")
    for v, t in opts[:8]:
        print(f"    {v!r}: {t}")

# Find tables
tables = soup.find_all('table')
print(f"\nTables found: {len(tables)}")
for i, t in enumerate(tables):
    rows = t.find_all('tr')
    print(f"  Table {i}: {len(rows)} rows")
    if rows:
        hdrs = [th.get_text(strip=True) for th in rows[0].find_all(['th','td'])]
        print(f"    Headers: {hdrs[:8]}")

# Find anchor links
links = [(a.get_text(strip=True), a.get('href','')) for a in soup.find_all('a', href=True)]
print(f"\nLinks ({len(links)}):")
for t, h in links[:30]:
    if any(k in h.lower() for k in ['aspx', 'report', 'mla', 'lad', 'pdmn', 'work', 'scheme']):
        print(f"  {t!r} -> {h}")
