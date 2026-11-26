import sys, urllib.request, urllib.parse, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'
}

BASE_URL = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'

# Step 1: GET to get ViewState tokens
req = urllib.request.Request(BASE_URL, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')

vs = soup.find('input', {'id': '__VIEWSTATE'})['value']
vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
ev = soup.find('input', {'id': '__EVENTVALIDATION'})['value']
csrf = soup.find('input', {'id': 'ctl00$hidcsrf'})['value'] if soup.find('input', {'id': 'ctl00$hidcsrf'}) else ''

print(f"ViewState (first 30): {vs[:30]}...")
print(f"VIEWSTATEGENERATOR: {vsg}")

# Step 2: POST to get MLA-LAD data with scheme=9 (विधायक स्थानीय क्षेत्र विकास योजना)
# Try year=2024-25, assembly no 16
form_data = {
    '__VIEWSTATE': vs,
    '__VIEWSTATEGENERATOR': vsg,
    '__VIEWSTATEENCRYPTED': '',
    '__EVENTVALIDATION': ev,
    'ctl00$hidcsrf': csrf,
    'ctl00$ContentPlaceHolder1$ddlscheme': '9',         # MLA-LAD scheme
    'ctl00$ContentPlaceHolder1$ddl_main_fin_yr': '2024-25',
    'ctl00$ContentPlaceHolder1$ddl_district': '--All--',
    'ctl00$ContentPlaceHolder1$ddl_ano': '16',           # 16th assembly
    'ctl00$ContentPlaceHolder1$ddlloksabha': '18',
    'ctl00$ContentPlaceHolder1$ddl_fin_yr_exp': '--All--',
    'ctl00$ContentPlaceHolder1$ddlfinancialyear': '2024-25',
    'ctl00$ContentPlaceHolder1$ddl_per_fin_yr': '2024-25',
    'ctl00$ContentPlaceHolder1$ddl_fin_mla': '2024-25',
    'ctl00$ContentPlaceHolder1$ddl_mla_ano': '16',
    'ctl00$ContentPlaceHolder1$hdndist': '',
    '__ASYNCPOST': 'true',
}

post_data = urllib.parse.urlencode(form_data).encode('utf-8')
req2 = urllib.request.Request(BASE_URL, data=post_data, headers=headers, method='POST')
try:
    res = urllib.request.urlopen(req2, timeout=20)
    response_html = res.read().decode('utf-8', errors='ignore')
    soup2 = BeautifulSoup(response_html, 'html.parser')

    print(f"\nResponse length: {len(response_html)}")

    # Find tables
    tables = soup2.find_all('table')
    print(f"Tables in response: {len(tables)}")
    for i, t in enumerate(tables):
        rows = t.find_all('tr')
        print(f"  Table {i}: {len(rows)} rows")
        for row in rows[:5]:
            cells = [td.get_text(strip=True) for td in row.find_all(['th','td'])]
            if cells:
                print(f"    {cells[:6]}")
except Exception as e:
    print(f"Error: {e}")
