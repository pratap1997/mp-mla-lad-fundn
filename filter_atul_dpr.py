import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('raw_data/mla_1_240010268.json', encoding='utf-8') as f:
    data = json.load(f)

rows = data['Table_0']

# Discover exact cost key
cost_key = None
dpr_key = None
for k in rows[0].keys():
    if 'लागत' in k:
        cost_key = k
    if 'डीoपीoआरo' in k and 'प्रेषित' in k:
        dpr_key = k

print("Cost key:", repr(cost_key))
print("DPR key:", repr(dpr_key))

# Filter 9 <= cost <= 10 lakhs
hits = []
for r in rows:
    cost_raw = r.get(cost_key, None)
    try:
        c = float(cost_raw) if cost_raw is not None else 0.0
    except (ValueError, TypeError):
        c = 0.0

    if 9.0 <= c <= 10.0:
        dpr_val = r.get(dpr_key, '')
        hits.append({
            'work_id': r.get('कार्य आईoडीo'),
            'cost_lakhs': c,
            'desc': str(r.get('कार्य का विवरण', ''))[:80],
            'work_type': r.get('कार्य का प्रकार', ''),
            'district': r.get('जनपद', ''),
            'dpr_raw': str(dpr_val)
        })

print(f"\nTotal works between 9-10 Lakhs: {len(hits)}")
for h in hits:
    print(f"  ID={h['work_id']} | Cost={h['cost_lakhs']}L | {h['desc'][:50]}")
    print(f"    DPR raw: {h['dpr_raw'][:100]}")
