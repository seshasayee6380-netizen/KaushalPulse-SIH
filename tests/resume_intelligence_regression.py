import requests
BASE='http://127.0.0.1:8010'
r=requests.post(BASE+'/api/auth/demo-login',json={'demo_id':'DEMO-STUDENT-001'}); r.raise_for_status(); j=r.json()
h={'X-Session-Token':j['token'],'X-Tenant-ID':j['user']['tenant_id'],'X-Market-District-ID':j['user']['tenant_id']}
resume=b'Name: Demo Student\nTarget Role: Software Engineer\nSkills: Python, SQL, Cloud, Docker, Communication\nExperience: backend API development.'
r=requests.post(BASE+'/api/student/resume',headers=h,files={'file':('resume.txt',resume,'text/plain')}); assert r.status_code==200, r.text
rf=requests.get(BASE+'/api/student/resume-fitness',headers=h); assert rf.status_code==200, rf.text
d=rf.json(); assert d['has_resume']; assert d['resume_skills']; assert 'learned_skills' in d; assert 'skill_employer_demand' in d; assert 'job_matches' in d
print('RESUME INTELLIGENCE REGRESSION PASS')
