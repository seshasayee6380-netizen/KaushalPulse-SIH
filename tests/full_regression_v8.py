import requests, json, tempfile, sqlite3, importlib.util, sys
from pathlib import Path
BASE='http://127.0.0.1:8010'
ROOT=Path(__file__).resolve().parents[1]

def req(method,path,headers=None,**kwargs):
    r=requests.request(method,BASE+path,headers=headers or {},timeout=15,**kwargs)
    if not r.ok:
        raise AssertionError(f'{method} {path} -> {r.status_code}: {r.text[:500]}')
    return r

def login(demo):
    j=req('POST','/api/auth/demo-login',json={'demo_id':demo}).json()
    return j, {'X-Session-Token':j['token'],'X-Tenant-ID':j['user']['tenant_id']}

# health
h=req('GET','/health').json(); assert h['version']=='8.0.0'

# all roles login + explicit role separation + market browsing
users={}
for demo, role in [('DEMO-STUDENT-001','STUDENT'),('DEMO-EMPLOYER-001','EMPLOYER'),('DEMO-TRAINER-001','TRAINING_PROVIDER'),('DEMO-ADMIN-001','DSC_ADMIN')]:
    j, headers=login(demo); assert j['user']['role']==role; users[role]=(j,headers)

student, sh=users['STUDENT']
employer, eh=users['EMPLOYER']
trainer, th=users['TRAINING_PROVIDER']
admin, ah=users['DSC_ADMIN']

# Ensure a known secondary market exists and select it read-only
loc=req('POST','/api/locations/ensure',headers=sh,json={'state':'Karnataka','state_code':'KA','district':'Bengaluru Urban','district_code':'TEST-KA'}).json()
market=loc['district_id']; sh2={**sh,'X-Market-District-ID':market}
for path in ['/api/market/summary','/api/market/demand','/api/market/alignment','/api/market/course-alerts','/api/market/companies?page=1&page_size=20','/api/market/academy','/api/market/jobs?limit=10','/api/core/engine']:
    r=req('GET',path,headers=sh2).json(); assert isinstance(r,(dict,list))
# explicit chosen market changes engine district
eng=req('GET','/api/core/engine',headers=sh2).json(); assert eng['district']['district_name']=='Bengaluru Urban'

# student core workflow, incl external market job matching
for path in ['/api/student/profile','/api/student/gap','/api/student/readiness','/api/student/alignment-hub','/api/student/market-jobs?limit=10','/api/jobs/recommended?limit=10','/api/student/resume-fitness','/api/student/path-navigator','/api/mentors','/api/mentors/requests','/api/skill-alerts','/api/skill-alerts/actions']:
    req('GET',path,headers=sh)
external=req('GET','/api/jobs/recommended?limit=10',headers=sh2).json(); assert external['market']['district_name']=='Bengaluru Urban'; assert all('match' in x for x in external['items'])
# update profile and assessment
req('PUT','/api/student/profile',headers=sh,json={'name':student['user']['name'],'qualification':'B.Tech','target_role':'Software Engineer','target_company':'National Technology Employer'})
req('POST','/api/student/assessment',headers=sh,json={'skill_id':'docker','level':2,'source':'task_assessment'})
# path generate, step complete
path=req('POST','/api/student/path-navigator/generate',headers=sh,json={'role_id':'software','market_district_id':market}).json(); assert path['path_id'] and path['steps']; before=req('GET','/api/student/readiness',headers=sh).json()['score'];
req('POST',f"/api/student/path-navigator/steps/{path['steps'][0]['id']}/complete",headers=sh); after=req('GET','/api/student/readiness',headers=sh).json()['score']; assert after>=before
# resume upload + fitness
resume=b"Name: Demo Student\nSkills: Python, Java, SQL, Docker, AWS, Communication\nExperience: backend APIs\n"
r=req('POST','/api/student/resume',headers=sh,files={'file':('demo_resume.txt',resume,'text/plain')}).json(); assert r['status']=='processed'
rf=req('GET','/api/student/resume-fitness',headers=sh).json(); assert rf['has_resume']
# mentor/reskill
mentors=req('GET','/api/mentors',headers=sh).json();
if mentors: req('POST','/api/mentors/request',headers=sh,json={'mentor_id':mentors[0]['id'],'goal':'Weekly project guidance'})
alerts=req('GET','/api/skill-alerts',headers=sh).json();
if alerts: req('POST',f"/api/skill-alerts/{alerts[0]['skill_id']}/act",headers=sh)

# role-based security: student cannot write employer/admin endpoints
security_cases=[
 ('POST','/api/industry/companies',{'name':'Should Fail','sector':'IT','size':'MSME'}),
 ('POST','/api/industry/jobs',{'company_id':'nope','role_id':'software','title':'Should Fail','openings':1}),
 ('POST','/api/employer/feedback',{'company_id':'nope','rating':5,'missing_skills':[],'comment':'nope'}),
 ('POST','/api/district/plan/save',{'target_year':2027}),
 ('POST','/api/national/coverage/refresh',None),
]
for method,path,body in security_cases:
    r=requests.request(method,BASE+path,headers=sh,json=body,timeout=15)
    assert r.status_code==403,(path,r.status_code,r.text)
# trainer cannot employer writes; employer can create company/job/commitment/feedback
r=requests.post(BASE+'/api/industry/companies',headers=th,json={'name':'No','sector':'IT','size':'MSME'},timeout=15); assert r.status_code==403
company=req('POST','/api/industry/companies',headers=eh,json={'name':'National Demo Employer','sector':'Technology','size':'MSME','website':''}).json(); cid=company['id']
job=req('POST','/api/industry/jobs',headers=eh,json={'company_id':cid,'role_id':'software','title':'Backend Engineer','openings':12,'salary_min':450000,'salary_max':800000}).json(); jid=job['id']
commit=req('POST','/api/employment/commitments',headers=eh,json={'company_id':cid,'role_id':'software','committed_slots':10,'hired_slots':2,'valid_until':'2027-12-31','notes':'Demo employer commitment'}).json();
req('PUT',f"/api/employment/commitments/{commit['id']}",headers=eh,json={'hired_slots':3})
req('POST','/api/employer/feedback',headers=eh,json={'company_id':cid,'role_id':'software','rating':5,'missing_skills':['docker'],'comment':'Need stronger container skills'})
# Employer invite on same-tenant student if any candidate
cands=req('GET','/api/employment/candidates',headers=eh).json();
if cands: req('POST','/api/employment/invite',headers=eh,json={'company_id':cid,'student_id':cands[0]['student_id'],'job_id':jid})
# Admin district plan + save + evidence
plan=req('GET','/api/district/plan?target_year=2027',headers=ah).json(); assert plan['engine_version'].startswith('8.0')
req('POST','/api/district/plan/save',headers=ah,json=plan)
coverage=req('GET','/api/national/coverage').json(); assert coverage['states']>=36 and coverage['districts']>=127
eng_admin=req('GET','/api/core/engine',headers=ah).json(); assert eng_admin['provenance']
ev=req('GET','/api/evidence?limit=20',headers=ah).json(); assert isinstance(ev,list)

# national parser unit test against iaseth-style shape, without internet dependency
spec=importlib.util.spec_from_file_location('kp_main',str(ROOT/'backend'/'main.py')); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fixture={'districts':[{'state':'Test State','stateCode':'TS','districtCode':'D1','district':'One'},{'state':'Test State','stateCode':'TS','districtCode':'D2','district':'Two'}]}
assert mod.apply_national_location_payload(fixture)==2

print('FULL REGRESSION PASS: auth + RBAC + national market + core engine + student + employer + trainer + admin + evidence + parser')
