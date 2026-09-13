"""Import the national district master.

Supported inputs:
  1) Government-directory-derived JSON with {"districts":[{state,stateCode,district,districtCode,...}]}
  2) Flat CSV with state_code,state_name,district_code,district_name

Existing app data is never deleted.
"""
import csv, sqlite3, re, sys, json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; DB=BASE/'database/kaushalpulse.db'
def norm(x): return re.sub(r'[^a-z0-9]+','-',str(x).lower()).strip('-')

def upsert(c, sc, sn, dc, dn):
    sr=c.execute('SELECT id FROM states WHERE code=? OR name=?',(sc,sn)).fetchone()
    if not sr:
        sid='state-'+norm(sn); c.execute('INSERT INTO states(id,name,code) VALUES(?,?,?)',(sid,sn,sc)); sr=(sid,)
    sid=sr[0]
    did=f'{sid}:{norm(dn)}'; c.execute('INSERT OR IGNORE INTO districts(id,state_id,name,lgd_code,status) VALUES(?,?,?,?,?)',(did,sid,dn,dc or None,'active'))
    c.execute('UPDATE districts SET state_id=?,name=?,lgd_code=COALESCE(?,lgd_code),status="active" WHERE id=?',(sid,dn,dc or None,did))
    c.execute('INSERT OR IGNORE INTO tenants(id,district_id,tenant_type,status) VALUES(?,?,"district","active")',(f't:{did}',did)); return did

if len(sys.argv)<2: raise SystemExit('Usage: python scripts/import_lgd_districts.py path/to/lgd.csv|districts.json')
p=Path(sys.argv[1]); c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON'); n=0
if p.suffix.lower()=='.json':
    payload=json.loads(p.read_text(encoding='utf-8'))
    rows=payload.get('districts',[]) if isinstance(payload,dict) else payload
    for row in rows:
        if not isinstance(row,dict): continue
        if row.get('state') and row.get('district'):
            upsert(c,str(row.get('stateCode','')).strip(),str(row['state']).strip(),str(row.get('districtCode','')).strip(),str(row['district']).strip()); n+=1
else:
    with p.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); cols={k.lower().strip():k for k in reader.fieldnames or []}
        required=['state_code','state_name','district_code','district_name']; missing=[x for x in required if x not in cols]
        if missing: raise SystemExit('Missing columns: '+', '.join(missing))
        for row in reader:
            upsert(c,str(row[cols['state_code']]).strip(),str(row[cols['state_name']]).strip(),str(row[cols['district_code']]).strip(),str(row[cols['district_name']]).strip()); n+=1
c.commit(); print(f'Imported/updated {n} district rows.')
