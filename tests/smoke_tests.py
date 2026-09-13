import requests
BASE='http://127.0.0.1:8010'

def ok(r):
    assert r.ok, (r.status_code, r.text)

def run():
    ok(requests.get(BASE+'/health'))
    login=requests.post(BASE+'/api/auth/demo-login',json={'demo_id':'DEMO-STUDENT-001'}); ok(login)
    j=login.json(); h={'X-Session-Token':j['token'],'X-Tenant-ID':j['user']['tenant_id'],'X-Market-District-ID':j['user']['tenant_id']}
    for path in ['/api/student/profile','/api/student/readiness','/api/student/gap','/api/student/alignment-hub','/api/student/market-jobs?limit=20','/api/mentors','/api/mentors/requests','/api/skill-alerts','/api/skill-alerts/actions']:
        ok(requests.get(BASE+path,headers=h))
    r=requests.post(BASE+'/api/student/path-navigator/generate',headers=h,json={'role_id':'software'}); ok(r); path=r.json(); assert path['path_id'] and path['steps']
    r=requests.post(BASE+f"/api/student/path-navigator/steps/{path['steps'][0]['id']}/complete",headers=h); ok(r); assert r.json()['progress_pct']>0
    print('all smoke tests passed')
if __name__=='__main__': run()
