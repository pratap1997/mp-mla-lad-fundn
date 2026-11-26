# Scrape winner affidavit profiles from MyNeta.info (UP 2022, Rajasthan 2023, Lok Sabha 2024)
# Outputs UTF-8-SIG CSVs with Candidate, Constituency, Party, Criminal Cases,
# Education, Total Assets (INR), Liabilities (INR), and MyNeta Profile URL.

import os
import re
import csv
import sys
import html
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

TARGETS = [
    ('UP_2022',        'https://myneta.info/UttarPradesh2022/index.php?action=show_winners&sort=default', 'MyNeta_UP_2022.csv'),
    ('Rajasthan_2023', 'https://myneta.info/Rajasthan2023/index.php?action=show_winners&sort=default',    'MyNeta_Rajasthan_2023.csv'),
    ('LokSabha_2024',  'https://myneta.info/LokSabha2024/index.php?action=show_winners&sort=default',     'MyNeta_LokSabha_2024.csv'),
]


def clean_text(raw: str) -> str:
    txt = re.sub(r'<[^>]+>', ' ', raw)
    txt = html.unescape(txt).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', txt).strip()


def parse_rupees(raw: str) -> int:
    m = re.search(r'Rs\s*([\d,]+)', raw)
    if not m:
        return 0
    try:
        return int(m.group(1).replace(',', ''))
    except ValueError:
        return 0


def scrape_one(label: str, url: str, out_csv: str) -> int:
    req = urllib.request.Request(url, headers=HDRS)
    page_html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
    base_dir = url.rsplit('/', 1)[0] + '/'

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', page_html, re.S)
    records = []
    for r in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
        if len(tds) < 8:
            continue
        sno = clean_text(tds[0])
        if not sno.isdigit():
            continue

        link_m = re.search(r'href=["\']([^"\']*candidate\.php[^"\']*)["\']', tds[1], re.I)
        profile_url = (base_dir + link_m.group(1)) if link_m else ''
        candidate = clean_text(tds[1])
        constituency = clean_text(tds[2])
        party = clean_text(tds[3])
        cases = clean_text(tds[4])
        education = clean_text(tds[5])
        assets_raw = clean_text(tds[6])
        liab_raw = clean_text(tds[7])

        records.append([
            sno, candidate, constituency, party,
            int(cases) if cases.isdigit() else 0,
            education,
            parse_rupees(assets_raw),
            parse_rupees(liab_raw),
            assets_raw.split('~')[0].strip(),
            liab_raw.split('~')[0].strip(),
            profile_url,
        ])

    out_path = os.path.join(OUT_DIR, out_csv)
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow([
            'SNo', 'Candidate', 'Constituency', 'Party', 'Criminal Cases',
            'Education', 'Assets (INR)', 'Liabilities (INR)',
            'Assets Display', 'Liabilities Display', 'MyNeta URL'
        ])
        w.writerows(records)

    print(f'[{label}] Saved {len(records)} winners -> {out_csv}')
    return len(records)


def main():
    for label, url, fn in TARGETS:
        try:
            scrape_one(label, url, fn)
        except Exception as e:
            print(f'[{label}] Error: {e}')


if __name__ == '__main__':
    main()
