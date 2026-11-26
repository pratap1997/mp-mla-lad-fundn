import sys, urllib.request, re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE_URL = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx'

req = urllib.request.Request(BASE_URL, headers=headers)
html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')

# Find AngularJS app name, controllers, $http/$resource calls
# Look for ng-app, ng-controller, $http.get/post
ng_app = re.findall(r'ng-app=["\']([^"\']+)["\']', html)
ng_ctrl = re.findall(r'ng-controller=["\']([^"\']+)["\']', html)
print("ng-app:", ng_app)
print("ng-controller:", ng_ctrl)

# External scripts loaded
soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script', src=True)
print("\nExternal scripts:")
for s in scripts:
    print(" ", s['src'])

# Find ScriptManager or UpdatePanel triggers (ASP.NET WebForms)
triggers = re.findall(r"__doPostBack\(['\"]([^'\"]+)['\"]", html)
print(f"\n__doPostBack triggers ({len(triggers)}):")
for t in set(triggers):
    print(f"  {t}")

# Look for any .aspx report links or chart data endpoints 
aspx_links = re.findall(r'href=["\']([^"\']*\.aspx[^"\']*)["\']', html)
print(f"\n.aspx links ({len(aspx_links)}):")
for l in aspx_links:
    print(f"  {l}")

# Look for AngularJS $http calls in all script text
all_script_text = '\n'.join(s.get_text() for s in soup.find_all('script'))
http_calls = re.findall(r'\$http\.(get|post)\(["\']([^"\']+)["\']', all_script_text)
print(f"\n$http calls found: {len(http_calls)}")
for method, url in http_calls:
    print(f"  {method.upper()} {url}")

# Look for ScriptService or PageMethods
pm = re.findall(r'PageMethods\.(\w+)\(', html)
print(f"\nPageMethods calls: {pm}")

# Any JSON-like data in page (chart data)
json_blobs = re.findall(r'(?:var\s+\w+\s*=\s*)(\[.*?\]|\{.*?\})', html[:5000], re.DOTALL)
print(f"\nJSON blobs in first 5000 chars: {len(json_blobs)}")
