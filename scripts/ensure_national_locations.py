import sqlite3, json, re
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
DB=BASE/'database'/'kaushalpulse.db'
SRC=BASE/'data'/'national_locations.json'
def slug(v): return re.sub(r'[^a-z0-9]+','-',v.strip().lower()).strip('-')
conn=sqlite3.connect(DB); conn.row_factory=sqlite3.Row
with SRC.open(encoding='utf-8') as f: data=json.load(f)
count=0
for st in data:
    sname=st['state']; scode=(st.get('stateCode') or slug(sname)[:8]).upper()
    row=conn.execute('select id from states where name=? or code=? limit 1',(sname,scode)).fetchone()
    sid=row['id'] if row else slug(scode)
    conn.execute('insert or ignore into states(id,name,code) values(?,?,?)',(sid,sname,scode))
    for d in st.get('districts',[]):
        did=f'{sid}:{slug(d)}'
        conn.execute('insert or ignore into districts(id,state_id,name,lgd_code,status) values(?,?,?,?,?)',(did,sid,d,None,'active'))
        conn.execute('insert or ignore into tenants(id,district_id,tenant_type,status) values(?,? ,"district","active")',(f't:{did}',did))
        count += 1
conn.commit();
print('seeded/verified',count,'district rows')
print('states',conn.execute('select count(*) from states').fetchone()[0])
print('districts',conn.execute('select count(*) from districts').fetchone()[0])
conn.close()
