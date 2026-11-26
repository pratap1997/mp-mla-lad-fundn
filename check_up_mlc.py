import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest'
}
WORKS_URL = 'https://mlaladsup.in/Main/getNikayDistrictWise'

def call(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))

# Test MLAWiseApplication for Vidhan Parishad (seatTypeId=2)
r2 = call(WORKS_URL, {'obj': {
    'optMode': 'MLAWiseApplication',
    'districtId': -1, 'yearId': '3',
    'seatId': '-1', 'seatTypeId': '2'
}})
rows2 = r2.get('Table_0', [])
print('MLC (seatTypeId=2), yearId=3: %d rows' % len(rows2))
if rows2:
    print('Sample:', rows2[0])

# Also test MLAWiseFundRelease for all MLAs, all years
FUND_URL = 'https://mlaladsup.in/Main/MLAWiseFundRelease'

r3 = call(WORKS_URL, {'obj': {
    'optMode': 'MLAWiseFundRelease',
    'districtId': -1, 'yearId': '-1',
    'seatId': '-1', 'seatTypeId': '1'
}})
print('\nMLAWiseFundRelease all MLAs all years: rows=%d' % len(r3.get('Table_0', [])))

# Test getWorkMLAWisePhysical for all MLAs
r4 = call(WORKS_URL, {'obj': {
    'optMode': 'getWorkMLAPhysicalWise',
    'districtId': -1, 'yearId': '3',
    'seatId': '-1', 'seatTypeId': '1'
}})
rows4 = r4.get('Table_0', [])
print('\ngetWorkMLAPhysicalWise all MLAs yearId=3: %d rows' % len(rows4))
if rows4:
    print('Columns:', list(rows4[0].keys()))
    print('Sample:', rows4[0])
