import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest'
}
WORKS_URL = 'https://mlaladsup.in/Main/getNikayDistrictWise'

# Get all column keys from MLAWiseApplication
def call(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))

# yearId -1 = all years for one MLA
r = call(WORKS_URL, {'obj': {
    'optMode': 'MLAWiseApplication',
    'districtId': -1, 'yearId': '3',
    'seatId': '-1', 'seatTypeId': '1'
}})
rows = r.get('Table_0', [])
print('MLAWiseApplication seatId=-1 (ALL MLAs), yearId=3: %d rows' % len(rows))
if rows:
    print('All column keys:')
    for k in rows[0].keys():
        print('  %r: %r' % (k, rows[0][k]))
    print('Row 2:', rows[1] if len(rows) > 1 else 'N/A')
