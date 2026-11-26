# Scrape all 18th UP Vidhan Sabha MLAs + official profile details from uplegisassembly.gov.in
# Uses POST /angular.asmx/show_MemberList {Id: 'MLA_HI', parm: '18'}
# and GET /Members/mla_profile_hi.aspx?mla_id=<mla_code>&assembly_no=18&is_resign=0

import os
import re
import csv
import sys
import ssl
import json
import html
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE = 'https://uplegisassembly.gov.in'
API_URL = f'{BASE}/angular.asmx/show_MemberList'
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(OUT_DIR, 'UP_VidhanSabha_18_MLAs.csv')
CTX = ssl._create_unverified_context()
HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def fetch_profile(mla: dict) -> dict:
    code = mla.get('mla_code')
    resign = mla.get('flg_resign') or '0'
    url = f'{BASE}/Members/mla_profile_hi.aspx?mla_id={code}&assembly_no=18&is_resign={resign}'
    spa_url = f'{BASE}/Members/main_members_hi.aspx#/Data/{code}/18/{resign}'
    info = {
        'mla_code': code,
        'mla_sno': mla.get('mla_sno', ''),
        'mla_name_hi': (mla.get('mla_name') or '').strip(),
        'mla_name_en': (mla.get('mla_name_eng') or '').strip(),
        'ac_name_hi': (mla.get('ac_name') or '').strip(),
        'ac_name_en': (mla.get('ac_name_eng') or '').strip(),
        'district_hi': (mla.get('district_name') or '').strip(),
        'district_en': (mla.get('district_name_eng') or '').strip(),
        'party_hi': (mla.get('party_name_hindi') or '').strip(),
        'party_en': (mla.get('party_name_english') or '').strip(),
        'party_short': (mla.get('partyShortNameEng') or '').strip(),
        'gender': (mla.get('gender') or '').strip(),
        'dob': '',
        'education': '',
        'phone': '',
        'email': '',
        'photo_url': '',
        'profile_url': spa_url,
    }
    try:
        req = urllib.request.Request(url, headers=HDRS)
        h = urllib.request.urlopen(req, timeout=20, context=CTX).read().decode('utf-8', 'ignore')
        img_m = re.search(r'<img[^>]+src=["\']([^"\']*(?:mla|member|photo|Upload)[^"\']*)["\']', h, re.I)
        if img_m:
            src = img_m.group(1)
            info['photo_url'] = (BASE + '/' + src.lstrip('./')) if not src.startswith('http') else src
        em_m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', h)
        if em_m:
            info['email'] = em_m.group(0)
        ph_m = re.search(r'(?:\+91[\s-]?)?[6-9]\d{9}', h)
        if ph_m:
            info['phone'] = ph_m.group(0)
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S):
            tds = [clean(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
            if len(tds) >= 2:
                k, v = tds[0], tds[1]
                if any(w in k for w in ['जन्म', 'Birth', 'DOB']):
                    info['dob'] = v
                elif any(w in k for w in ['शैक्षिक', 'शिक्षा', 'Education', 'Qualification']):
                    info['education'] = v
    except Exception:
        pass
    return info


def main():
    print('Fetching 18th UP Vidhan Sabha member list...')
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({'Id': 'MLA_HI', 'parm': '18'}).encode('utf-8'),
        headers={**HDRS, 'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    res = json.loads(urllib.request.urlopen(req, timeout=30, context=CTX).read().decode('utf-8'))
    members = res.get('d', [])
    print(f'Found {len(members)} MLAs. Fetching official profiles in parallel...')

    results = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(fetch_profile, m) for m in members]
        for i, fut in enumerate(as_completed(futs), 1):
            results.append(fut.result())
            if i % 100 == 0 or i == len(members):
                print(f'  [{i}/{len(members)}] profiles fetched')

    results.sort(key=lambda r: int(r['mla_code'] or 0))
    fields = list(results[0].keys()) if results else []
    with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    print(f'Saved {len(results)} UP Vidhan Sabha MLA profiles -> {OUT_CSV}')


if __name__ == '__main__':
    main()
