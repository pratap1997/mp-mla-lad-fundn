import sys, urllib.request, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE_URL = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'

req = urllib.request.Request(BASE_URL, headers=headers)
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')

# Print ALL inline scripts to find chart data fetching
inline_scripts = [s.get_text() for s in soup.find_all('script') if not s.get('src') and s.get_text(strip=True)]
print(f"Inline scripts count: {len(inline_scripts)}")
for i, s in enumerate(inline_scripts):
    if len(s.strip()) > 20:
        print(f"\n--- Script {i} (len={len(s)}) ---")
        print(s[:3000])
