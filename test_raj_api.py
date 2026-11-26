import sys, urllib.request, json

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
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            text = res.read().decode('utf-8')
            parsed = json.loads(text)
            return parsed
    except Exception as e:
        return {'error': str(e)}

# API endpoints discovered:
# 1. get_mla_data       -> MLA-wise table (name, constituency, proposed, sanction, completed, funds)
# 2. load_card          -> summary cards
# 3. work_graph         -> bar chart data
# 4. Get_totincom_work  -> incomplete works
# 5. Get_tot_expenditure -> expenditure chart
# 6. Get_performance_report -> top/bottom performers

# Scheme IDs:
# 9  = MLA-LAD (विधायक स्थानीय क्षेत्र विकास योजना)
# 10 = MP-LAD
# 15 = Sv-Vivek Jila Vikas Yojana
# etc.

# Assembly numbers: 16 (current 2023-), 15 (2018-2023), 14 (2013-2018), 13 (2008-2013)

YEARS = ['2024-25', '2023-24', '2022-23', '2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15']
ASSEMBLIES = ['16', '15', '14', '13']

print("=" * 60)
print("TEST 1: get_mla_data for MLA-LAD scheme=9, year=2024-25, assembly=16")
print("=" * 60)
result = call_api('get_mla_data', {"a_no": "16", "fin_yr": "2024-25", "dist_code": "0"})
if 'd' in result:
    rows = result['d']
    print(f"Rows returned: {len(rows)}")
    if rows:
        print(f"Sample row keys: {list(rows[0].keys())}")
        print(f"Sample row[0]: {rows[0]}")
        print(f"Sample row[1]: {rows[1] if len(rows) > 1 else 'N/A'}")
else:
    print(f"Result: {str(result)[:300]}")

print("\n")
print("=" * 60)
print("TEST 2: load_card summary for MLA-LAD scheme=9, year=2024-25, assembly=16")
print("=" * 60)
result2 = call_api('load_card', {"scheme_id": "9", "is_lr": "0", "p_no": "0", "a_no": "16", "fin_yr": "2024-25", "dist_code": "0"})
print(f"Result: {str(result2)[:500]}")

print("\n")
print("=" * 60)
print("TEST 3: work_graph for MLA-LAD scheme=9, year=2024-25")
print("=" * 60)
result3 = call_api('work_graph', {"scheme_id": "9", "is_lr": "0", "p_no": "0", "a_no": "16", "fin_yr": "2024-25", "dist_code": "0"})
print(f"Result: {str(result3)[:500]}")
