import sys, urllib.request, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
url = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'
req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')

soup = BeautifulSoup(html, 'html.parser')

# Print the full scheme dropdown options
print("=== SCHEME LIST ===")
ddl = soup.find('select', {'id': 'ctl00_ContentPlaceHolder1_ddlscheme'})
if ddl:
    for opt in ddl.find_all('option'):
        print(f"  value={opt.get('value')!r}: {opt.get_text(strip=True)}")

print("\n=== ASSEMBLY NUMBER (ddl_ano) ===")
ddl = soup.find('select', {'id': 'ctl00_ContentPlaceHolder1_ddl_ano'})
if ddl:
    for opt in ddl.find_all('option'):
        print(f"  value={opt.get('value')!r}: {opt.get_text(strip=True)}")

print("\n=== MLA ASSEMBLY NO (ddl_mla_ano) ===")
ddl = soup.find('select', {'id': 'ctl00_ContentPlaceHolder1_ddl_mla_ano'})
if ddl:
    for opt in ddl.find_all('option'):
        print(f"  value={opt.get('value')!r}: {opt.get_text(strip=True)}")

# Check inline JS for AngularJS controllers, API endpoints, $http calls
scripts = [s.get_text() for s in soup.find_all('script') if not s.get('src')]
print("\n=== Inline scripts with API clues ===")
for s in scripts:
    if any(k in s for k in ['$http', 'api/', '.asmx', '.ashx', 'WebMethod', 'PageMethods', 'ajaxurl', 'controller', 'ng-app']):
        print(s[:2000])
        print("---")

# Collect all hidden inputs (ViewState, etc.)
hidden = [(i.get('name'), i.get('value','')[:40]) for i in soup.find_all('input', {'type': 'hidden'})]
print(f"\nHidden inputs: {len(hidden)}")
for n, v in hidden[:10]:
    print(f"  {n}: {v}")
