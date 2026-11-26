import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest'
}
DROP_URL = 'https://mlaladsup.in/DropdownBinder/fillDropdown'
WORKS_URL = 'https://mlaladsup.in/Main/getNikayDistrictWise'
FUND_URL  = 'https://mlaladsup.in/Main/MLAWiseFundRelease'

def call(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))

# 1. Get all year IDs
years = call(DROP_URL, {'obj': {'optMode': 'bindYear'}})
print('Years available:')
for y in years:
    print('  id=%s  value=%s' % (y['id'], y['value']))

# 2. Test MLAWiseApplication for one MLA across all years
print('\nTest MLAWiseApplication (MLA 240010268 = Atul Pradhan) for each year:')
for y in years:
    yid = str(y['id'])
    r = call(WORKS_URL, {'obj': {
        'optMode': 'MLAWiseApplication',
        'districtId': -1, 'yearId': yid,
        'seatId': '240010268', 'seatTypeId': '1'
    }})
    rows = r.get('Table_0', [])
    if rows:
        row = rows[0]
        print('  Year=%s (%s) | allocated=%s | sanctioned=%s | expenditure=%s | remaining=%s' % (
            yid, y['value'],
            row.get('आवंटित \u003cbr/\u003e धनराशि \u003cbr/\u003e (लाख में ) '),
            row.get('स्वीकृत \u003cbr/\u003e धनराशि \u003cbr/\u003e (लाख में)'),
            row.get('व्यय \u003cbr/\u003e धनराशि \u003cbr/\u003e (लाख में)'),
            row.get('अवशेष \u003cbr/\u003e धनराशि \u003cbr/\u003e (लाख में) ')
        ))
    else:
        print('  Year=%s (%s): no data' % (yid, y['value']))
