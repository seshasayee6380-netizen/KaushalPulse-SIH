import requests

BASE='http://127.0.0.1:8010'
s=requests.Session()
r=s.post(BASE+'/api/auth/demo-login',json={'demo_id':'DEMO-ADMIN-001'},timeout=10)
r.raise_for_status(); s.headers['X-Session-Token']=r.json()['token']
for ep in ['/api/district/admin-dashboard','/api/district/recruiters','/api/district/course-library','/api/district/guarantees','/api/district/feedback','/api/district/placements','/api/district/plan?target_year=2027']:
    x=s.get(BASE+ep,timeout=10); x.raise_for_status()
fb=s.get(BASE+'/api/district/feedback',timeout=10).json()
if fb:
    s.put(BASE+f"/api/district/feedback/{fb[0]['id']}/review",json={'status':'reviewed','admin_note':'Regression validation'},timeout=10).raise_for_status()
cs=s.get(BASE+'/api/district/guarantees',timeout=10).json()
if cs:
    c=cs[0]
    s.put(BASE+f"/api/district/guarantees/{c['id']}",json={'hired_slots':min(int(c['hired_slots']),int(c['committed_slots']))},timeout=10).raise_for_status()
plan=s.get(BASE+'/api/district/plan?target_year=2027',timeout=10).json()
s.post(BASE+'/api/district/plan/save',json=plan,timeout=10).raise_for_status()
print('DISTRICT ADMIN REGRESSION PASS')
