import sys, urllib.request, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE_URL = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'

req = urllib.request.Request(BASE_URL, headers=headers)
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')

inline_scripts = [s.get_text() for s in soup.find_all('script') if not s.get('src') and s.get_text(strip=True)]

# Script 2 is the big one - extract all function definitions and $.ajax / $.get / $.post calls
big_script = inline_scripts[2] if len(inline_scripts) > 2 else ''

# Find $.ajax / $.post / $.get calls
ajax_calls = re.findall(r'\$\.(ajax|get|post)\s*\([\s\S]{0,500}?\)', big_script)
print(f"$.ajax/get/post calls: {len(ajax_calls)}")
for c in ajax_calls:
    print(c[:300])
    print("---")

# Find all function names
funcs = re.findall(r'function\s+(\w+)\s*\(', big_script)
print(f"\nFunctions defined: {funcs}")

# Find fetch() calls
fetch_calls = re.findall(r'fetch\([\'"]([^\'"]+)[\'"]', big_script)
print(f"\nfetch() calls: {fetch_calls}")

# Find XMLHttpRequest
xhr = re.findall(r'XMLHttpRequest|ActiveXObject', big_script)
print(f"\nXHR usage: {xhr}")

# Print function bodies for load_card, performance_rpt, mla_report, work_graph, tot_incom_work, tot_expenditure
def extract_func(src, fname):
    pos = src.find(f'function {fname}')
    if pos == -1:
        pos = src.find(f'{fname} =')
    if pos != -1:
        return src[pos:pos+1500]
    return None

for fn in ['performance_rpt', 'mla_report', 'load_card', 'work_graph', 'tot_incom_work', 'tot_expenditure', 'load_dashboard']:
    body = extract_func(big_script, fn)
    if body:
        print(f"\n=== {fn} ===")
        print(body)
