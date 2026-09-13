import requests

BASE='http://127.0.0.1:8010'

def login(demo_id):
    r=requests.post(BASE+'/api/auth/demo-login',json={'demo_id':demo_id},timeout=10)
    r.raise_for_status(); j=r.json();
    return j, {'X-Session-Token':j['token'],'X-Tenant-ID':j['user']['tenant_id']}

def main():
    assert requests.get(BASE+'/health',timeout=10).json()['version']=='8.0.0'
    for did in ['DEMO-STUDENT-001','DEMO-EMPLOYER-001','DEMO-TRAINER-001','DEMO-ADMIN-001']:
        j,h=login(did)
        assert j['token'] and j['user']['role']
        # Every account can browse market context without changing its write tenant.
        r=requests.post(BASE+'/api/locations/ensure',headers=h,json={'state':'Karnataka','state_code':'KA','district':'Bengaluru Urban','district_code':'TEST'},timeout=10)
        assert r.ok
        md=r.json()['district_id']; h['X-Market-District-ID']=md
        assert requests.get(BASE+'/api/market/summary',headers=h,timeout=10).ok
    print('PASS: role login + national market selection')

if __name__=='__main__': main()
