# Scrape 18th Lok Sabha MP legislative activeness (Attendance, Debates, Questions, Private Member Bills)
# from PRS Legislative Research (https://prsindia.org/mptrack/18th-lok-sabha)

import os
import re
import csv
import sys
import ssl
import html
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PRS_LokSabha_18_Activeness.csv')
BASE    = 'https://prsindia.org'
LIST_URL = f'{BASE}/mptrack/18th-lok-sabha'
CTX     = ssl._create_unverified_context()
HDRS    = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HDRS)
    return urllib.request.urlopen(req, timeout=25, context=CTX).read().decode('utf-8', 'ignore')


def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def parse_mp(slug: str) -> list | None:
    url = f'{BASE}/{slug}'
    try:
        h = fetch(url)
    except Exception:
        return None

    name_m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S | re.I)
    name = clean(name_m.group(1)) if name_m else slug.split('/')[-1].replace('-', ' ').title()

    txt = clean(h)
    const_m = re.search(r'Constituency\s*:?\s*([A-Za-z0-9\s\(\)\.\-]+?)(?:State|Party|Term|Lok Sabha)', txt)
    state_m = re.search(r'State\s*:?\s*([A-Za-z\s&]+?)(?:Party|Constituency|Term|Nature)', txt)
    party_m = re.search(r'Party\s*:?\s*([A-Za-z0-9\s\(\)\.\-]+?)(?:Term|Nature|Attendance|Education)', txt)

    att_m = re.search(r'Attendance\s+Selected MP\s+(\d+)\s*%', txt)
    deb_m = re.search(r'No\. of Debates\s+Selected MP\s+(\d+)', txt)
    q_m   = re.search(r'No\. of Questions\s+Selected MP\s+(\d+)', txt)
    pmb_m = re.search(r"Private Member's Bills\s+Selected MP\s+(\d+)", txt)

    return [
        name,
        const_m.group(1).strip() if const_m else '',
        state_m.group(1).strip() if state_m else '',
        party_m.group(1).strip() if party_m else '',
        int(att_m.group(1)) if att_m else '',
        int(deb_m.group(1)) if deb_m else 0,
        int(q_m.group(1)) if q_m else 0,
        int(pmb_m.group(1)) if pmb_m else 0,
        url,
    ]


def main():
    print('Fetching 18th Lok Sabha MP directory (paginated)...')
    slugs = set()
    for p in range(0, 80):
        try:
            page = fetch(f'{LIST_URL}?page={p}')
        except Exception:
            break
        found = set(re.findall(r'mptrack/18th-lok-sabha/[a-z0-9-]+', page))
        new_ones = found - slugs
        if not new_ones:
            break
        slugs.update(new_ones)
    slugs = sorted(slugs)
    print(f'Found {len(slugs)} MP profile URLs. Scraping in parallel...')

    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(parse_mp, s) for s in slugs]
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if res:
                rows.append(res)
            if i % 100 == 0 or i == len(slugs):
                print(f'  [{i}/{len(slugs)}] scraped ({len(rows)} valid)')

    rows.sort(key=lambda r: r[0])
    with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['MP Name', 'Constituency', 'State', 'Party', 'Attendance %', 'Debates', 'Questions Asked', 'Private Member Bills', 'PRS URL'])
        w.writerows(rows)

    print(f'Saved {len(rows)} MP activeness profiles -> {OUT_CSV}')


if __name__ == '__main__':
    main()
