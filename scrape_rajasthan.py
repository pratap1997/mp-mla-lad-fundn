"""
Rajasthan RDPRWMS Scraper
Scrapes MLA-LAD and all active schemes, year-wise, project/scheme/mission-wise
from https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/Dashboard_graph_amchart.aspx

API endpoint: Dashboard_graph_amchart.aspx/<method>
Methods:
  - get_mla_data       : MLA-wise fund & work data
  - load_card          : Summary totals (proposed/sanctioned/completed/expenditure)
  - Get_totincom_work  : Incomplete works breakdown
  - Get_tot_expenditure: Expenditure data
  - Get_performance_report: Top/bottom performers
"""

import sys
import json
import time
import os
import csv
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

# ─── Configuration ─────────────────────────────────────────
BASE_URL = 'https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/'
API_URL  = BASE_URL + 'Dashboard_graph_amchart.aspx/'
HEADERS  = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Content-Type':    'application/json;charset=utf-8',
    'Accept':          'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With':'XMLHttpRequest',
    'Referer':         BASE_URL + 'Dashboard_graph_amchart.aspx'
}

OUT_DIR = os.path.join(os.path.dirname(__file__), 'Rajasthan_RDPRWMS')
os.makedirs(OUT_DIR, exist_ok=True)

# Financial years available on the portal
YEARS = [
    '2026-27','2025-26','2024-25','2023-24',
    '2022-23','2021-22','2020-21','2019-20',
    '2018-19','2017-18','2016-17','2015-16','2014-15'
]

# Assembly session mapped by year (determined from probe)
def year_to_assembly(year):
    y = int(year.split('-')[0])
    if y >= 2023: return '16'
    elif y >= 2018: return '15'
    elif y >= 2013: return '14'
    else: return '13'

# All schemes
SCHEMES = {
    '9':  'MLA-LAD (विधायक स्थानीय क्षेत्र विकास योजना)',
    '10': 'MP-LAD (सांसद स्थानीय क्षेत्र विकास योजना)',
    '16': 'महात्मा गांधी जनभागीदारी विकास योजना',
    '56': 'जिला खनिज फाउंडेशन ट्रस्ट',
    '5':  'डांग क्षेत्रीय विकास कार्यक्रम',
    '60': 'डॉ श्यामा प्रसाद मुखर्जी जिला उत्थान योजना',
    '59': 'पं.दीनदयाल उपाध्याय गरीबी मुक्त गांव योजना',
    '55': 'प्रधानमंत्री आदर्श ग्राम योजना',
    '58': 'बृज क्षेत्रीय विकास योजना',
    '54': 'मुख्यमंत्री ग्रामीण रोजगार गारंटी योजना CM-REGS',
    '53': 'मुख्यमंत्री जिला नवाचार निधि योजना-2021',
    '57': 'मुख्यमंत्री थार सीमा क्षेत्र विकास कार्यक्रम',
    '7':  'मगरा क्षेत्रीय विकास कार्यक्रम',
    '6':  'मेवात क्षेत्रीय विकास कार्यक्रम',
    '15': 'स्व-विवेक जिला विकास योजना',
    '48': 'श्यामा प्रसाद मुखर्जी रूर्बन मिशन',
    '8':  'सीमावर्ती क्षेत्रीय विकास कार्यक्रम',
}

# Districts on portal
DISTRICTS = {
    '0':  '--All--',
    '21': 'Ajmer', '06': 'Alwar', '34': 'Balotra', '28': 'Banswara',
    '31': 'Baran', '17': 'Barmer', '37': 'Beawar', '03': 'Bharatpur',
    '20': 'Bhilwara', '12': 'Bikaner', '24': 'Bundi', '23': 'Chittorgarh',
    '10': 'Churu', '14': 'Dausa', '39': 'Deeg', '36': 'Didwana-Kuchaman',
    '30': 'Dungarpur', '11': 'Ganganagar', '13': 'Hanumangarh', '01': 'Jaipur',
    '16': 'Jaisalmer', '18': 'Jalor', '25': 'Jhalawar', '09': 'Jhunjhunu',
    '02': 'Jodhpur', '33': 'Karauli', '40': 'Khairthal-Tijara', '26': 'Kota',
    '41': 'Kotputli-Behror', '19': 'Nagaur', '22': 'Pali', '38': 'Phalodi',
    '29': 'Pratapgarh', '27': 'Rajsamand', '32': 'Sawai Madhopur',
    '42': 'Salumbar', '08': 'Sikar', '35': 'Sirohi', '15': 'Tonk', '07': 'Udaipur',
}

# ─── API helpers ───────────────────────────────────────────
def call_api(method, params, retries=3):
    url = API_URL + method
    data = json.dumps(params).encode('utf-8')
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.loads(res.read().decode('utf-8'))
        except Exception as e:
            if attempt == retries - 1:
                return {'error': str(e)}
            time.sleep(1)

def decode(s):
    """Decode HTML entities and clean whitespace."""
    return unescape(str(s)).strip() if s is not None else ''

# ─── Fetch functions ───────────────────────────────────────
def fetch_mla_data(year, dist_code='0'):
    a_no = year_to_assembly(year)
    r = call_api('get_mla_data', {"a_no": a_no, "fin_yr": year, "dist_code": dist_code})
    rows = r.get('d', []) if isinstance(r, dict) else []
    return [{
        'financial_year':          year,
        'assembly_no':             a_no,
        'scheme_id':               '9',
        'scheme_name':             'MLA-LAD',
        'district_filter':         DISTRICTS.get(dist_code, dist_code),
        's_no':                    row.get('s_no'),
        'mla_name':                decode(row.get('HMLAName', '')),
        'constituency':            decode(row.get('const_name', '')),
        'no_proposed':             row.get('no_proposed'),
        'no_financial_sanction':   row.get('no_fs'),
        'no_completed':            row.get('no_cc'),
        'available_funds_lacs':    row.get('avail_amt'),
        'financial_sanction_lacs': row.get('fs_amt'),
        'remaining_amount_lacs':   row.get('remain_amt'),
    } for row in rows if isinstance(row, dict) and 's_no' in row]

def fetch_summary_card(scheme_id, year, dist_code='0'):
    a_no = year_to_assembly(year)
    p_no = '0'
    r = call_api('load_card', {
        "scheme_id": scheme_id, "is_lr": "0",
        "p_no": p_no, "a_no": a_no, "fin_yr": year, "dist_code": dist_code
    })
    d = r.get('d', {}) if isinstance(r, dict) else {}
    if isinstance(d, dict) and 'tot_proposed' in d:
        return {
            'financial_year':    year,
            'assembly_no':       a_no,
            'scheme_id':         scheme_id,
            'scheme_name':       SCHEMES.get(scheme_id, scheme_id),
            'district_filter':   DISTRICTS.get(dist_code, dist_code),
            'total_proposed':    d.get('tot_proposed'),
            'total_admin_sanction': d.get('tot_as'),
            'total_tech_sanction':  d.get('tot_ts'),
            'total_fin_sanction':   d.get('tot_fs'),
            'total_incomplete':     d.get('tot_uc'),
            'total_completed':      d.get('tot_cc'),
        }
    return None

# ─── Main Scrape ───────────────────────────────────────────
def main():
    t0 = time.time()
    print("=" * 70)
    print("RAJASTHAN RDPRWMS SCRAPER")
    print("Portal: https://rdprwms.rajasthan.gov.in/iwmsweb/Pdmn/")
    print("=" * 70)

    # ── Part 1: MLA-LAD data, all years ────────────────────
    print("\n[1/3] Scraping MLA-LAD data for all years...")
    mla_rows = []
    for year in YEARS:
        rows = fetch_mla_data(year)
        mla_rows.extend(rows)
        print(f"  Year {year}: {len(rows)} MLA rows")
        time.sleep(0.2)

    print(f"  Total MLA-LAD rows: {len(mla_rows)}")

    mla_csv = os.path.join(OUT_DIR, 'MLA_LAD_Rajasthan_YearWise.csv')
    if mla_rows:
        with open(mla_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=mla_rows[0].keys())
            writer.writeheader()
            writer.writerows(mla_rows)
        print(f"  Saved: {mla_csv}")

    # ── Part 2: Summary cards for ALL schemes, all years ────
    print("\n[2/3] Scraping summary cards for all schemes × all years...")
    summary_rows = []
    tasks = [(sid, yr) for sid in SCHEMES.keys() for yr in YEARS]
    total = len(tasks)
    done = 0

    def fetch_one(args):
        sid, yr = args
        return fetch_summary_card(sid, yr)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, t): t for t in tasks}
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                summary_rows.append(result)
            if done % 30 == 0 or done == total:
                print(f"  Progress: {done}/{total} ({done/total*100:.0f}%)")

    print(f"  Total summary rows: {len(summary_rows)}")
    summary_csv = os.path.join(OUT_DIR, 'All_Schemes_Summary_YearWise.csv')
    if summary_rows:
        with open(summary_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"  Saved: {summary_csv}")

    # ── Part 3: MLA-LAD district-wise breakdown ─────────────
    print("\n[3/3] Scraping MLA-LAD data district-wise for recent years...")
    dist_rows = []
    recent_years = ['2024-25', '2023-24', '2022-23', '2021-22', '2020-21']
    dist_tasks = [(yr, dc) for yr in recent_years for dc in list(DISTRICTS.keys())[1:]]
    done2 = 0
    total2 = len(dist_tasks)

    def fetch_dist(args):
        yr, dc = args
        rows = fetch_mla_data(yr, dc)
        return rows

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_dist, t): t for t in dist_tasks}
        for future in as_completed(futures):
            done2 += 1
            rows = future.result()
            dist_rows.extend(rows)
            if done2 % 50 == 0 or done2 == total2:
                print(f"  Progress: {done2}/{total2} ({done2/total2*100:.0f}%) | rows: {len(dist_rows)}")

    # deduplicate by (year, constituency, s_no)
    seen = set()
    unique_dist_rows = []
    for r in dist_rows:
        key = (r['financial_year'], r['constituency'], r['s_no'])
        if key not in seen:
            seen.add(key)
            unique_dist_rows.append(r)

    print(f"  Total district-wise unique rows: {len(unique_dist_rows)}")
    dist_csv = os.path.join(OUT_DIR, 'MLA_LAD_DistrictWise_Recent5Yrs.csv')
    if unique_dist_rows:
        with open(dist_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=unique_dist_rows[0].keys())
            writer.writeheader()
            writer.writerows(unique_dist_rows)
        print(f"  Saved: {dist_csv}")

    # ── Excel export ─────────────────────────────────────────
    print("\nGenerating Excel workbook...")
    try:
        import pandas as pd
        excel_path = os.path.join(OUT_DIR, 'Rajasthan_RDPRWMS_Complete.xlsx')
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            if mla_rows:
                pd.DataFrame(mla_rows).to_excel(writer, sheet_name='MLA-LAD All Years', index=False)
            if summary_rows:
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name='All Schemes Summary', index=False)
            if unique_dist_rows:
                pd.DataFrame(unique_dist_rows).to_excel(writer, sheet_name='MLA-LAD District Wise', index=False)
        print(f"  Saved: {excel_path}")
    except Exception as e:
        print(f"  Excel export error: {e}")

    total_time = time.time() - t0
    print(f"\n{'='*70}")
    print(f"DONE in {total_time:.1f}s")
    print(f"Output folder: {OUT_DIR}")
    print(f"  MLA-LAD All Years:         {len(mla_rows):>6} rows")
    print(f"  All Schemes Summary:        {len(summary_rows):>6} rows")
    print(f"  MLA-LAD District-wise:      {len(unique_dist_rows):>6} rows")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
