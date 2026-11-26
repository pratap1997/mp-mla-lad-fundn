import sys, urllib.request, json, re
from html import unescape

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type': 'application/json;charset=utf-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': BASE + 'Dashboard_graph_amchart.aspx'
}

def call_api(endpoint, params):
    url = BASE + 'Dashboard_graph_amchart.aspx/' + endpoint
    data = json.dumps(params).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))

def decode_html_name(s):
    """Decode HTML entities like &#2325; to real Unicode characters"""
    return unescape(s) if s else ''

# All available years and assemblies
YEARS = ['2026-27','2025-26','2024-25','2023-24','2022-23','2021-22','2020-21','2019-20','2018-19','2017-18','2016-17','2015-16','2014-15']
# Assembly 16=current(2023-), 15=2018-23, 14=2013-18, 13=2008-13
ASSEMBLIES = [('16', '2023-'), ('15', '2018-2023'), ('14', '2013-2018'), ('13', '2008-2013')]

# Map year to assembly
def year_to_assembly(year):
    y = int(year.split('-')[0])
    if y >= 2023: return '16'
    elif y >= 2018: return '15'
    elif y >= 2013: return '14'
    else: return '13'

# All schemes available
SCHEMES = {
    '9':  'MLA-LAD (विधायक स्थानीय क्षेत्र विकास योजना)',
    '10': 'MP-LAD (सांसद स्थानीय क्षेत्र विकास योजना)',
    '15': 'स्व-विवेक जिला विकास योजना',
    '16': 'महात्मा गांधी जनभागीदारी विकास योजना',
    '56': 'जिला खनिज फाउंडेशन ट्रस्ट',
    '5':  'डांग क्षेत्रीय विकास कार्यक्रम',
    '60': 'डॉ श्यामा प्रसाद मुखर्जी जिला उत्थान योजना',
    '59': 'पं.दीनदयाल उपाध्याय गरीबी मुक्त गांव योजना',
    '55': 'प्रधानमंत्री आदर्श ग्राम योजना',
    '58': 'बृज क्षेत्रीय विकास योजना',
    '54': 'CM-REGS',
    '53': 'मुख्यमंत्री जिला नवाचार निधि योजना-2021',
    '57': 'मुख्यमंत्री थार सीमा क्षेत्र विकास कार्यक्रम',
    '7':  'मगरा क्षेत्रीय विकास कार्यक्रम',
    '6':  'मेवात क्षेत्रीय विकास कार्यक्रम',
    '48': 'श्यामा प्रसाद मुखर्जी रूर्बन मिशन',
    '8':  'सीमावर्ती क्षेत्रीय विकास कार्यक्रम',
}

# Test all years and all schemes for get_mla_data
print("Probing all years x MLA-LAD scheme (9)...")
mla_lad_rows = {}
for year in YEARS:
    a_no = year_to_assembly(year)
    try:
        r = call_api('get_mla_data', {"a_no": a_no, "fin_yr": year, "dist_code": "0"})
        rows = r.get('d', [])
        cnt = len(rows)
        mla_lad_rows[year] = cnt
        print(f"  Year={year} (asm={a_no}): {cnt} MLA rows")
    except Exception as e:
        print(f"  Year={year}: ERROR {e}")

print("\nProbing other schemes for year=2024-25...")
for scheme_id, scheme_name in SCHEMES.items():
    if scheme_id == '9': continue
    try:
        r = call_api('load_card', {"scheme_id": scheme_id, "is_lr": "0", "p_no": "0", "a_no": "16", "fin_yr": "2024-25", "dist_code": "0"})
        d = r.get('d', {})
        print(f"  Scheme {scheme_id} ({scheme_name[:30]}): proposed={d.get('tot_proposed')}, fs={d.get('tot_fs')}, cc={d.get('tot_cc')}")
    except Exception as e:
        print(f"  Scheme {scheme_id}: ERROR {e}")
