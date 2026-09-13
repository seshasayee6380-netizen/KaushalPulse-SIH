"""End-to-end regression for the four core Employer workspace menus.
Run while backend is serving on http://127.0.0.1:8010.
"""
import requests, sys

BASE='http://127.0.0.1:8010'
s=requests.Session()

r=s.post(BASE+'/api/auth/demo-login',json={'demo_id':'DEMO-EMPLOYER-001'}); r.raise_for_status()
j=r.json(); h={'X-Session-Token':j['token'],'X-Tenant-ID':j['user']['tenant_id'],'Content-Type':'application/json'}

def get(path):
    r=s.get(BASE+path,headers=h); r.raise_for_status(); return r.json()
def post(path, body):
    r=s.post(BASE+path,headers=h,json=body); r.raise_for_status(); return r.json()
def put(path, body):
    r=s.put(BASE+path,headers=h,json=body); r.raise_for_status(); return r.json()

co=get('/api/employer/company')
roles=get('/api/roles')
skills=get('/api/skills')
role=next(x for x in roles if x['id']=='cnc-op')

# 1. Jobs & Hiring
job=post('/api/industry/jobs',{'company_id':co['id'],'role_id':role['id'],'title':'Employer Regression Job','openings':3,'salary_min':20000,'salary_max':32000,'location_text':co['district_name']})
assert job['status']=='created'
put('/api/employer/jobs/'+job['id'],{'status':'closed'})
put('/api/employer/jobs/'+job['id'],{'status':'open'})
assert any(x['id']==job['id'] for x in get('/api/employer/jobs')['jobs'])

# 2. Skill Requirements
sr=get('/api/employer/skill-requirements')
assert sr['skills'], 'No derived skill requirements returned'
sk=sr['skills'][0]
saved=post('/api/employer/skill-requirements',{'skill_id':sk['skill_id'],'importance':'Critical','proficiency_level':3,'notes':'Regression requirement'})
assert saved['status']=='saved'
updated=next(x for x in get('/api/employer/skill-requirements')['skills'] if x['skill_id']==sk['skill_id'])
assert updated['importance']=='Critical' and updated['proficiency_level']==3

# 3. Candidate Pool
cands=get('/api/employment/candidates')
assert cands, 'No employer-scoped candidate/job matches returned'
c=cands[0]
inv=post('/api/employment/invite',{'company_id':c['company_id'],'student_id':c['student_id'],'job_id':c['job_id']})
assert inv['status'] in {'invited','interviewed','offered','hired','joined'}
if not inv.get('existing'):
    for status in ('interviewed','offered','hired','joined'):
        put('/api/employment/invites/'+inv['id'],{'status':status})

# 4. Training Partnership
req=post('/api/employer/training-partnership',{'request_type':'Curriculum Update','skill_id':skills[0]['id'],'title':'Employer regression training request','details':'Add practical exposure for a required skill.'})
assert req['status']=='created'
assert any(x['id']==req['id'] for x in get('/api/employer/training-partnership')['requests'])

# Final reads
get('/api/employer/hiring-outcomes')
get('/api/employer/dashboard')

print('PASS: Jobs & Hiring')
print('PASS: Skill Requirements')
print('PASS: Candidate Pool')
print('PASS: Training Partnership')
print('PASS: Employer end-to-end regression')
