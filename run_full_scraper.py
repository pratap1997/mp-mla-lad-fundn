import os
import sys
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
from bs4 import BeautifulSoup
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://mlaladsup.in"
DROPDOWN_URL = f"{BASE_URL}/DropdownBinder/fillDropdown"
WORKS_URL = f"{BASE_URL}/Main/getNikayDistrictWise"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*; q=0.01'
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_members(seat_type_id):
    """Fetch all members for a seat type (1: Vidhan Sabha, 2: Vidhan Parishad)."""
    payload = {"obj": {"optMode": "bindMLA", "seatTypeId": str(seat_type_id)}}
    req = urllib.request.Request(DROPDOWN_URL, data=json.dumps(payload).encode('utf-8'), headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))

def fetch_mla_works(member, seat_type_id, max_retries=3):
    seat_id = member['id']
    name = member['value'].strip()
    cache_file = os.path.join(DATA_DIR, f"mla_{seat_type_id}_{seat_id}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return seat_id, name, seat_type_id, len(data.get('Table_0', [])), "cached"
        except Exception:
            pass

    payload = {
        "obj": {
            "applicationType": "-1",
            "yearId": "-1",
            "seatId": str(seat_id),
            "seatTypeId": str(seat_type_id),
            "districtId": -1,
            "optMode": "getWorkDetails"
        }
    }
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(WORKS_URL, data=json.dumps(payload).encode('utf-8'), headers=HEADERS, method='POST')
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                rows = len(data.get('Table_0', []))
                return seat_id, name, seat_type_id, rows, "downloaded"
        except Exception as e:
            if attempt == max_retries - 1:
                return seat_id, name, seat_type_id, 0, f"error: {e}"
            time.sleep(1 + attempt)

def parse_html_text_and_link(html_val):
    if not html_val:
        return "", ""
    val_str = str(html_val).strip()
    if '<a ' in val_str:
        soup = BeautifulSoup(val_str, 'html.parser')
        a = soup.find('a')
        if a:
            link = a.get('href', '').strip()
            if link and not link.startswith('http') and not link.startswith('javascript'):
                link = BASE_URL + (link if link.startswith('/') else '/' + link)
            text = a.get_text(strip=True)
            return text, link
        return soup.get_text(strip=True), ""
    clean = re.sub(r'<[^>]+>', ' ', val_str)
    return re.sub(r'\s+', ' ', clean).strip(), ""

def parse_amount_spent(val):
    """Parse '90.40 Thousands', '2.80 Lakhs', etc. into float Lakhs."""
    if not val or val == 'None' or val == '':
        return 0.0
    val_str = str(val).strip()
    val_str = re.sub(r'<[^>]+>', ' ', val_str).strip()
    
    m = re.search(r'([\d\.]+)\s*(Thousands?|Lakhs?|Crores?|Cr)?', val_str, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1))
            unit = (m.group(2) or '').lower()
            if 'thousand' in unit:
                return round(num / 100.0, 4)
            elif 'lakh' in unit:
                return round(num, 4)
            elif 'crore' in unit or 'cr' in unit:
                return round(num * 100.0, 4)
            else:
                return round(num, 4)
        except ValueError:
            return 0.0
    return 0.0

def process_raw_data(all_members):
    print("\n--- Processing Raw JSON Files into Clean Records ---")
    rows = []
    
    for member, seat_type_id in all_members:
        seat_id = member['id']
        name = member['value'].strip()
        house = "विधान सभा (Vidhan Sabha / MLA)" if seat_type_id == 1 else "विधान परिषद (Vidhan Parishad / MLC)"
        
        cache_file = os.path.join(DATA_DIR, f"mla_{seat_type_id}_{seat_id}.json")
        if not os.path.exists(cache_file):
            continue
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        table = data.get('Table_0', [])
        for item in table:
            # MLA name & constituency parsing
            prop_str = item.get('प्रस्तावक का नाम, पदनाम  व क्षेत्र') or ''
            prop_clean, _ = parse_html_text_and_link(prop_str)
            
            # Work description & work type
            work_desc, _ = parse_html_text_and_link(item.get('कार्य का विवरण'))
            work_type, _ = parse_html_text_and_link(item.get('कार्य का प्रकार'))
            
            # Location fields
            district, _ = parse_html_text_and_link(item.get('जनपद'))
            block, _ = parse_html_text_and_link(item.get('ब्लॉक/निकाय '))
            ward_gp, _ = parse_html_text_and_link(item.get('वार्ड/ग्राo पंo का नाम'))
            village_moh, _ = parse_html_text_and_link(item.get('मोहल्ले/ ग्राम का नाम'))
            
            loc_parts = [p for p in [village_moh, ward_gp, block, district] if p and p != 'None']
            full_location = ", ".join(loc_parts)
            
            # Cost in Lakhs
            cost_raw = item.get('कार्यदायी संस्था द्वारा <br/>आगणित लागत <br/> (लाख में )')
            try:
                cost_lakhs = float(cost_raw) if cost_raw is not None else 0.0
            except ValueError:
                cost_lakhs = 0.0
                
            # Under 10 Lakh / More than 10 Lakh classification
            if cost_lakhs <= 10.0:
                under_10_lakh = cost_lakhs
                more_than_10_lakh = None
                cost_category = "Under 10 Lakh (<= 10 लाख)"
            else:
                under_10_lakh = None
                more_than_10_lakh = cost_lakhs
                cost_category = "More than 10 Lakh (> 10 लाख)"
                
            # Amount spent
            raw_spent = item.get(' वित्तीय प्रगति <br/> (प्रतिशत में )')
            spent_lakhs = parse_amount_spent(raw_spent)
            spent_rupees = round(spent_lakhs * 100000.0, 2)
            
            # Physical progress %
            phys_prog = item.get(' भौतिक प्रगति <br/> (प्रतिशत में )')
            try:
                phys_prog = float(phys_prog) if phys_prog is not None else 0.0
            except ValueError:
                phys_prog = 0.0
                
            # Determine work status
            completion_date, _ = parse_html_text_and_link(item.get('कार्य पूर्ण <br/>की तिथि'))
            start_date, _ = parse_html_text_and_link(item.get('कार्य प्रारम्भ <br/> की तिथि'))
            if completion_date or phys_prog >= 100.0:
                work_status = "पूर्ण (Completed)"
            elif phys_prog > 0 or start_date:
                work_status = "प्रगति पर (In Progress)"
            elif item.get('आईoडीoएo</br>द्वारा परिपत्र</br> अपलोड की तिथि'):
                work_status = "स्वीकृत (Sanctioned)"
            else:
                work_status = "अनुशंसित / प्रक्रियाधीन (Proposed / Processing)"
                
            # Documents
            _, dpr_link = parse_html_text_and_link(item.get('कार्यदायी संस्था  <br/>द्वारा प्रेषित <br/> डीoपीoआरo'))
            _, circular_link = parse_html_text_and_link(item.get('आईoडीoएo <br/>द्वारा अपलोड <br/> परिपत्र'))
            
            row = {
                'विधायक / एमएलसी नाम (Representative Name)': name,
                'सदन (House)': house,
                'प्रस्तावक विवरण (Constituency / Details)': prop_clean,
                'वित्तीय वर्ष (Financial Year)': item.get('वित्तीय वर्ष') or '',
                'कार्य आईoडीo (Work ID)': item.get('कार्य आईoडीo'),
                'कार्य का विवरण (Name of Work / Description)': work_desc,
                'कार्य का प्रकार (Work Type)': work_type,
                'जनपद (District)': district,
                'ब्लॉक / निकाय (Block / Urban Body)': block,
                'वार्ड / ग्राम पंचायत (Ward / Gram Panchayat)': ward_gp,
                'मोहल्ला / ग्राम (Village / Mohalla)': village_moh if village_moh != 'None' else '',
                'कार्य स्थल का पूर्ण पता (Full Location)': full_location,
                'आगणित लागत लाख में (Estimated Cost in Lakhs)': cost_lakhs,
                '10 लाख तक के कार्य (Under 10 Lakh Column - Lakhs)': under_10_lakh,
                '10 लाख से अधिक के कार्य (More Than 10 Lakh Column - Lakhs)': more_than_10_lakh,
                'लागत श्रेणी (Cost Category)': cost_category,
                'व्यय धनराशि लाख में (Amount Spent in Lakhs)': spent_lakhs,
                'व्यय धनराशि रु० में (Amount Spent in Rs)': spent_rupees,
                'प्रथम किश्त धनराशि रु० (1st Installment Rs)': item.get('प्रथम किश्त की <br/> धनराशि (रुo में )'),
                'द्वितीय किश्त धनराशि रु० (2nd Installment Rs)': item.get('आईoडीoएo <br/>द्वारा निर्गत<br/>द्वितीय किश्त की<br/> धनराशि'),
                'भौतिक प्रगति % (Physical Progress %)': phys_prog,
                'कार्य की स्थिति (Work Status)': work_status,
                'कार्यदायी संस्था का नाम (Implementing Agency)': item.get('कार्यदायी संस्था </br> का नाम') or '',
                'ठेकेदार का नाम (Contractor Name)': item.get('ठेकेदार का नाम') or '',
                'अनुशंसा की तिथि (Recommendation Date)': item.get('अनुशंसा की तिथि') or '',
                'कार्यदायी संस्था नामित तिथि (Agency Nominated Date)': item.get('कार्यदायी संस्था  <br/> नामित की तिथि') or '',
                'डीoपीoआर प्रेषण तिथि (DPR Submission Date)': item.get('कार्यदायी संस्था  <br/> द्वारा डीoपीoआर <br/> प्रेषण की तिथि') or '',
                'विधायक सहमति तिथि (MLA Consent Date)': item.get('माo विधायक</br>द्वारा सहमति</br> देने की तिथि') or '',
                'परिपत्र अपलोड तिथि (Sanction Circular Date)': item.get('आईoडीoएo</br>द्वारा परिपत्र</br> अपलोड की तिथि') or '',
                'निविदा प्रारम्भ तिथि (Tender Start Date)': item.get('निविदा प्रारम्भ<br/> की तिथि') or '',
                'निविदा पूर्ण तिथि (Tender Complete Date)': item.get('निविदा पूर्ण<br/> की तिथि') or '',
                'कार्य प्रारम्भ तिथि (Work Start Date)': start_date,
                'कार्य पूर्ण तिथि (Work Completion Date)': completion_date,
                'समय / कुल दिन (Time - Days Elapsed)': item.get('Days'),
                'कार्य जोड़ने की तिथि (Entry Date)': item.get('कार्य जोड़ने<br/> की तिथि') or '',
                'डीoपीoआरo लिंक (DPR Link)': dpr_link,
                'परिपत्र लिंक (Circular Link)': circular_link,
            }
            rows.append(row)
            
    df_works = pd.DataFrame(rows)
    print(f"Total processed works rows: {len(df_works)}")
    return df_works

def create_summary_dataframe(df_works, all_members):
    print("\n--- Generating MLA Summary Metrics ---")
    summary_rows = []
    
    for member, seat_type_id in all_members:
        name = member['value'].strip()
        house = "विधान सभा (Vidhan Sabha / MLA)" if seat_type_id == 1 else "विधान परिषद (Vidhan Parishad / MLC)"
        
        m_df = df_works[df_works['विधायक / एमएलसी नाम (Representative Name)'] == name]
        total_works = len(m_df)
        
        if total_works > 0:
            under_10_df = m_df[m_df['आगणित लागत लाख में (Estimated Cost in Lakhs)'] <= 10.0]
            more_10_df = m_df[m_df['आगणित लागत लाख में (Estimated Cost in Lakhs)'] > 10.0]
            
            under_10_cnt = len(under_10_df)
            under_10_cost = round(under_10_df['आगणित लागत लाख में (Estimated Cost in Lakhs)'].sum(), 4)
            
            more_10_cnt = len(more_10_df)
            more_10_cost = round(more_10_df['आगणित लागत लाख में (Estimated Cost in Lakhs)'].sum(), 4)
            
            total_cost = round(m_df['आगणित लागत लाख में (Estimated Cost in Lakhs)'].sum(), 4)
            total_spent = round(m_df['व्यय धनराशि लाख में (Amount Spent in Lakhs)'].sum(), 4)
            
            completed_cnt = len(m_df[m_df['कार्य की स्थिति (Work Status)'] == "पूर्ण (Completed)"])
            in_prog_cnt = len(m_df[m_df['कार्य की स्थिति (Work Status)'] == "प्रगति पर (In Progress)"])
            sanctioned_cnt = len(m_df[m_df['कार्य की स्थिति (Work Status)'] == "स्वीकृत (Sanctioned)"])
            proposed_cnt = len(m_df[m_df['कार्य की स्थिति (Work Status)'] == "अनुशंसित / प्रक्रियाधीन (Proposed / Processing)"])
            
            avg_phys = round(m_df['भौतिक प्रगति % (Physical Progress %)'].mean(), 2)
            districts = ", ".join(m_df['जनपद (District)'].dropna().unique())
        else:
            under_10_cnt = under_10_cost = more_10_cnt = more_10_cost = 0
            total_cost = total_spent = completed_cnt = in_prog_cnt = sanctioned_cnt = proposed_cnt = 0
            avg_phys = 0.0
            districts = ""
            
        summary_rows.append({
            'विधायक / एमएलसी नाम (Representative Name)': name,
            'सदन (House)': house,
            'संबंधित जनपद (Districts)': districts,
            'कुल अनुशंसित कार्य (Total Works Recommended)': total_works,
            '10 लाख तक के कार्य - संख्या (Under 10L Count)': under_10_cnt,
            '10 लाख तक के कार्य - कुल लागत लाख में (Under 10L Total Lakhs)': under_10_cost,
            '10 लाख से अधिक के कार्य - संख्या (Over 10L Count)': more_10_cnt,
            '10 लाख से अधिक के कार्य - कुल लागत लाख में (Over 10L Total Lakhs)': more_10_cost,
            'कुल आगणित लागत लाख में (Total Estimated Cost Lakhs)': total_cost,
            'कुल व्यय धनराशि लाख में (Total Amount Spent Lakhs)': total_spent,
            'पूर्ण कार्य संख्या (Completed Works Count)': completed_cnt,
            'प्रगति पर कार्य संख्या (In Progress Works Count)': in_prog_cnt,
            'स्वीकृत कार्य संख्या (Sanctioned Works Count)': sanctioned_cnt,
            'प्रक्रियाधीन कार्य संख्या (Proposed / Pending Count)': proposed_cnt,
            'औसत भौतिक प्रगति % (Average Physical Progress %)': avg_phys
        })
        
    df_summary = pd.DataFrame(summary_rows)
    print(f"Total MLA summary rows: {len(df_summary)}")
    return df_summary

def export_to_excel_and_csv(df_works, df_summary):
    excel_path = os.path.join(os.path.dirname(__file__), "MLA_LADS_UP_All_Works_and_Summary.xlsx")
    csv_works_path = os.path.join(os.path.dirname(__file__), "MLA_LADS_UP_All_Works.csv")
    csv_summary_path = os.path.join(os.path.dirname(__file__), "MLA_LADS_UP_Summary.csv")
    
    print(f"\n--- Exporting to CSV ---")
    df_works.to_csv(csv_works_path, index=False, encoding='utf-8-sig')
    df_summary.to_csv(csv_summary_path, index=False, encoding='utf-8-sig')
    print(f"Saved: {csv_works_path}")
    print(f"Saved: {csv_summary_path}")
    
    print(f"\n--- Exporting to Excel ({excel_path}) ---")
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name="MLA Summary", index=False)
        df_works.to_excel(writer, sheet_name="All Works Details", index=False)
    print(f"Excel file created successfully: {excel_path}")

def main():
    print("=== UP MLA LADS Scraper & Excel Report Generator ===")
    t0 = time.time()
    
    print("\nStep 1: Fetching member list (Vidhan Sabha & Vidhan Parishad)...")
    vs = fetch_members(1)
    vp = fetch_members(2)
    print(f"Vidhan Sabha MLAs: {len(vs)}")
    print(f"Vidhan Parishad MLCs: {len(vp)}")
    
    all_members = [(m, 1) for m in vs] + [(m, 2) for m in vp]
    total_members = len(all_members)
    print(f"Total Representatives to scrape: {total_members}")
    
    print("\nStep 2: Concurrently scraping all works data...")
    completed = 0
    total_works = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_mla_works, m, st): (m, st) for m, st in all_members}
        for future in as_completed(futures):
            m, st = futures[future]
            sid, name, st_id, rows, status = future.result()
            completed += 1
            total_works += rows
            if completed % 25 == 0 or completed == total_members:
                elapsed = time.time() - t0
                print(f"  [{completed}/{total_members}] Progress: {completed/total_members*100:.1f}% | Total works fetched: {total_works} | Time: {elapsed:.1f}s")
                
    scrape_time = time.time() - t0
    print(f"\nScraping finished in {scrape_time:.2f} seconds!")
    
    print("\nStep 3: Cleaning & Structuring Data...")
    df_works = process_raw_data(all_members)
    df_summary = create_summary_dataframe(df_works, all_members)
    
    print("\nStep 4: Writing Excel & CSV Files...")
    export_to_excel_and_csv(df_works, df_summary)
    
    total_time = time.time() - t0
    print(f"\n=== All operations completed successfully in {total_time:.2f} seconds! ===")

if __name__ == "__main__":
    main()
