"""
UP MLA-LAD Fund Scraper — Year-wise × MLA-wise
================================================
Fetches financial fund summary AND physical progress for all UP MLAs
across all available financial years from mlaladsup.in.

Output: UP_MLA_LAD_Fund_YearWise.xlsx  (multi-sheet)
        UP_MLA_LAD_Fund_YearWise.csv   (combined flat file)
        UP_MLA_Physical_Progress.csv   (work counts)
"""

import sys
import json
import re
import time
import html
from html.parser import HTMLParser
import urllib.request
import urllib.error
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import datetime

sys.stdout.reconfigure(encoding='utf-8')

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_URL   = 'https://mlaladsup.in'
WORKS_URL  = f'{BASE_URL}/Main/getNikayDistrictWise'
FUND_REL_URL = f'{BASE_URL}/Main/MLAWiseFundRelease'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://mlaladsup.in/',
}

YEARS = {
    '2': '2023-24',
    '3': '2024-25',
    '4': '2025-26',
    '5': '2026-27',
}

SEAT_TYPES = {
    '1': 'Vidhan Sabha (MLA)',
    '2': 'Vidhan Parishad (MLC)',
}

OUTPUT_DIR = r'C:\Users\hp\Desktop\Mla funds'
EXCEL_OUT  = rf'{OUTPUT_DIR}\UP_MLA_LAD_Fund_YearWise.xlsx'
CSV_FUND   = rf'{OUTPUT_DIR}\UP_MLA_LAD_Fund_YearWise.csv'
CSV_PHYS   = rf'{OUTPUT_DIR}\UP_MLA_Physical_Progress.csv'

RETRY_LIMIT = 3
RETRY_DELAY = 5  # seconds

# ─── HELPERS ──────────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Strip all HTML tags, return plain text."""
    def __init__(self):
        super().__init__()
        self.texts = []
    def handle_data(self, data):
        t = data.strip()
        if t:
            self.texts.append(t)
    def get_text(self):
        return ' '.join(self.texts)

def strip_html(value):
    """Remove HTML tags & entities, return plain text."""
    if not isinstance(value, str):
        return value
    p = _TextExtractor()
    p.feed(html.unescape(value))
    return p.get_text().strip()

def clean_col(col):
    """Normalize a column name: strip HTML, collapse whitespace."""
    return re.sub(r'\s+', ' ', strip_html(str(col))).strip()

def post_json(url, payload, attempt=1):
    """POST JSON payload, return parsed response dict/list or None."""
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f'    HTTP {e.code} on attempt {attempt}: {url}')
    except Exception as e:
        print(f'    Error attempt {attempt}: {e}')
    if attempt < RETRY_LIMIT:
        time.sleep(RETRY_DELAY)
        return post_json(url, payload, attempt + 1)
    return None

def rows_from_response(resp):
    """Extract the data rows list from various response formats."""
    if resp is None:
        return []
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for key in ('data', 'Data', 'aaData', 'rows', 'Rows', 'result', 'Result'):
            if key in resp and isinstance(resp[key], list):
                return resp[key]
        # Try the first list value
        for v in resp.values():
            if isinstance(v, list) and len(v) > 0:
                return v
    return []

# ─── COLUMN MAPPINGS ──────────────────────────────────────────────────────────

FUND_COL_MAP = {
    'क्रम सं0':                              'Serial No',
    'माननीय विधायक का नाम व क्षेत्र':        'MLA Name & Constituency',
    'वित्तीय वर्ष':                           'Financial Year',
    'नोडल जनपद':                             'Nodal District',
    'गत वित्तीय वर्ष की अवशेष धनराशि (लाख में)':  'Opening Balance (Lakhs)',
    'आवंटित धनराशि (लाख में)':               'Allocated Funds (Lakhs)',
    'योग (अवशेष + आवंटित) (लाख में)':        'Total Opening+Allocated (Lakhs)',
    'स्वीकृत धनराशि (लाख में)':              'Sanctioned Amount (Lakhs)',
    'स्वीकृति हेतु अवशेष धनराशि (लाख में)':  'Balance for Sanction (Lakhs)',
    'व्यय धनराशि (लाख में)':                 'Expenditure (Lakhs)',
    'अवशेष धनराशि (लाख में)':                'Remaining Balance (Lakhs)',
    'प्रतिबद्ध धनराशि (लाख में)':            'Committed Amount (Lakhs)',
}

PHYS_COL_MAP = {
    'क्रम सं0':                              'Serial No',
    'माननीय विधायक का नाम व क्षेत्र':        'MLA Name & Constituency',
    'वित्तीय वर्ष':                           'Financial Year',
    'नोडल जनपद':                             'Nodal District',
    'प्रस्तावित कार्य':                       'Proposed Works',
    'स्वीकृत कार्य':                          'Sanctioned Works',
    'प्रारम्भ कार्य':                          'Started Works',
    'अप्रारम्भ कार्य':                         'Not Started Works',
    'पूर्ण कार्य':                             'Completed Works',
    'अपूर्ण कार्य':                            'Incomplete Works',
    'अनुशंसित कार्य':                         'Recommended Works',
}

def map_columns(df, col_map):
    """Rename cleaned column names using the mapping (partial match allowed)."""
    rename = {}
    for col in df.columns:
        col_clean = col.strip()
        # exact match first
        if col_clean in col_map:
            rename[col] = col_map[col_clean]
            continue
        # partial / fuzzy match
        for hindi, english in col_map.items():
            if hindi in col_clean or col_clean in hindi:
                rename[col] = english
                break
    return df.rename(columns=rename)

# ─── FETCH FUND DATA ──────────────────────────────────────────────────────────

def fetch_fund_data(year_id, year_label, seat_type_id, seat_type_label):
    """Fetch MLAWiseApplication data for one year × seat type."""
    print(f'  Fetching FUND  | {year_label} | {seat_type_label}')
    payload = {
        "obj": {
            "optMode":     "MLAWiseApplication",
            "districtId":  -1,
            "yearId":      year_id,
            "seatId":      "-1",
            "seatTypeId":  seat_type_id,
        }
    }
    resp = post_json(WORKS_URL, payload)
    rows = rows_from_response(resp)
    if not rows:
        print(f'    → No rows returned.')
        return pd.DataFrame()

    # Build DataFrame from list-of-dicts (each dict has column->value)
    # The API returns HTML table rows where keys are raw HTML column headers
    df = pd.DataFrame(rows)

    # Clean all column names
    df.columns = [clean_col(c) for c in df.columns]

    # Clean all cell values
    for col in df.columns:
        df[col] = df[col].apply(strip_html)

    # Apply English column mapping
    df = map_columns(df, FUND_COL_MAP)

    # Add metadata columns
    df.insert(0, 'Year ID',     year_id)
    df.insert(1, 'Year Label',  year_label)
    df.insert(2, 'House',       seat_type_label)
    df.insert(3, 'Seat Type ID', seat_type_id)

    print(f'    → {len(df)} rows, {len(df.columns)} cols')
    return df


def fetch_physical_data(year_id, year_label, seat_type_id, seat_type_label):
    """Fetch getWorkMLAPhysicalWise data for one year × seat type."""
    print(f'  Fetching PHYS  | {year_label} | {seat_type_label}')
    payload = {
        "obj": {
            "optMode":     "getWorkMLAPhysicalWise",
            "districtId":  -1,
            "yearId":      year_id,
            "seatId":      "-1",
            "seatTypeId":  seat_type_id,
        }
    }
    resp = post_json(WORKS_URL, payload)
    rows = rows_from_response(resp)
    if not rows:
        print(f'    → No rows returned.')
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.columns = [clean_col(c) for c in df.columns]
    for col in df.columns:
        df[col] = df[col].apply(strip_html)
    df = map_columns(df, PHYS_COL_MAP)

    df.insert(0, 'Year ID',     year_id)
    df.insert(1, 'Year Label',  year_label)
    df.insert(2, 'House',       seat_type_label)
    df.insert(3, 'Seat Type ID', seat_type_id)

    print(f'    → {len(df)} rows, {len(df.columns)} cols')
    return df


def fetch_fund_release(year_id, year_label, seat_type_id, seat_type_label):
    """Try to fetch MLAWiseFundRelease (installment-level) data."""
    print(f'  Fetching FUND RELEASE | {year_label} | {seat_type_label}')
    payload = {
        "obj": {
            "optMode":     "MLAWiseFundRelease",
            "districtId":  -1,
            "yearId":      year_id,
            "seatId":      "-1",
            "seatTypeId":  seat_type_id,
        }
    }
    # Try the main works URL first
    resp = post_json(WORKS_URL, payload)
    rows = rows_from_response(resp)
    if rows:
        print(f'    → {len(rows)} rows from WORKS_URL')
        df = pd.DataFrame(rows)
        df.columns = [clean_col(c) for c in df.columns]
        for col in df.columns:
            df[col] = df[col].apply(strip_html)
        df.insert(0, 'Year ID',     year_id)
        df.insert(1, 'Year Label',  year_label)
        df.insert(2, 'House',       seat_type_label)
        return df

    # Try dedicated fund release URL
    resp2 = post_json(FUND_REL_URL, payload)
    rows2 = rows_from_response(resp2)
    if rows2:
        print(f'    → {len(rows2)} rows from FUND_REL_URL')
        df = pd.DataFrame(rows2)
        df.columns = [clean_col(c) for c in df.columns]
        for col in df.columns:
            df[col] = df[col].apply(strip_html)
        df.insert(0, 'Year ID',     year_id)
        df.insert(1, 'Year Label',  year_label)
        df.insert(2, 'House',       seat_type_label)
        return df

    print(f'    → No fund release data.')
    return pd.DataFrame()

# ─── EXCEL STYLING ────────────────────────────────────────────────────────────

HEADER_FILL   = PatternFill('solid', fgColor='1F5C8B')
SUBHEAD_FILL  = PatternFill('solid', fgColor='2E86AB')
ALT_ROW_FILL  = PatternFill('solid', fgColor='EBF5FB')
HEADER_FONT   = Font(bold=True, color='FFFFFF', size=10)
NORMAL_FONT   = Font(size=9)
THIN_BORDER   = Border(
    left=Side(style='thin', color='CCCCCC'),
    right=Side(style='thin', color='CCCCCC'),
    top=Side(style='thin', color='CCCCCC'),
    bottom=Side(style='thin', color='CCCCCC'),
)

def style_sheet(ws):
    """Apply consistent styling to a worksheet."""
    # Header row
    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[1].height = 36

    # Data rows
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        fill = ALT_ROW_FILL if row_idx % 2 == 0 else None
        for cell in row:
            cell.font = NORMAL_FONT
            cell.border = THIN_BORDER
            if fill:
                cell.fill = fill
            # Right-align numeric columns
            if isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal='right')
            else:
                cell.alignment = Alignment(horizontal='left', wrap_text=False)

    # Auto-fit column widths (capped at 40)
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        max_len = max(
            (len(str(c.value)) if c.value is not None else 0 for c in col_cells),
            default=10
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

    # Freeze pane below header
    ws.freeze_panes = 'A2'


def add_df_to_sheet(wb, sheet_name, df, title_row=None):
    """Write a DataFrame to a named sheet with styling."""
    if df.empty:
        ws = wb.create_sheet(title=sheet_name)
        ws['A1'] = 'No data available'
        return ws
    ws = wb.create_sheet(title=sheet_name[:31])  # Excel 31-char limit
    if title_row:
        ws.append([title_row])
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
        ws['A1'].font = Font(bold=True, size=12, color='1F5C8B')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.append(list(df.columns))
        for row in df.itertuples(index=False):
            ws.append(list(row))
        # Style from row 2 (headers)
        for cell in ws[2]:
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = THIN_BORDER
        ws.row_dimensions[2].height = 36
        for row_idx, row in enumerate(ws.iter_rows(min_row=3), start=3):
            fill = ALT_ROW_FILL if row_idx % 2 == 0 else None
            for cell in row:
                cell.font = NORMAL_FONT
                cell.border = THIN_BORDER
                if fill:
                    cell.fill = fill
        for col_idx, col_cells in enumerate(ws.columns, start=1):
            max_len = max((len(str(c.value)) if c.value is not None else 0 for c in col_cells), default=10)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)
        ws.freeze_panes = 'A3'
    else:
        ws.append(list(df.columns))
        for row in df.itertuples(index=False):
            ws.append(list(row))
        style_sheet(ws)
    return ws


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print('=' * 70)
    print('UP MLA-LAD Fund Scraper — Year-wise × MLA-wise')
    print(f'Started: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)

    all_fund_dfs  = []
    all_phys_dfs  = []
    all_releas_dfs = []
    year_dfs = {}  # {year_label: df}

    # ── 1. Fetch all fund + physical data (8 calls each = 16 total) ──────────
    for year_id, year_label in YEARS.items():
        print(f'\n── Year: {year_label} ──────────────────────────────')
        year_frames = []
        for seat_type_id, seat_type_label in SEAT_TYPES.items():
            # Fund summary
            df_fund = fetch_fund_data(year_id, year_label, seat_type_id, seat_type_label)
            if not df_fund.empty:
                all_fund_dfs.append(df_fund)
                year_frames.append(df_fund)

            # Physical progress
            df_phys = fetch_physical_data(year_id, year_label, seat_type_id, seat_type_label)
            if not df_phys.empty:
                all_phys_dfs.append(df_phys)

            time.sleep(0.5)  # polite delay

        if year_frames:
            year_dfs[year_label] = pd.concat(year_frames, ignore_index=True)

    # ── 2. Try fund release installment data (bonus) ─────────────────────────
    print(f'\n── Fund Release Installments ───────────────────────')
    for year_id, year_label in YEARS.items():
        df_rel = fetch_fund_release(year_id, year_label, '1', 'Vidhan Sabha (MLA)')
        if not df_rel.empty:
            all_releas_dfs.append(df_rel)

    # ── 3. Merge all years into combined frames ───────────────────────────────
    if not all_fund_dfs:
        print('\n❌ No fund data fetched. Check network connectivity.')
        return

    df_all_fund  = pd.concat(all_fund_dfs,  ignore_index=True)
    df_all_phys  = pd.concat(all_phys_dfs,  ignore_index=True) if all_phys_dfs else pd.DataFrame()
    df_all_releas = pd.concat(all_releas_dfs, ignore_index=True) if all_releas_dfs else pd.DataFrame()

    # Convert numeric columns
    numeric_keywords = ['Lakhs', 'Balance', 'Amount', 'Works', 'Funds', 'Opening', 'Expenditure',
                        'Sanctioned', 'Allocated', 'Committed', 'Remaining', 'Total']
    for df in [df_all_fund, df_all_phys]:
        if df.empty:
            continue
        for col in df.columns:
            if any(k in col for k in numeric_keywords):
                df[col] = pd.to_numeric(df[col], errors='coerce')

    # ── 4. Build pivot summary (MLA-wise totals across all years) ────────────
    mla_col = 'MLA Name & Constituency'
    house_col = 'House'
    numeric_fund_cols = [c for c in df_all_fund.columns
                         if any(k in c for k in ['Lakhs', 'Balance', 'Amount', 'Funds',
                                                  'Opening', 'Expenditure', 'Sanctioned',
                                                  'Allocated', 'Committed', 'Remaining', 'Total'])]

    pivot_frames = []
    if mla_col in df_all_fund.columns and numeric_fund_cols:
        group_cols = [mla_col]
        if house_col in df_all_fund.columns:
            group_cols.insert(0, house_col)
        if 'Nodal District' in df_all_fund.columns:
            group_cols.append('Nodal District')
        pivot = df_all_fund.groupby(group_cols)[numeric_fund_cols].sum(numeric_only=True).reset_index()
        pivot_frames.append(pivot)
    df_pivot = pivot_frames[0] if pivot_frames else pd.DataFrame()

    # ── 5. Write Excel ───────────────────────────────────────────────────────
    print(f'\n── Writing Excel: {EXCEL_OUT}')
    from openpyxl import Workbook
    wb = Workbook()
    # Remove default sheet
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']

    # Cover sheet
    ws_cover = wb.create_sheet('README', 0)
    ws_cover['A1'] = 'UP MLA-LAD Fund Data — Year-wise & MLA-wise'
    ws_cover['A1'].font = Font(bold=True, size=16, color='1F5C8B')
    ws_cover['A2'] = f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    ws_cover['A3'] = f'Source: https://mlaladsup.in'
    ws_cover['A4'] = f'Total fund rows: {len(df_all_fund)}'
    ws_cover['A5'] = f'Years covered: {", ".join(YEARS.values())}'
    ws_cover['A6'] = f'Houses: Vidhan Sabha (MLA) + Vidhan Parishad (MLC)'
    ws_cover['A7'] = ''
    ws_cover['A8'] = 'Sheets in this workbook:'
    entries = [
        ('README',          'This cover sheet'),
        ('All Years Fund',  'Complete fund data — all years, both houses'),
        ('Physical Progress','Work completion counts — all years, both houses'),
    ]
    for year_label in YEARS.values():
        entries.append((year_label, f'Fund data for {year_label} only'))
    if not df_pivot.empty:
        entries.append(('MLA Pivot Summary', 'Totals per MLA across all years'))
    if not df_all_releas.empty:
        entries.append(('Fund Release',      'Installment-wise fund release data'))
    for i, (sheet, desc) in enumerate(entries, start=9):
        ws_cover[f'A{i}'] = sheet
        ws_cover[f'B{i}'] = desc
    ws_cover.column_dimensions['A'].width = 25
    ws_cover.column_dimensions['B'].width = 55

    # All Years Fund sheet
    add_df_to_sheet(wb, 'All Years Fund', df_all_fund,
                    title_row='UP MLA-LAD Fund Summary — All Years Combined')

    # Physical Progress sheet
    if not df_all_phys.empty:
        add_df_to_sheet(wb, 'Physical Progress', df_all_phys,
                        title_row='UP MLA-LAD Physical Work Progress — All Years')

    # Year-wise sheets
    for year_label, df_year in year_dfs.items():
        add_df_to_sheet(wb, year_label, df_year,
                        title_row=f'UP MLA-LAD Fund Summary — {year_label}')

    # Pivot summary
    if not df_pivot.empty:
        add_df_to_sheet(wb, 'MLA Pivot Summary', df_pivot,
                        title_row='UP MLA-LAD Totals Per MLA (All Years)')

    # Fund Release sheet
    if not df_all_releas.empty:
        add_df_to_sheet(wb, 'Fund Release', df_all_releas,
                        title_row='UP MLA-LAD Installment-wise Fund Release')

    wb.save(EXCEL_OUT)
    print(f'  ✅ Excel saved: {EXCEL_OUT}')

    # ── 6. Write CSVs ────────────────────────────────────────────────────────
    df_all_fund.to_csv(CSV_FUND, index=False, encoding='utf-8-sig')
    print(f'  ✅ Fund CSV saved: {CSV_FUND}')
    if not df_all_phys.empty:
        df_all_phys.to_csv(CSV_PHYS, index=False, encoding='utf-8-sig')
        print(f'  ✅ Physical CSV saved: {CSV_PHYS}')

    # ── 7. Summary ───────────────────────────────────────────────────────────
    print('\n' + '=' * 70)
    print('SCRAPE COMPLETE')
    print('=' * 70)
    print(f'  Total fund rows  : {len(df_all_fund)}')
    print(f'  Total phys rows  : {len(df_all_phys)}')
    if not df_all_fund.empty and 'Allocated Funds (Lakhs)' in df_all_fund.columns:
        total_alloc = pd.to_numeric(df_all_fund['Allocated Funds (Lakhs)'], errors='coerce').sum()
        print(f'  Total allocated  : ₹ {total_alloc:,.2f} Lakhs')
    if not df_all_fund.empty and 'Expenditure (Lakhs)' in df_all_fund.columns:
        total_exp = pd.to_numeric(df_all_fund['Expenditure (Lakhs)'], errors='coerce').sum()
        print(f'  Total expenditure: ₹ {total_exp:,.2f} Lakhs')
    print(f'\n  Excel → {EXCEL_OUT}')
    print(f'  CSV   → {CSV_FUND}')
    print(f'  Finished: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')


if __name__ == '__main__':
    main()
