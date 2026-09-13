from fastapi import FastAPI, HTTPException, Header, Depends, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from pathlib import Path
from datetime import datetime, timezone
import sqlite3, json, math, uuid, re, shutil, secrets, hashlib, hmac, urllib.request, urllib.error
from typing import Optional

BASE = Path(__file__).resolve().parents[1]
DB = BASE / 'database' / 'kaushalpulse.db'
SCHEMA = BASE / 'database' / 'schema.sql'
RESUME_DIR = BASE / 'data' / 'resumes'
RESUME_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='KaushalPulse — Disha for your skills', version='8.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

LEVEL_SCORE = {1: 35, 2: 70, 3: 95}
LEVEL_NAME = {1: 'Beginner', 2: 'Intermediate', 3: 'Advanced'}


def now(): return datetime.now(timezone.utc).isoformat()

def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=30000')
    try: c.execute('PRAGMA journal_mode=WAL')
    except Exception: pass
    return c

def extract_text_from_upload(path: Path, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {'.txt', '.md', '.csv'}:
        return path.read_text(encoding='utf-8', errors='ignore')[:100000]
    if ext == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((page.extract_text() or '') for page in reader.pages)[:100000]
        except Exception as exc:
            raise HTTPException(400, f'Could not read PDF resume: {exc}')
    raise HTTPException(400, 'Upload a PDF, TXT, MD or CSV resume file.')

def extract_resume_skills(text: str):
    lower = text.lower()
    c=conn(); rows=c.execute('SELECT id,name FROM skills').fetchall(); c.close()
    aliases={'java':['java','spring boot','spring'],'cloud':['cloud','aws','azure','gcp','kubernetes'], 'docker':['docker','containerization','containers'],'python':['python'],'sql':['sql','mysql','postgresql'],'ai':['artificial intelligence','machine learning','tensorflow','pytorch','ai'],'cyber':['cybersecurity','soc','penetration testing','security'],'ev':['ev diagnostics','electric vehicle','ev service'],'bms':['battery management','bms'],'cnc':['cnc','cnc operator'],'plc':['plc','programmable logic controller'],'solar':['solar','photovoltaic','pv'],'welding':['welding'],'excel':['excel','spreadsheet'],'communication':['communication','presentation','stakeholder']}
    found=[]
    for r in rows:
        terms=aliases.get(r['id'], [r['name'].lower()])
        if any(term in lower for term in terms): found.append(dict(r))
    return found

def resume_fitness(t, market_tid=None):
    c=conn(); s=c.execute('SELECT id,target_role FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    if not s: c.close(); raise HTTPException(404,'Student profile not found')
    rr=c.execute('SELECT * FROM roles WHERE name=? OR id=?',(s['target_role'],s['target_role'])).fetchone() or c.execute('SELECT * FROM roles ORDER BY id LIMIT 1').fetchone()
    latest=c.execute('SELECT * FROM student_resumes WHERE tenant_id=? AND student_id=? ORDER BY id DESC LIMIT 1',(t['id'],s['id'])).fetchone()
    if not latest:
        c.close(); return {'has_resume':False,'score':0,'target_role':rr['name'],'matched_skills':[],'missing_skills':[],'next_skill':None,'projected_after_next_skill':0,'local_skill_demand':[],'learned_skills':[],'resume_skills':[],'skill_employer_demand':[],'job_matches':[],'message':'Upload your resume to calculate job fitness.'}
    req=c.execute('SELECT sk.id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=?',(rr['id'],)).fetchall()
    extracted=set(json.loads(latest['extracted_skills']));
    # Rehydrate the extracted skill IDs into stable skill records for the dashboard.
    extracted_rows=c.execute('SELECT id,name FROM skills WHERE id IN (%s) ORDER BY name' % ','.join('?'*len(extracted)), tuple(extracted)).fetchall() if extracted else []
    found=[dict(x) for x in extracted_rows]
    gaps=[dict(x) for x in req if x['id'] not in extracted]; matched=[dict(x) for x in req if x['id'] in extracted]
    den=sum(x['weight'] for x in req) or 1
    score=round(sum(x['weight'] for x in matched)/den*100) if req else 0
    # Show the effect of the next missing skill using only the stored role weights.
    next_skill = gaps[0]['name'] if gaps else None
    projected_after_next = score
    if gaps and req:
        projected_after_next = round(min(100, score + (gaps[0]['weight']/den*100)))
    demand_tid=market_tid or t['id']
    snap=core_engine_snapshot(demand_tid, s['id'] if demand_tid==t['id'] else None)
    demand_skill_rows=[x for x in snap.get('skill_demand',[]) if x.get('openings',0)>0]
    # Verified/learned skills are kept separately from skills merely detected in a resume.
    learned_rows=c.execute('''SELECT sk.id,sk.name,ss.level,ss.score,ss.source,ss.updated_at
                              FROM student_skills ss JOIN skills sk ON sk.id=ss.skill_id
                              WHERE ss.student_id=? ORDER BY ss.score DESC, sk.name''',(s['id'],)).fetchall()
    learned_skills=[dict(x) for x in learned_rows]
    # For every skill detected in the resume, show which local employers currently need it.
    employer_demand=[]
    skill_ids=sorted({x['id'] for x in found})
    for sid in skill_ids:
        companies=c.execute('''SELECT sk.id skill_id,sk.name skill_name,co.id company_id,co.name company_name,
                                      j.id job_id,j.title job_title,j.openings,j.location_text
                               FROM jobs j JOIN companies co ON co.id=j.company_id
                               JOIN role_skills rs ON rs.role_id=j.role_id
                               JOIN skills sk ON sk.id=rs.skill_id
                               WHERE j.tenant_id=? AND j.status='open' AND rs.skill_id=?
                               ORDER BY j.openings DESC,co.name,j.title''',(demand_tid,sid)).fetchall()
        employer_demand.append({'skill_id':sid,'skill_name':next((x['name'] for x in found if x['id']==sid),sid),'employers':[dict(x) for x in companies]})
    best=snap.get('job_fit',[]) if demand_tid==t['id'] else []
    if not best:
        jobrows=c.execute('SELECT j.id,j.title,co.name company_name,j.openings,r.id role_id FROM jobs j JOIN companies co ON co.id=j.company_id JOIN roles r ON r.id=j.role_id WHERE j.tenant_id=? AND j.status="open"',(demand_tid,)).fetchall()
        for j in jobrows:
            rs=c.execute('SELECT skill_id,weight,required_level FROM role_skills WHERE role_id=?',(j['role_id'],)).fetchall(); den=sum(float(x['weight']) for x in rs) or 1; num=sum(float(x['weight']) for x in rs if x['skill_id'] in extracted)
            best.append({**dict(j),'match':round(num/den*100),'missing_skill_ids':[x['skill_id'] for x in rs if x['skill_id'] not in extracted]})
    c.close(); return {'has_resume':True,'score':score,'target_role':rr['name'],'matched_skills':matched,'missing_skills':gaps,'next_skill':next_skill,'projected_after_next_skill':projected_after_next,'local_skill_demand':demand_skill_rows[:12],'learned_skills':learned_skills,'resume_skills':found,'skill_employer_demand':employer_demand,'job_matches':sorted(best,key=lambda x:(x.get('match',0),x.get('openings',0)),reverse=True)[:20],'message':'Resume fitness is calculated from extracted skills against the target role and the selected market; the same core engine supplies the local demand and job-fit evidence. Resume-detected skills are shown separately from verified skills learned through your training/assessment history.','engine_version':ENGINE_VERSION,'provenance':snap['provenance']}

def ensure_feature_seed(c):
    for tid_row in c.execute('SELECT id FROM tenants').fetchall():
        tid=tid_row['id']
        companies=c.execute('SELECT id FROM companies WHERE tenant_id=? ORDER BY id',(tid,)).fetchall()
        jobs=c.execute('SELECT j.role_id FROM jobs j WHERE j.tenant_id=? ORDER BY j.id',(tid,)).fetchall()
        if companies and jobs:
            cid=companies[0]['id']; rid=jobs[0]['role_id']
            c.execute('INSERT OR IGNORE INTO employer_commitments(id,tenant_id,company_id,role_id,committed_slots,hired_slots,valid_until,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(f'commit-{tid}',tid,cid,rid,25,8,'2027-03-31','active','Employer commitment entered into the district board; hiring remains subject to employer verification.',now()))
        mentors=[('Ananya Rao','Senior Software Engineer','Industry Mentor Network',8,'python,cloud,sql,communication',2,'Weekly project, interview and workplace guidance.'),('Vikram Kumar','EV Systems Engineer','EV Mobility Network',7,'ev,bms,communication',2,'EV diagnostics and BMS guidance with practical checkpoints.')]
        for idx,(nm,title,co,yrs,skills_txt,slots,bio) in enumerate(mentors,1):
            mid=f'mentor-{tid}-{idx}'
            c.execute('INSERT OR IGNORE INTO mentors(id,tenant_id,name,job_title,company,years_experience,skills,available_slots,bio,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,tid,nm,title,co,yrs,skills_txt,slots,bio,now()))
        providers=c.execute('SELECT id FROM training_providers WHERE tenant_id=?',(tid,)).fetchall()
        for prow in providers:
            pid=prow['id']
            trainer_seed=[('Arun Kumar','Industrial Automation','PLC, SCADA, Electrical Troubleshooting',8,'Available'),('Meena Das','Renewable Energy','Solar PV, IoT, Safety',5,'Available'),('Ravi Menon','Software Engineering','Python, SQL, Cloud',6,'Limited')]
            for n,(nm,spec,skills_txt,yrs,av) in enumerate(trainer_seed,1):
                xid=f'provider-trainer-{pid}-{n}'
                c.execute('INSERT OR IGNORE INTO provider_trainers(id,tenant_id,provider_id,name,specialization,skills,experience_years,availability,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(xid,tid,pid,nm,spec,skills_txt,yrs,av,'Active',now(),now()))
            equipment_seed=[('PLC Training Kit',12,7,88),('SCADA Workstation',8,5,91),('Solar Training Kit',10,9,72)]
            for n,(nm,req,avail,util) in enumerate(equipment_seed,1):
                xid=f'provider-equipment-{pid}-{n}'; status='Shortage' if req>avail else ('High utilization' if util>=85 else 'Adequate')
                c.execute('INSERT OR IGNORE INTO provider_equipment(id,tenant_id,provider_id,name,required_qty,available_qty,utilization_pct,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(xid,tid,pid,nm,req,avail,util,status,now(),now()))
            first_course=c.execute('SELECT id FROM courses WHERE tenant_id=? AND provider_id=? ORDER BY name LIMIT 1',(tid,pid)).fetchone()
            if first_course:
                c.execute('INSERT OR IGNORE INTO provider_placements(id,tenant_id,provider_id,course_id,employer_name,students_placed,openings,placement_date,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('provider-placement-'+pid,tid,pid,first_course['id'],'Apex Manufacturing',42,50,'2026-09-01','Verified','Placement outcome seeded for prototype demo.',now(),now()))
        for sk in c.execute('SELECT id FROM skills').fetchall():
            cur_jobs,cur_open=c.execute('SELECT COUNT(DISTINCT j.id),COALESCE(SUM(j.openings),0) FROM jobs j JOIN role_skills rs ON rs.role_id=j.role_id WHERE j.tenant_id=? AND j.status="open" AND rs.skill_id=?',(tid,sk['id'])).fetchone()
            prev_open=max(int(cur_open*0.7),1) if cur_open else 0
            c.execute('INSERT OR REPLACE INTO skill_demand_history(tenant_id,skill_id,period_label,job_count,openings,created_at) VALUES(?,?,?,?,?,?)',(tid,sk['id'],'previous_quarter',max(cur_jobs-1,0),prev_open,now()))
            c.execute('INSERT OR REPLACE INTO skill_demand_history(tenant_id,skill_id,period_label,job_count,openings,created_at) VALUES(?,?,?,?,?,?)',(tid,sk['id'],'current_quarter',cur_jobs,cur_open,now()))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    return salt.hex() + '$' + dk.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split('$', 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
        return hmac.compare_digest(dk.hex(), digest_hex)
    except Exception:
        return False

def ensure_auth_columns(c):
    cols = {r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
    if 'password_hash' not in cols: c.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
    if 'credential_id' not in cols: c.execute('ALTER TABLE users ADD COLUMN credential_id TEXT')
    if 'organization_id' not in cols: c.execute('ALTER TABLE users ADD COLUMN organization_id TEXT')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_credential ON users(credential_id) WHERE credential_id IS NOT NULL')
    c.execute("CREATE TABLE IF NOT EXISTS auth_sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)")
    c.execute('CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)')
    c.execute('CREATE TABLE IF NOT EXISTS demo_accounts (demo_id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE, label TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_demo_accounts_user ON demo_accounts(user_id)')

def ensure_auth_seed(c):
    # Real local accounts used to exercise every role/workspace.
    # Students use email + password; non-student roles also require their role credential.
    accounts = [
      # Students
      ('usr-student-demo','t:tn:salem','Ritkl Student','student.demo@kaushalpulse.local','STUDENT',None,None,'student123'),
      ('usr-student-py','t:py:puducherry','Anu Student','anu.student@example.com','STUDENT',None,None,'student123'),
      ('usr-student-coi','t:tn:coimbatore','Kiran Student','kiran.student@example.com','STUDENT',None,None,'student123'),
      # Employers
      ('usr-employer-demo','t:tn:salem','Employer Demo User','employer.demo@kaushalpulse.local','EMPLOYER','EMP-DEMO-001','cmp-salem-1','employer123'),
      ('usr-employer-py','t:py:puducherry','Puducherry Employer User','employer.puducherry@example.com','EMPLOYER','EMP-PY-001','cmp-py-1','employer123'),
      ('usr-employer-coi','t:tn:coimbatore','Coimbatore Employer User','employer.coimbatore@example.com','EMPLOYER','EMP-COI-001','cmp-coimbatore-1','employer123'),
      # Training providers
      ('usr-provider-demo','t:tn:salem','Training Provider Demo','trainer.demo@kaushalpulse.local','TRAINING_PROVIDER','TRN-DEMO-001','prov-salem-iti','trainer123'),
      ('usr-provider-coi','t:tn:coimbatore','Coimbatore Training Provider','trainer.coimbatore@example.com','TRAINING_PROVIDER','TRN-COI-001','prov-coi-iti','trainer123'),
      # District administrators
      ('usr-admin-demo','t:tn:salem','District Admin Demo','dsc.demo@kaushalpulse.local','DSC_ADMIN','DSC-DEMO-001',None,'admin123'),
      ('usr-admin-py','t:py:puducherry','Puducherry DSC Administrator','dsc.puducherry@example.com','DSC_ADMIN','DSC-PY-001',None,'admin123'),
      ('usr-admin-coi','t:tn:coimbatore','Coimbatore DSC Administrator','dsc.coimbatore@example.com','DSC_ADMIN','DSC-COI-001',None,'admin123'),
    ]
    for uid,tid,nm,email,role,cred,org,pwd in accounts:
        ph=hash_password(pwd)
        c.execute('INSERT OR IGNORE INTO users(id,tenant_id,name,email,role,password_hash,credential_id,organization_id) VALUES(?,?,?,?,?,?,?,?)',(uid,tid,nm,email,role,ph,cred,org))
        c.execute('UPDATE users SET tenant_id=?,name=?,role=?,password_hash=?,credential_id=?,organization_id=? WHERE id=?',(tid,nm,role,ph,cred,org,uid))
    c.execute('DELETE FROM demo_accounts')
    demo_rows = [
      ('DEMO-STUDENT-001','usr-student-demo','Student — National Learner'),
      ('DEMO-EMPLOYER-001','usr-employer-demo','Employer — National Hiring Workspace'),
      ('DEMO-TRAINER-001','usr-provider-demo','Training Provider — National Centre'),
      ('DEMO-ADMIN-001','usr-admin-demo','District Admin — National DSC Workspace'),
    ]
    for did,uid,label in demo_rows:
        c.execute('INSERT OR IGNORE INTO demo_accounts(demo_id,user_id,label) VALUES(?,?,?)',(did,uid,label))
        c.execute('UPDATE demo_accounts SET user_id=?,label=? WHERE demo_id=?',(uid,label,did))

def ensure_workflow_tables(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS learning_paths (
      id TEXT PRIMARY KEY,
      tenant_id TEXT NOT NULL,
      student_id TEXT NOT NULL,
      role_id TEXT NOT NULL,
      title TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id),
      FOREIGN KEY(student_id) REFERENCES students(id),
      FOREIGN KEY(role_id) REFERENCES roles(id)
    );
    CREATE INDEX IF NOT EXISTS idx_learning_path_tenant_student ON learning_paths(tenant_id,student_id);
    CREATE TABLE IF NOT EXISTS learning_path_steps (
      id TEXT PRIMARY KEY,
      path_id TEXT NOT NULL,
      step_no INTEGER NOT NULL,
      week_start INTEGER NOT NULL,
      week_end INTEGER NOT NULL,
      skill_id TEXT NOT NULL,
      target_level INTEGER NOT NULL,
      course_id TEXT,
      project TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      completed_at TEXT,
      FOREIGN KEY(path_id) REFERENCES learning_paths(id) ON DELETE CASCADE,
      FOREIGN KEY(skill_id) REFERENCES skills(id),
      FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    CREATE INDEX IF NOT EXISTS idx_learning_steps_path ON learning_path_steps(path_id,step_no);
    CREATE TABLE IF NOT EXISTS reskilling_actions (
      id TEXT PRIMARY KEY,
      tenant_id TEXT NOT NULL,
      student_id TEXT NOT NULL,
      skill_id TEXT NOT NULL,
      action TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'planned',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id),
      FOREIGN KEY(student_id) REFERENCES students(id),
      FOREIGN KEY(skill_id) REFERENCES skills(id)
    );
    CREATE INDEX IF NOT EXISTS idx_reskill_tenant_student ON reskilling_actions(tenant_id,student_id);
    CREATE TABLE IF NOT EXISTS provider_trainers (
      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, name TEXT NOT NULL,
      specialization TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '', experience_years INTEGER NOT NULL DEFAULT 0,
      availability TEXT NOT NULL DEFAULT 'Available', status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id)
    );
    CREATE INDEX IF NOT EXISTS idx_provider_trainers ON provider_trainers(tenant_id,provider_id);
    CREATE TABLE IF NOT EXISTS provider_equipment (
      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, name TEXT NOT NULL, required_qty INTEGER NOT NULL DEFAULT 0,
      available_qty INTEGER NOT NULL DEFAULT 0, utilization_pct INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Adequate', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id)
    );
    CREATE INDEX IF NOT EXISTS idx_provider_equipment ON provider_equipment(tenant_id,provider_id);
    CREATE TABLE IF NOT EXISTS provider_placements (
      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, course_id TEXT NOT NULL, employer_name TEXT NOT NULL,
      students_placed INTEGER NOT NULL DEFAULT 0, openings INTEGER NOT NULL DEFAULT 0, placement_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Verified', notes TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id), FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    CREATE INDEX IF NOT EXISTS idx_provider_placements ON provider_placements(tenant_id,provider_id);
    CREATE TABLE IF NOT EXISTS employer_training_requests (
      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, company_id TEXT NOT NULL, request_type TEXT NOT NULL, skill_id TEXT, title TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(company_id) REFERENCES companies(id), FOREIGN KEY(skill_id) REFERENCES skills(id)
    );
    CREATE INDEX IF NOT EXISTS idx_employer_training_requests ON employer_training_requests(tenant_id,company_id,status);
    CREATE TABLE IF NOT EXISTS employer_skill_requirements (
      company_id TEXT NOT NULL, tenant_id TEXT NOT NULL, skill_id TEXT NOT NULL, importance TEXT NOT NULL DEFAULT 'High',
      proficiency_level INTEGER NOT NULL DEFAULT 2 CHECK(proficiency_level BETWEEN 1 AND 3), notes TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL, PRIMARY KEY(company_id,skill_id),
      FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(skill_id) REFERENCES skills(id)
    );
    CREATE INDEX IF NOT EXISTS idx_employer_skill_requirements ON employer_skill_requirements(tenant_id,company_id);
    CREATE TABLE IF NOT EXISTS employer_jobs_meta (
      job_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, requirements_note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
      FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE, FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    );
    CREATE TABLE IF NOT EXISTS feedback_reviews (
      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, feedback_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'new',
      admin_note TEXT NOT NULL DEFAULT '', reviewed_at TEXT, created_at TEXT NOT NULL,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(feedback_id) REFERENCES employer_feedback(id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_review_unique ON feedback_reviews(tenant_id,feedback_id);
    """)

def init_db():
    c = conn(); c.executescript(SCHEMA.read_text(encoding='utf-8')); ensure_auth_columns(c); ensure_workflow_tables(c); c.commit();
    seed(c)
    ensure_feature_seed(c)
    ensure_auth_seed(c)
    c.commit(); c.close()


def seed(c):
    # State/UT catalogue (all 36 administrative entries); district list is extensible through import.
    states = [
        ('an','Andaman and Nicobar Islands','35'),('ap','Andhra Pradesh','28'),('ar','Arunachal Pradesh','12'),('as','Assam','18'),('br','Bihar','10'),
        ('ch','Chandigarh','04'),('ct','Chhattisgarh','22'),('dn','Dadra and Nagar Haveli and Daman and Diu','26'),('dl','Delhi','07'),('ga','Goa','30'),
        ('gj','Gujarat','24'),('hr','Haryana','06'),('hp','Himachal Pradesh','02'),('jk','Jammu and Kashmir','01'),('jh','Jharkhand','20'),('ka','Karnataka','29'),
        ('kl','Kerala','32'),('la','Ladakh','38'),('ld','Lakshadweep','31'),('mp','Madhya Pradesh','23'),('mh','Maharashtra','27'),('mn','Manipur','14'),
        ('ml','Meghalaya','17'),('mz','Mizoram','15'),('nl','Nagaland','13'),('od','Odisha','21'),('py','Puducherry','34'),('pb','Punjab','03'),
        ('rj','Rajasthan','08'),('sk','Sikkim','11'),('tn','Tamil Nadu','33'),('tg','Telangana','36'),('tr','Tripura','16'),('up','Uttar Pradesh','09'),
        ('uk','Uttarakhand','05'),('wb','West Bengal','19')
    ]
    c.executemany('INSERT OR IGNORE INTO states(id,name,code) VALUES(?,?,?)', states)

    # Representative real districts for ready-to-run use; import script can load full LGD directory.
    reps = {
        'tn': ['Ariyalur','Chengalpattu','Chennai','Coimbatore','Cuddalore','Dharmapuri','Dindigul','Erode','Kallakurichi','Kancheepuram','Karur','Krishnagiri','Madurai','Mayiladuthurai','Nagapattinam','Namakkal','Perambalur','Pudukkottai','Ramanathapuram','Ranipet','Salem','Sivaganga','Tenkasi','Thanjavur','The Nilgiris','Theni','Thoothukudi','Tiruchirappalli','Tirunelveli','Tirupathur','Tiruppur','Tiruvallur','Tiruvarur','Vellore','Viluppuram','Virudhunagar'],
        'ka': ['Bengaluru Urban','Bengaluru Rural','Mysuru','Mangaluru','Belagavi','Dharwad','Shivamogga','Tumakuru','Hassan','Ballari','Hubballi'],
        'mh': ['Mumbai City','Mumbai Suburban','Pune','Nagpur','Nashik','Thane','Aurangabad','Kolhapur','Satara','Solapur'],
        'up': ['Agra','Aligarh','Ayodhya','Bareilly','Ghaziabad','Gorakhpur','Kanpur Nagar','Lucknow','Meerut','Noida'],
        'dl': ['Central Delhi','East Delhi','New Delhi','North Delhi','North East Delhi','North West Delhi','Shahdara','South Delhi','South East Delhi','South West Delhi','West Delhi'],
        'py': ['Puducherry','Karaikal','Mahe','Yanam'],
        'kl': ['Thiruvananthapuram','Kollam','Alappuzha','Pathanamthitta','Kottayam','Idukki','Ernakulam','Thrissur','Palakkad','Malappuram','Kozhikode','Wayanad','Kannur','Kasaragod'],
        'ap': ['Anakapalli','Anantapur','Chittoor','East Godavari','Kakinada','Krishna','NTR','Nellore','Prakasam','Srikakulam','Tirupati','Visakhapatnam','Vizianagaram','West Godavari'],
        'rj': ['Ajmer','Alwar','Bharatpur','Bikaner','Jaipur','Jaisalmer','Jodhpur','Kota','Udaipur'],
        'gj': ['Ahmedabad','Gandhinagar','Surat','Vadodara','Rajkot','Bhavnagar','Kutch','Mehsana'],
    }
    for sid, names in reps.items():
        for name in names:
            did = f'{sid}:{re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")}'
            c.execute('INSERT OR IGNORE INTO districts(id,state_id,name,lgd_code) VALUES(?,?,?,?)',(did,sid,name,None))
    # Tenant for every seeded district
    for r in c.execute('SELECT id FROM districts').fetchall():
        did = r['id']; c.execute('INSERT OR IGNORE INTO tenants(id,district_id) VALUES(?,?)',(f't:{did}',did))

    skills=[
        ('java','Java','Technical'),('cloud','Cloud','Technical'),('python','Python','Technical'),('sql','SQL','Technical'),('ai','AI & ML','Technical'),
        ('cyber','Cybersecurity','Technical'),('docker','Docker','Technical'),('ev','EV Diagnostics','Domain'),('bms','Battery Management Systems','Domain'),('cnc','CNC Operations','Domain'),
        ('plc','PLC & Automation','Domain'),('solar','Solar Installation','Domain'),('welding','Welding','Domain'),('excel','Excel & Data Operations','Digital'),('communication','Communication','Soft Skill')]
    c.executemany('INSERT OR IGNORE INTO skills(id,name,category) VALUES(?,?,?)',skills)
    roles=[('software','Software Engineer','IT & Services'),('frontend','Frontend Developer','IT & Services'),('qa','QA Automation Engineer','IT & Services'),('ai-engineer','AI Engineer','IT & Services'),('ev-tech','EV Service Technician','Automotive'),('cnc-op','CNC Operator','Manufacturing'),('solar-tech','Solar Technician','Energy'),('cyber-analyst','Cybersecurity Analyst','IT & Services')]
    c.executemany('INSERT OR IGNORE INTO roles(id,name,sector) VALUES(?,?,?)',roles)
    rolemap={
      'frontend':[('java',1,.4),('sql',1,.4),('communication',2,.5)],
      'qa':[('java',1,.6),('sql',2,.7),('communication',2,.4)],
      'software':[('java',2,1),('cloud',2,1),('docker',2,.8),('sql',2,1),('communication',2,.5)],
      'ai-engineer':[('python',2,1),('ai',2,1),('cloud',2,.7),('sql',2,.5)],
      'ev-tech':[('ev',2,1),('bms',2,1),('communication',2,.4)],
      'cnc-op':[('cnc',2,1),('plc',2,.8),('welding',1,.5)],
      'solar-tech':[('solar',2,1),('plc',1,.5),('communication',2,.4)],
      'cyber-analyst':[('python',2,.8),('cyber',2,1),('cloud',2,.7),('sql',2,.5)]}
    for rid, pairs in rolemap.items():
        for sid, lvl, wt in pairs: c.execute('INSERT OR IGNORE INTO role_skills(role_id,skill_id,required_level,weight) VALUES(?,?,?,?)',(rid,sid,lvl,wt))

    default_d = c.execute('SELECT id FROM districts WHERE state_id="tn" AND name="Salem"').fetchone()['id']
    default_t = f't:{default_d}'
    c.execute('INSERT OR IGNORE INTO users(id,tenant_id,name,email,role) VALUES(?,?,?,?,?)',('u-student',default_t,'Ritkl','ritkl@example.com','student'))
    c.execute('INSERT OR IGNORE INTO students(id,tenant_id,user_id,name,qualification,target_role,target_company,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',('stu-001',default_t,'u-student','Ritkl','B.E. Computer Science','Software Engineer','Tata Technologies',now(),now()))
    for sid,lvl in [('java',2),('cloud',1),('python',1),('sql',2),('communication',2),('ai',1)]:
        c.execute('INSERT OR IGNORE INTO student_skills(student_id,skill_id,level,score,source,updated_at) VALUES(?,?,?,?,?,?)',('stu-001',sid,lvl,LEVEL_SCORE[lvl],'self_assessment',now()))
    # seeded companies/jobs in multiple districts for real cross-district behavior
    companies=[
      ('cmp-salem-1','tn:salem','Salem Steel Works','Manufacturing','Large'),('cmp-salem-2','tn:salem','Kaveri Auto Components','Automotive','MSME'),('cmp-salem-3','tn:salem','GreenGrid Solar','Energy','MSME'),
      ('cmp-coimbatore-1','tn:coimbatore','Coimbatore Precision','Manufacturing','Large'),('cmp-coimbatore-2','tn:coimbatore','Kovai Cloud Labs','IT & Services','MSME'),('cmp-coimbatore-3','tn:coimbatore','SouthGrid Energy','Energy','MSME'),
      ('cmp-pune-1','mh:pune','Pune Automation Systems','Manufacturing','Large'),('cmp-pune-2','mh:pune','Pune AI Works','IT & Services','MSME'),
      ('cmp-bengaluru-1','ka:bengaluru-urban','Bengaluru Cloud Systems','IT & Services','Large'),('cmp-bengaluru-2','ka:bengaluru-urban','Karnataka EV Mobility','Automotive','Large'),
      ('cmp-py-1','py:puducherry','Puducherry Electronics','Electronics','MSME'),('cmp-py-2','py:puducherry','AuroTech Manufacturing','Manufacturing','MSME'),('cmp-py-3','py:puducherry','Puducherry Digital Works','IT & Services','MSME'),('cmp-py-4','py:puducherry','Coastal Solar Systems','Energy','MSME')]
    for cid,did,nm,sec,size in companies:
        tid=f't:{did}'; c.execute('INSERT OR IGNORE INTO companies(id,tenant_id,name,sector,size,created_at) VALUES(?,?,?,?,?,?)',(cid,tid,nm,sec,size,now()))
    jobseed=[('j1','cmp-salem-1','cnc-op','CNC Operator',12,22000,38000),('j2','cmp-salem-2','ev-tech','EV Service Technician',18,22000,42000),('j3','cmp-salem-3','solar-tech','Solar Technician',10,20000,36000),('j4','cmp-coimbatore-2','software','Software Engineer',20,45000,85000),('j5','cmp-coimbatore-3','solar-tech','Solar Technician',16,22000,38000),('j6','cmp-pune-2','ai-engineer','AI Engineer',15,65000,120000),('j7','cmp-pune-1','cnc-op','CNC Operator',22,24000,42000),('j8','cmp-bengaluru-1','software','Software Engineer',30,60000,140000),('j9','cmp-bengaluru-2','ev-tech','EV Service Technician',25,26000,48000),('j10','cmp-py-1','software','Software Engineer',1,40000,75000),('j11','cmp-py-2','cnc-op','CNC Operator',1,24000,42000),('j12','cmp-py-2','ev-tech','EV Service Technician',1,26000,48000),('j13','cmp-py-3','ai-engineer','AI Engineer',1,55000,95000),('j14','cmp-py-3','cyber-analyst','Cybersecurity Analyst',1,45000,80000),('j15','cmp-py-4','solar-tech','Solar Technician',1,22000,38000),('j16','cmp-py-1','software','Frontend Developer',1,38000,70000),('j17','cmp-py-1','software','QA Automation Engineer',1,35000,65000)]
    for jid,cid,rid,title,openings,smin,smax in jobseed:
        did=c.execute('SELECT tenant_id FROM companies WHERE id=?',(cid,)).fetchone()['tenant_id']
        c.execute('INSERT OR IGNORE INTO jobs(id,tenant_id,company_id,role_id,title,openings,location_text,salary_min,salary_max,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,did,cid,rid,title,openings,None,smin,smax,now()))
    # training providers and courses for seeded districts
    courses=[
      ('prov-salem-iti','tn:salem','Government ITI Salem','ITI'),('prov-salem-pvt','tn:salem','Salem Skill Academy','Private'),('prov-coi-iti','tn:coimbatore','Government ITI Coimbatore','ITI'),('prov-pune-poly','mh:pune','Pune Industrial Training Hub','Polytechnic')]
    for pid,did,nm,pt in courses: c.execute('INSERT OR IGNORE INTO training_providers(id,tenant_id,name,provider_type,created_at) VALUES(?,?,?,?,?)',(pid,f't:{did}',nm,pt,now()))
    course_data=[('course-salem-cnc','tn:salem','prov-salem-iti','CNC Operator',16,120,['cnc','plc']),('course-salem-ev','tn:salem','prov-salem-pvt','EV Technician',16,80,['ev','bms']),('course-salem-solar','tn:salem','prov-salem-pvt','Solar Technician',12,60,['solar']),('course-coi-software','tn:coimbatore','prov-coi-iti','Software Foundations',20,180,['java','sql','cloud']),('course-pune-ai','mh:pune','prov-pune-poly','AI Engineering',24,150,['python','ai','cloud','sql'])]
    for cid,did,pid,nm,dur,seats,ss in course_data:
        c.execute('INSERT OR IGNORE INTO courses(id,tenant_id,provider_id,name,duration_weeks,seats,created_at) VALUES(?,?,?,?,?,?,?)',(cid,f't:{did}',pid,nm,dur,seats,now()))
        for sid in ss: c.execute('INSERT OR IGNORE INTO course_skills(course_id,skill_id,taught_level) VALUES(?,?,?)',(cid,sid,2))
    c.commit()

init_db()



LOCATION_SOURCE_URL = 'https://raw.githubusercontent.com/iaseth/data-for-india/master/data/readable/districts.json'
LOCATION_SOURCE_NAME = 'India district reference — sourced from a public dataset whose README traces the district data to the Government of India directory'
LOCATION_SOURCE_OFFICIAL = 'https://igod.gov.in/sg/district/states'
ENGINE_VERSION = '8.0-national-unified-engine'
BUNDLED_LOCATION_FILE = BASE / 'data' / 'national_locations.json'

def slugify_location(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.strip().lower()).strip('-')

def ensure_location_tenant(c, state_name: str, state_code: str, district_name: str, district_code: str=''):
    existing = c.execute('SELECT id FROM states WHERE name=? OR code=? LIMIT 1',(state_name,state_code)).fetchone() if state_name or state_code else None
    state_id = existing['id'] if existing else slugify_location(state_code or state_name)
    c.execute('INSERT OR IGNORE INTO states(id,name,code) VALUES(?,?,?)',(state_id,state_name,state_code or state_id.upper()))
    c.execute('UPDATE states SET name=?, code=? WHERE id=?',(state_name,state_code or c.execute('SELECT code FROM states WHERE id=?',(state_id,)).fetchone()['code'],state_id))
    district_id = f'{state_id}:{slugify_location(district_name)}'
    c.execute('INSERT OR IGNORE INTO districts(id,state_id,name,lgd_code,status) VALUES(?,?,?,?,?)',(district_id,state_id,district_name,district_code or None,'active'))
    c.execute('UPDATE districts SET state_id=?,name=?,lgd_code=COALESCE(?,lgd_code),status="active" WHERE id=?',(state_id,district_name,district_code or None,district_id))
    tenant_id=f't:{district_id}'
    c.execute('INSERT OR IGNORE INTO tenants(id,district_id,tenant_type,status) VALUES(?,?,"district","active")',(tenant_id,district_id))
    return district_id, tenant_id

def market_tenant_id(market_district_id: Optional[str]):
    if not market_district_id: return None
    c=conn(); r=c.execute('SELECT id FROM tenants WHERE district_id=?',(market_district_id,)).fetchone(); c.close()
    return r['id'] if r else None

def market_from_header(x_market_district_id: Optional[str]):
    return market_tenant_id(x_market_district_id)

def apply_national_location_payload(payload):
    """Apply a national location payload to the local master. Returns inserted/updated rows."""
    c=conn(); count=0; seen=set()
    try:
        if isinstance(payload, dict):
            rows=payload.get('districts',[]) or []
            for d in rows:
                if not isinstance(d,dict): continue
                sname=str(d.get('state','')).strip(); dname=str(d.get('district','')).strip()
                if not sname or not dname: continue
                key=(sname.casefold(),dname.casefold())
                if key in seen: continue
                seen.add(key)
                ensure_location_tenant(c,sname,str(d.get('stateCode','')).strip(),dname,str(d.get('districtCode','')).strip()); count+=1
        elif isinstance(payload, list):
            for state in payload:
                if not isinstance(state,dict): continue
                sname=str(state.get('state','')).strip()
                if not sname: continue
                for d in state.get('districts',[]) or []:
                    dname=str(d.get('district','') if isinstance(d,dict) else d).strip()
                    if not dname: continue
                    dcode=str(d.get('districtCode','')).strip() if isinstance(d,dict) else ''
                    scode=str(state.get('stateCode','')).strip()
                    key=(sname.casefold(),dname.casefold())
                    if key in seen: continue
                    seen.add(key); ensure_location_tenant(c,sname,scode,dname,dcode); count+=1
        c.commit()
        return count
    finally:
        c.close()

def load_bundled_national_locations():
    """Load the bundled national state/district reference for offline-first operation."""
    try:
        with open(BUNDLED_LOCATION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def ensure_bundled_national_locations():
    payload = load_bundled_national_locations()
    if payload:
        return apply_national_location_payload(payload)
    return 0

def sync_national_locations_from_remote():
    """Refresh district master from the configured public national reference source."""
    try:
        req=urllib.request.Request(LOCATION_SOURCE_URL, headers={'User-Agent':'KaushalPulse/8.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload=json.loads(resp.read().decode('utf-8'))
        return apply_national_location_payload(payload)
    except Exception:
        return 0

def ensure_provenance_tables(c):
    c.executescript('''
      CREATE TABLE IF NOT EXISTS data_sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL, url TEXT,
        official_url TEXT, accessed_at TEXT NOT NULL, data_vintage TEXT, license TEXT, notes TEXT
      );
      CREATE TABLE IF NOT EXISTS evidence_records (
        id TEXT PRIMARY KEY, tenant_id TEXT, source_id TEXT NOT NULL, entity_type TEXT NOT NULL,
        entity_id TEXT, metric TEXT, value_json TEXT NOT NULL, observed_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(source_id) REFERENCES data_sources(id)
      );
      CREATE INDEX IF NOT EXISTS idx_evidence_tenant_entity ON evidence_records(tenant_id,entity_type,entity_id);
      CREATE TABLE IF NOT EXISTS engine_runs (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, engine_version TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id)
      );
      CREATE INDEX IF NOT EXISTS idx_engine_runs_tenant_time ON engine_runs(tenant_id,created_at);
    ''')
    c.execute('INSERT OR IGNORE INTO data_sources(id,name,source_type,url,official_url,accessed_at,data_vintage,license,notes) VALUES(?,?,?,?,?,?,?,?,?)',('src-lgd','National district reference (government-directory derived)','public-reference',LOCATION_SOURCE_URL,LOCATION_SOURCE_OFFICIAL,now(),'runtime-refresh','MIT for the mirror dataset; official reference linked','District names/codes are refreshed from a public dataset whose README traces the data to the Government of India directory. Replace the mirror with an authenticated official LGD feed for production.'))
    c.execute('INSERT OR IGNORE INTO data_sources(id,name,source_type,url,official_url,accessed_at,data_vintage,license,notes) VALUES(?,?,?,?,?,?,?,?,?)',('src-job-signal','KaushalPulse employer/job signal dataset','prototype-seeded','', '', now(),'prototype','Internal','Seeded operational records; not represented as live government statistics.'))
    c.execute('INSERT OR IGNORE INTO data_sources(id,name,source_type,url,official_url,accessed_at,data_vintage,license,notes) VALUES(?,?,?,?,?,?,?,?,?)',('src-employer','Employer-submitted demand and feedback','user-submitted','', '', now(),'live-on-write','Owner-submitted','Employer records are user submissions and remain auditable.'))
    c.execute('INSERT OR IGNORE INTO data_sources(id,name,source_type,url,official_url,accessed_at,data_vintage,license,notes) VALUES(?,?,?,?,?,?,?,?,?)',('src-training','Training-provider course and capacity records','user-submitted','', '', now(),'live-on-write','Owner-submitted','Training supply is based on provider-entered records.'))
    c.execute('INSERT OR IGNORE INTO data_sources(id,name,source_type,url,official_url,accessed_at,data_vintage,license,notes) VALUES(?,?,?,?,?,?,?,?,?)',('src-student','Student assessment/profile inputs','user-submitted','', '', now(),'live-on-write','User-owned','Used for personalized recommendations and readiness.'))

try:
    ensure_prov_conn=conn(); ensure_provenance_tables(ensure_prov_conn); ensure_prov_conn.commit(); ensure_prov_conn.close()
except Exception:
    pass

def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()[:24]

def core_engine_snapshot(tid, student_id=None):
    c=conn()
    district=c.execute('SELECT t.id,d.name district_name,s.name state_name FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?',(tid,)).fetchone()
    if not district: c.close(); raise HTTPException(404,'District tenant not found')
    roles=c.execute('SELECT r.id,r.name,r.sector,COALESCE(SUM(j.openings),0) openings,COUNT(DISTINCT j.id) postings FROM roles r LEFT JOIN jobs j ON j.role_id=r.id AND j.tenant_id=? AND j.status="open" GROUP BY r.id ORDER BY openings DESC,r.name',(tid,)).fetchall()
    skill_rows=c.execute('SELECT sk.id,sk.name,COALESCE(SUM(j.openings),0) openings,COUNT(DISTINCT j.id) postings FROM skills sk LEFT JOIN role_skills rs ON rs.skill_id=sk.id LEFT JOIN jobs j ON j.role_id=rs.role_id AND j.tenant_id=? AND j.status="open" GROUP BY sk.id ORDER BY openings DESC,sk.name',(tid,)).fetchall()
    skill_demand=[]
    for r in skill_rows:
        hist=c.execute('SELECT period_label,openings FROM skill_demand_history WHERE tenant_id=? AND skill_id=? ORDER BY CASE period_label WHEN "current_quarter" THEN 0 ELSE 1 END, id DESC LIMIT 2',(tid,r['id'])).fetchall()
        prev=next((x['openings'] for x in hist if x['period_label']=='previous_quarter'),0)
        cur=int(r['openings'] or 0)
        growth=round(((cur-prev)/prev)*100) if prev else (100 if cur else 0)
        fb=c.execute('SELECT AVG(rating) v FROM employer_feedback WHERE tenant_id=? AND instr(lower(COALESCE(missing_skills,"")),lower(?))>0',(tid,r['name'])).fetchone()['v'] or 0
        employer_priority=round(float(fb)*20) if fb else 50
        volume_score=min(100,cur*4)
        growth_score=max(0,min(100,50+growth))
        sector_growth=50
        emerging=80 if r['id'] in {'ai','cloud','docker','ev','bms','plc'} else 45
        score=round(.35*volume_score+.25*growth_score+.20*employer_priority+.10*sector_growth+.10*emerging)
        supply=c.execute('SELECT COALESCE(SUM(c.seats),0) v FROM courses c JOIN course_skills cs ON cs.course_id=c.id WHERE c.tenant_id=? AND c.active=1 AND cs.skill_id=?',(tid,r['id'])).fetchone()['v']
        gap=max(cur-int(supply or 0),0)
        skill_demand.append({'skill_id':r['id'],'name':r['name'],'openings':cur,'postings':int(r['postings'] or 0),'growth_pct':growth,'training_seats':int(supply or 0),'gap':gap,'demand_score':score})
    course_rows=c.execute('SELECT c.id,c.name,c.seats FROM courses c WHERE c.tenant_id=? AND c.active=1 ORDER BY c.name',(tid,)).fetchall()
    course_health=[]
    demand_weights={x['skill_id']:max(1,x['demand_score']) for x in skill_demand}
    for course in course_rows:
        taught={x['skill_id'] for x in c.execute('SELECT skill_id FROM course_skills WHERE course_id=?',(course['id'],)).fetchall()}
        den=sum(demand_weights.values()) or 1; covered=sum(v for sid,v in demand_weights.items() if sid in taught)
        score=round(covered/den*100) if den else 0
        missing=[x['name'] for x in skill_demand if x['demand_score']>=55 and x['skill_id'] not in taught][:5]
        course_health.append({'course_id':course['id'],'course':course['name'],'health_score':score,'seats':course['seats'],'missing_skills':missing,'action':'Healthy' if score>=70 else ('Needs upgrade' if score>=45 else 'Review / phase down')})
    recommendations=[]
    for x in sorted(skill_demand,key=lambda z:(z['gap'],z['demand_score']),reverse=True)[:6]:
        if x['gap']>0 and x['demand_score']>=50:
            recommendations.append({'skill_id':x['skill_id'],'skill':x['name'],'action':f'Increase aligned training capacity by up to {min(x["gap"],200)} seats','reason':f'Demand score {x["demand_score"]}; {x["openings"]} open positions vs {x["training_seats"]} aligned seats.'})
    payload={'district':dict(district),'engine_version':ENGINE_VERSION,'skill_demand':skill_demand[:20],'role_demand':[dict(x) for x in roles],'course_health':course_health,'recommendations':recommendations}
    if student_id:
        ss={r['skill_id']:r['level'] for r in c.execute('SELECT skill_id,level FROM student_skills WHERE student_id=?',(student_id,)).fetchall()}
        payload['student_skill_levels']=ss
        active_student=c.execute('SELECT target_role FROM students WHERE id=?',(student_id,)).fetchone()
        if active_student:
            role=c.execute('SELECT * FROM roles WHERE name=? OR id=?',(active_student['target_role'],active_student['target_role'])).fetchone()
            if role:
                reqs=c.execute('SELECT skill_id,required_level,weight FROM role_skills WHERE role_id=?',(role['id'],)).fetchall()
                denom=sum(float(r['weight']) for r in reqs) or 1
                readiness_num=sum(min(int(ss.get(r['skill_id'],0)), int(r['required_level']))/max(int(r['required_level']),1)*float(r['weight']) for r in reqs)
                payload['student_readiness'] = round(readiness_num/denom*100) if reqs else 0
                jobs=c.execute('SELECT j.id,j.title,j.openings,j.company_id,co.name company_name,j.role_id FROM jobs j JOIN companies co ON co.id=j.company_id WHERE j.tenant_id=? AND j.status="open" ORDER BY j.openings DESC,j.id DESC LIMIT 50',(tid,)).fetchall()
                fits=[]
                for j in jobs:
                    jr=c.execute('SELECT skill_id,required_level,weight FROM role_skills WHERE role_id=?',(j['role_id'],)).fetchall(); d=sum(float(x['weight']) for x in jr) or 1
                    n=sum(min(int(ss.get(x['skill_id'],0))/max(int(x['required_level']),1),1)*float(x['weight']) for x in jr)
                    missing=[x['skill_id'] for x in jr if int(ss.get(x['skill_id'],0))<int(x['required_level'])]
                    fits.append({**dict(j),'match':round(n/d*100),'missing_skill_ids':missing})
                payload['job_fit']=sorted(fits,key=lambda z:(-z['match'],-z['openings']))[:20]
    fp=_fingerprint(payload)
    run_id='run-'+uuid.uuid4().hex[:14]
    c.execute('INSERT INTO engine_runs(id,tenant_id,engine_version,input_fingerprint,created_at) VALUES(?,?,?,?,?)',(run_id,tid,ENGINE_VERSION,fp,now()))
    observed=now()
    for item in skill_demand[:20]:
        c.execute('INSERT INTO evidence_records(id,tenant_id,source_id,entity_type,entity_id,metric,value_json,observed_at) VALUES(?,?,?,?,?,?,?,?)',(f'evidence-{uuid.uuid4().hex[:14]}',tid,'src-job-signal','skill',item['skill_id'],'demand_snapshot',json.dumps(item,default=str),observed))
    for item in course_health:
        c.execute('INSERT INTO evidence_records(id,tenant_id,source_id,entity_type,entity_id,metric,value_json,observed_at) VALUES(?,?,?,?,?,?,?,?)',(f'evidence-{uuid.uuid4().hex[:14]}',tid,'src-training','course',item['course_id'],'course_health',json.dumps(item,default=str),observed))
    c.commit(); c.close()
    payload['run_id']=run_id
    payload['provenance']=[
      {'source_id':'src-lgd','label':'District identity','type':'public-reference','official_url':LOCATION_SOURCE_OFFICIAL,'source_url':LOCATION_SOURCE_URL,'note':'Reference mirror; refresh against official LGD/IGOD source for production.'},
      {'source_id':'src-job-signal','label':'Job demand records','type':'prototype-seeded / employer-entered'},
      {'source_id':'src-training','label':'Training supply','type':'training-provider records'},
    ]
    return payload

def tenant_context(x_tenant_id: Optional[str] = Header(None, alias='X-Tenant-ID'), x_session_token: Optional[str] = Header(None, alias='X-Session-Token')):
    tid=x_tenant_id
    if x_session_token:
        c=conn(); sess=c.execute('SELECT s.*,u.tenant_id,u.role,u.name,u.email,u.credential_id,u.organization_id FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?',(x_session_token,)).fetchone()
        if not sess: c.close(); raise HTTPException(401,'Session expired or invalid. Please sign in again.')
        if sess['expires_at'] < now(): c.execute('DELETE FROM auth_sessions WHERE token=?',(x_session_token,)); c.commit(); c.close(); raise HTTPException(401,'Session expired. Please sign in again.')
        tid=sess['tenant_id']
        if x_tenant_id and x_tenant_id != tid: c.close(); raise HTTPException(403,'Signed-in user cannot switch to another district tenant.')
        row=c.execute('SELECT t.id,t.district_id,d.name district_name,d.state_id,s.name state_name,s.code state_code FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?',(tid,)).fetchone(); c.close()
        if not row: raise HTTPException(403,'Unknown tenant')
        return {**dict(row),'user_id':sess['user_id'],'role':sess['role'],'user_name':sess['name'],'user_email':sess['email'],'credential_id':sess['credential_id'],'organization_id':sess['organization_id'],'session_token':x_session_token}
    if not tid:
        c=conn(); row=c.execute('SELECT id FROM tenants ORDER BY id LIMIT 1').fetchone(); c.close(); tid=row['id'] if row else None
    c=conn(); row=c.execute('SELECT t.id,t.district_id,d.name district_name,d.state_id,s.name state_name,s.code state_code FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?',(tid,)).fetchone(); c.close()
    if not row: raise HTTPException(403,'Unknown tenant')
    return dict(row)

def require_auth(t=Depends(tenant_context)):
    if not t.get('user_id'): raise HTTPException(401,'Login required')
    return t

def require_role(*roles):
    def dep(t=Depends(require_auth)):
        if t.get('role') not in roles: raise HTTPException(403,'This workspace is not available for your account role.')
        return t
    return dep

def log(c,tenant_id,actor,action,etype,eid,payload): c.execute('INSERT INTO audit_log(tenant_id,actor,action,entity_type,entity_id,payload,created_at) VALUES(?,?,?,?,?,?,?)',(tenant_id,actor,action,etype,eid,json.dumps(payload),now()))

@app.get('/api/core/engine')
def core_engine(t=Depends(require_auth), x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    market_tid=market_tenant_id(x_market_district_id) or t['id']
    return core_engine_snapshot(market_tid, t.get('user_id') if market_tid==t['id'] else None)

def ensure_national_demo_data():
    """Give every known national district a small, clearly demo-labelled market so every selector target is usable end-to-end."""
    c=conn()
    roles=[('software','Software Engineer','IT & Services'),('frontend','Frontend Developer','IT & Services'),('qa','QA Automation Engineer','IT & Services'),('ai-engineer','AI Engineer','IT & Services'),('ev-tech','EV Service Technician','Automotive'),('cnc-op','CNC Operator','Manufacturing'),('solar-tech','Solar Technician','Energy'),('cyber-analyst','Cybersecurity Analyst','IT & Services')]
    course_map={
      'software':('Software Foundations',['java','sql','cloud']),
      'frontend':('Web Development',['java','sql','communication']),
      'qa':('QA Automation',['java','sql','communication']),
      'ai-engineer':('Applied AI Engineering',['python','ai','cloud','sql']),
      'ev-tech':('EV Service Technician',['ev','bms','communication']),
      'cnc-op':('CNC & Automation',['cnc','plc','welding']),
      'solar-tech':('Solar Technology',['solar','plc','communication']),
      'cyber-analyst':('Cybersecurity Foundations',['python','cyber','cloud','sql'])}
    try:
        districts=c.execute('SELECT t.id tenant_id,d.id district_id,d.name district_name,s.id state_id,s.name state_name,s.code state_code FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id ORDER BY d.id').fetchall()
        for row in districts:
            tid=row['tenant_id']
            existing=c.execute('SELECT COUNT(*) n FROM jobs WHERE tenant_id=?',(tid,)).fetchone()['n']
            if existing:
                continue
            seed=int(hashlib.sha256(row['district_id'].encode()).hexdigest()[:8],16)
            chosen=[]
            for i in range(3): chosen.append(roles[(seed+i)%len(roles)])
            company_id=f'demo-co-{hashlib.sha1(row["district_id"].encode()).hexdigest()[:16]}'
            cname=f'{row["district_name"]} Workforce Partners'
            sector=chosen[0][2]
            c.execute('INSERT OR IGNORE INTO companies(id,tenant_id,name,sector,size,website,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(company_id,tid,cname,sector,'Prototype','', 'active', now()))
            for i,(rid,title,rsector) in enumerate(chosen,1):
                jid=f'demo-job-{hashlib.sha1((row["district_id"]+rid).encode()).hexdigest()[:16]}'
                openings=3+((seed>>(i*4))%18)
                smin=18000+((seed+i*7000)%32000); smax=smin+18000+((seed>>8)%30000)
                c.execute('INSERT OR IGNORE INTO jobs(id,tenant_id,company_id,role_id,title,openings,location_text,salary_min,salary_max,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,tid,company_id,rid,title,openings,row['district_name'],smin,smax,'open',now()))
            prov_id=f'demo-prov-{hashlib.sha1((row["district_id"]+"prov").encode()).hexdigest()[:16]}'
            c.execute('INSERT OR IGNORE INTO training_providers(id,tenant_id,name,provider_type,created_at) VALUES(?,?,?,?,?)',(prov_id,tid,f'{row["district_name"]} Skill Centre','Prototype Training Provider',now()))
            rid=chosen[seed%len(chosen)][0]
            cname2, skill_ids=course_map[rid]
            course_id=f'demo-course-{hashlib.sha1((row["district_id"]+rid).encode()).hexdigest()[:16]}'
            seats=40+seed%121
            c.execute('INSERT OR IGNORE INTO courses(id,tenant_id,provider_id,name,duration_weeks,seats,active,created_at) VALUES(?,?,?,?,?,?,?,?)',(course_id,tid,prov_id,cname2,12,seats,1,now()))
            for sid in skill_ids:
                c.execute('INSERT OR IGNORE INTO course_skills(course_id,skill_id,taught_level) VALUES(?,?,?)',(course_id,sid,2))
        c.commit()
        return len(districts)
    finally:
        c.close()

@app.on_event('startup')
def startup_sync_locations():
    try:
        c=conn(); n=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; c.close()
        if n < 500:
            ensure_bundled_national_locations()
        # Prefer the live national refresh when network access is available.
        c=conn(); n=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; c.close()
        if n < 740:
            sync_national_locations_from_remote()
        # Any district that exists in the national master gets a usable demo market.
        ensure_national_demo_data()
        c=conn(); ensure_feature_seed(c); c.commit(); c.close()
    except Exception as exc:
        try: ensure_bundled_national_locations(); ensure_national_demo_data()
        except Exception: pass

@app.get('/api/national/locations')
def national_locations():
    """Return the national state/district selector data. Prefer a fresh remote sync, then bundled fallback."""
    try:
        c=conn(); n=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; c.close()
        if n < 740:
            sync_national_locations_from_remote()
        c=conn(); n2=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; c.close()
        if n2 < 500:
            ensure_bundled_national_locations()
    except Exception:
        try: ensure_bundled_national_locations()
        except Exception: pass
    c=conn()
    rows=c.execute('SELECT d.id district_id,d.name district,d.lgd_code district_code,s.id state_id,s.name state,s.code state_code FROM districts d JOIN states s ON s.id=d.state_id ORDER BY s.name,d.name').fetchall()
    c.close()
    locations=[dict(r) for r in rows]
    return {'locations':locations,'states':len({(x['state_id'],x['state']) for x in locations}),'districts':len(locations),'source':LOCATION_SOURCE_NAME,'official_reference':LOCATION_SOURCE_OFFICIAL,'refresh_endpoint':'/api/national/coverage/refresh','coverage_mode':'remote national refresh with bundled offline fallback'}

@app.get('/api/national/coverage')
def national_coverage():
    c=conn(); states=c.execute('SELECT COUNT(*) FROM states').fetchone()[0]; districts=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; tenants=c.execute('SELECT COUNT(*) FROM tenants').fetchone()[0]; c.close()
    return {'states':states,'districts':districts,'tenant_ready_districts':tenants,'location_source':LOCATION_SOURCE_NAME,'source_url':LOCATION_SOURCE_URL,'official_reference':LOCATION_SOURCE_OFFICIAL,'refresh_endpoint':'/api/national/coverage/refresh','coverage_mode':'bundled fallback + online refresh'}

@app.post('/api/national/coverage/refresh')
def national_coverage_refresh(t=Depends(require_role('DSC_ADMIN'))):
    count=sync_national_locations_from_remote(); c=conn(); states=c.execute('SELECT COUNT(*) FROM states').fetchone()[0]; districts=c.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; tenants=c.execute('SELECT COUNT(*) FROM tenants').fetchone()[0]; c.close()
    return {'refreshed_records':count,'states':states,'districts':districts,'tenant_ready_districts':tenants,'source_url':LOCATION_SOURCE_URL,'official_reference':LOCATION_SOURCE_OFFICIAL}

@app.get('/api/evidence')
def evidence(entity_type: Optional[str]=None, entity_id: Optional[str]=None, limit:int=50, t=Depends(require_auth)):
    c=conn(); q='SELECT er.id,er.source_id,ds.name source_name,ds.source_type,ds.url,ds.official_url,er.entity_type,er.entity_id,er.metric,er.value_json,er.observed_at FROM evidence_records er JOIN data_sources ds ON ds.id=er.source_id WHERE er.tenant_id=?'; args=[t['id']]
    if entity_type: q+=' AND er.entity_type=?'; args.append(entity_type)
    if entity_id: q+=' AND er.entity_id=?'; args.append(entity_id)
    q+=' ORDER BY er.observed_at DESC LIMIT ?'; args.append(max(1,min(limit,200)))
    rows=c.execute(q,args).fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/health')
def health(): return {'status':'ok','service':'kaushalpulse','version':'8.0.0','database':'sqlite','mode':'national-evidence-engine','required_routes':['/api/student/readiness','/api/student/gap','/api/jobs/recommended','/api/student/resume','/api/student/resume-fitness','/api/student/path-navigator','/api/student/path-navigator/generate','/api/student/path-navigator/steps','/api/employment/commitments','/api/employment/invites','/api/mentors','/api/mentors/requests','/api/skill-alerts','/api/skill-alerts/actions']}

class LoginIn(BaseModel):
    role: str
    email: EmailStr
    password: str = Field(min_length=6)
    identifier: Optional[str] = None

class DemoLoginIn(BaseModel):
    demo_id: str = Field(min_length=6, max_length=64)

@app.post('/api/auth/demo-login')
def demo_login(x: DemoLoginIn):
    demo_id=x.demo_id.strip().upper()
    c=conn(); u=c.execute('SELECT u.* FROM demo_accounts d JOIN users u ON u.id=d.user_id WHERE upper(d.demo_id)=?',(demo_id,)).fetchone()
    if not u:
        c.close(); raise HTTPException(401,'Unknown demo ID')
    token=secrets.token_urlsafe(32); created=now(); expires=datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()+60*60*12,tz=timezone.utc).isoformat()
    c.execute('INSERT INTO auth_sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)',(token,u['id'],created,expires))
    tenant=c.execute('SELECT t.id tenant_id,d.name district_name,s.name state_name FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?',(u['tenant_id'],)).fetchone(); c.commit(); c.close()
    return {'token':token,'user':{'id':u['id'],'name':u['name'],'email':u['email'],'role':u['role'],'credential_id':u['credential_id'],'organization_id':u['organization_id'],'tenant_id':u['tenant_id'],'district_name':tenant['district_name'],'state_name':tenant['state_name']},'demo_id':demo_id}

@app.get('/api/auth/demo-accounts')
def demo_accounts():
    c=conn(); rows=c.execute('SELECT demo_id,label FROM demo_accounts ORDER BY demo_id').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/auth/login')
def login(x: LoginIn):
    role=x.role.strip().upper()
    if role not in {'STUDENT','EMPLOYER','TRAINING_PROVIDER','DSC_ADMIN'}: raise HTTPException(400,'Unsupported account role')
    c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND role=?',(str(x.email),role)).fetchone()
    if not u or not u['password_hash'] or not verify_password(x.password,u['password_hash']): c.close(); raise HTTPException(401,'Invalid sign-in details')
    if role!='STUDENT' and (not x.identifier or str(x.identifier).strip().upper()!=str(u['credential_id'] or '').upper()): c.close(); raise HTTPException(401,'The additional identity number does not match this account')
    token=secrets.token_urlsafe(32); created=now(); expires=datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()+60*60*12,tz=timezone.utc).isoformat()
    c.execute('INSERT INTO auth_sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)',(token,u['id'],created,expires))
    tenant=c.execute('SELECT t.id tenant_id,d.name district_name,s.name state_name FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?',(u['tenant_id'],)).fetchone(); c.commit(); c.close()
    return {'token':token,'user':{'id':u['id'],'name':u['name'],'email':u['email'],'role':u['role'],'credential_id':u['credential_id'],'organization_id':u['organization_id'],'tenant_id':u['tenant_id'],'district_name':tenant['district_name'],'state_name':tenant['state_name']}}

@app.get('/api/auth/me')
def auth_me(t=Depends(require_auth)):
    return {'user':{'id':t['user_id'],'name':t['user_name'],'email':t['user_email'],'role':t['role'],'credential_id':t['credential_id'],'organization_id':t['organization_id'],'tenant_id':t['id'],'district_name':t['district_name'],'state_name':t['state_name']}}

@app.post('/api/auth/logout')
def logout(x_session_token: Optional[str] = Header(None, alias='X-Session-Token')):
    if x_session_token:
        c=conn(); c.execute('DELETE FROM auth_sessions WHERE token=?',(x_session_token,)); c.commit(); c.close()
    return {'status':'logged_out'}

@app.get('/api/states')
def get_states():
    try:
        c0=conn(); n=c0.execute('SELECT COUNT(*) FROM districts').fetchone()[0]; c0.close()
        if n < 700: sync_national_locations_from_remote()
    except Exception: pass
    c=conn(); rows=c.execute('SELECT s.*, COUNT(d.id) district_count FROM states s LEFT JOIN districts d ON d.state_id=s.id GROUP BY s.id ORDER BY s.name').fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/states/{state_id}/districts')
def get_districts(state_id:str, search:Optional[str]=None):
    c=conn(); q='SELECT d.*, s.name state_name FROM districts d JOIN states s ON s.id=d.state_id WHERE d.state_id=?'; args=[state_id]
    if search: q+=' AND d.name LIKE ?'; args.append('%'+search+'%')
    q+=' ORDER BY d.name'; rows=c.execute(q,args).fetchall(); c.close(); return [dict(r) for r in rows]


@app.get('/api/market/summary')
def market_summary(x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return {'district':'Select a district','companies':0,'open_jobs':0,'training_providers':0,'training_capacity':0,'data_status':'location-only'}
    c=conn(); row=c.execute("""SELECT d.name district_name,s.name state_name,
      (SELECT COUNT(*) FROM companies WHERE tenant_id=? AND status='active') companies,
      (SELECT COALESCE(SUM(openings),0) FROM jobs WHERE tenant_id=? AND status='open') open_jobs,
      (SELECT COUNT(*) FROM training_providers WHERE tenant_id=?) training_providers,
      (SELECT COALESCE(SUM(seats),0) FROM courses WHERE tenant_id=? AND active=1) training_capacity
      FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE t.id=?""",(tid,tid,tid,tid,tid)).fetchone(); c.close()
    return {**dict(row),'data_status':'stored-local-district-data','engine_version':ENGINE_VERSION,'provenance':core_engine_snapshot(tid)['provenance']} if row else {'district':'Select a district','companies':0,'open_jobs':0,'training_providers':0,'training_capacity':0,'data_status':'location-only'}


@app.get('/api/student/market-jobs')
def student_market_jobs(limit:int=50, x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID'), t=Depends(require_role('STUDENT'))):
    tid=market_from_header(x_market_district_id) or t['id']
    snap=core_engine_snapshot(tid,t['user_id'])
    out=snap.get('job_fit',[])[:max(1,min(limit,100))]
    return {'items':out,'market':snap['district'],'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.get('/api/market/jobs')
def market_jobs(limit:int=50, x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return []
    c=conn(); rows=c.execute("""SELECT j.id,j.title,j.openings,j.location_text,j.salary_min,j.salary_max,
      co.name company_name,r.name role_name FROM jobs j JOIN companies co ON co.id=j.company_id JOIN roles r ON r.id=j.role_id
      WHERE j.tenant_id=? AND j.status='open' ORDER BY j.created_at DESC LIMIT ?""",(tid,max(1,min(limit,100)))).fetchall(); c.close(); return [dict(x) for x in rows]

@app.get('/api/market/demand')
def market_demand(x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return {'roles':[],'skills':[],'skill_demand':[],'data_status':'location-only'}
    snap=core_engine_snapshot(tid)
    c=conn(); roles=[]
    for r in snap.get('role_demand',[]):
        skills=c.execute('SELECT sk.id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=? ORDER BY rs.weight DESC',(r['id'],)).fetchall()
        roles.append({**r,'skills':[dict(x) for x in skills]})
    c.close()
    return {'district':snap['district'],'roles':roles,'skills':snap.get('skill_demand',[]),'skill_demand':snap.get('skill_demand',[]),'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.get('/api/market/companies')
def market_companies(page:int=1,page_size:int=20, x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return {'items':[],'total':0,'page':page,'page_size':page_size,'pages':0}
    page=max(1,page); page_size=max(1,min(page_size,50)); off=(page-1)*page_size
    c=conn(); total=c.execute('SELECT COUNT(*) FROM companies WHERE tenant_id=? AND status="active"',(tid,)).fetchone()[0]
    rows=c.execute('SELECT id,name,sector,size,website FROM companies WHERE tenant_id=? AND status="active" ORDER BY name LIMIT ? OFFSET ?',(tid,page_size,off)).fetchall(); c.close(); return {'items':[dict(x) for x in rows],'total':total,'page':page,'page_size':page_size,'pages':math.ceil(total/page_size) if page_size else 0}

@app.get('/api/market/academy')
def market_academy(x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return {'courses':[]}
    c=conn(); rows=c.execute("""SELECT c.id,c.name,c.duration_weeks,c.seats,p.name provider_name FROM courses c JOIN training_providers p ON p.id=c.provider_id WHERE c.tenant_id=? AND c.active=1 ORDER BY c.name""",(tid,)).fetchall(); out=[]
    for r in rows:
        skills=c.execute('SELECT sk.name FROM course_skills cs JOIN skills sk ON sk.id=cs.skill_id WHERE cs.course_id=? ORDER BY sk.name',(r['id'],)).fetchall(); out.append({**dict(r),'skills':', '.join(x['name'] for x in skills)})
    c.close(); return {'courses':out}

@app.get('/api/market/alignment')
def market_alignment(x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    tid=market_from_header(x_market_district_id)
    if not tid: return []
    snap=core_engine_snapshot(tid)
    return [dict(x,alignment_score=x['health_score']) for x in snap['course_health']]

@app.get('/api/market/course-alerts')
def market_course_alerts(x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID')):
    return market_alignment(x_market_district_id)

@app.post('/api/locations/ensure')
def ensure_location(payload:dict, t=Depends(require_auth)):
    state=payload.get('state','').strip(); district=payload.get('district','').strip(); state_code=payload.get('state_code','').strip(); district_code=payload.get('district_code','').strip()
    if not state or not district: raise HTTPException(400,'State and district are required')
    c=conn(); did,tid=ensure_location_tenant(c,state,state_code,district,district_code); c.commit(); c.close(); return {'district_id':did,'tenant_id':tid,'district':district,'state':state}

@app.post('/api/tenants/select')
def select_tenant(payload:dict,t=Depends(require_auth)):
    did=payload.get('district_id'); c=conn(); r=c.execute('SELECT t.id,d.name district_name,s.name state_name FROM tenants t JOIN districts d ON d.id=t.district_id JOIN states s ON s.id=d.state_id WHERE d.id=?',(did,)).fetchone(); c.close()
    if not r: raise HTTPException(404,'District tenant not found')
    if r['id'] != t['id']: raise HTTPException(403,'Your account is locked to its assigned district.')
    return dict(r)

@app.get('/api/tenant/context')
def context(t=Depends(tenant_context)): return t

@app.get('/api/student/profile')
def profile(t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT * FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    if not s:
        sid='stu-'+re.sub(r'[^a-z0-9]+','-',t['district_id'].lower()).strip('-')
        c.execute('INSERT OR IGNORE INTO students(id,tenant_id,name,qualification,target_role,target_company,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(sid,t['id'],'New Student','','Software Engineer','',now(),now()))
        s=c.execute('SELECT * FROM students WHERE id=?',(sid,)).fetchone()
    # Seed a neutral starter skill profile for a newly onboarded district/student.
    if c.execute('SELECT COUNT(*) FROM student_skills WHERE student_id=?',(s['id'],)).fetchone()[0]==0:
        for sid2,lvl in [('java',1),('python',1),('sql',1),('communication',1)]:
            c.execute('INSERT OR IGNORE INTO student_skills(student_id,skill_id,level,score,source,updated_at) VALUES(?,?,?,?,?,?)',(s['id'],sid2,lvl,LEVEL_SCORE[lvl],'starter',now()))
        c.commit()
    ss=c.execute('SELECT sk.id,sk.name,sk.category,ss.level,ss.score,ss.source FROM student_skills ss JOIN skills sk ON sk.id=ss.skill_id WHERE ss.student_id=? ORDER BY sk.category,sk.name',(s['id'],)).fetchall(); c.close()
    return {**dict(s),'tenant':t,'skills':[dict(x) for x in ss]}

class ProfileIn(BaseModel): name:str; qualification:str=''; target_role:str=''; target_company:str=''
@app.put('/api/student/profile')
def update_profile(p:ProfileIn,t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    sid=s['id'] if s else 'stu-'+uuid.uuid4().hex[:8]
    if s: c.execute('UPDATE students SET name=?,qualification=?,target_role=?,target_company=?,updated_at=? WHERE id=?',(p.name,p.qualification,p.target_role,p.target_company,now(),sid))
    else: c.execute('INSERT INTO students(id,tenant_id,name,qualification,target_role,target_company,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(sid,t['id'],p.name,p.qualification,p.target_role,p.target_company,now(),now()))
    c.commit(); c.close(); return {'status':'saved','student_id':sid}

class AssessmentIn(BaseModel): skill_id:str; level:int=Field(ge=1,le=3); source:str='task_assessment'
@app.post('/api/student/assessment')
def save_assessment(a:AssessmentIn,t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone();
    if not s: raise HTTPException(404,'Create profile first')
    score=LEVEL_SCORE[a.level]; c.execute('INSERT INTO student_skills(student_id,skill_id,level,score,source,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(student_id,skill_id) DO UPDATE SET level=excluded.level,score=excluded.score,source=excluded.source,updated_at=excluded.updated_at',(s['id'],a.skill_id,a.level,score,a.source,now()))
    c.execute('INSERT INTO assessments(tenant_id,student_id,skill_id,level,score,source,created_at) VALUES(?,?,?,?,?,?,?)',(t['id'],s['id'],a.skill_id,a.level,score,a.source,now()))
    log(c,t['id'],s['id'],'assessment_saved','assessment',a.skill_id,a.model_dump()); c.commit(); c.close(); return {'status':'saved','skill_id':a.skill_id,'level':a.level,'label':LEVEL_NAME[a.level],'score':score}

@app.get('/api/student/alignment-hub')
def student_alignment_hub(
    x_market_district_id: Optional[str] = Header(None, alias='X-Market-District-ID'),
    t=Depends(require_role('STUDENT'))
):
    """Student-facing view backed by the shared national engine."""
    market_tid=market_from_header(x_market_district_id) or t['id']
    c=conn(); student=c.execute('SELECT id,name,target_role,target_company FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    if not student:
        sid='stu-'+re.sub(r'[^a-z0-9]+','-',t['district_id'].lower()).strip('-')
        c.execute('INSERT OR IGNORE INTO students(id,tenant_id,name,qualification,target_role,target_company,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(sid,t['id'],'New Student','','Software Engineer','',now(),now()))
        for skill_id in ['java','cloud','sql','communication','docker','python']:
            c.execute('INSERT OR IGNORE INTO student_skills(student_id,skill_id,level,score,source,updated_at) VALUES(?,?,?,?,?,?)',(sid,skill_id,1,LEVEL_SCORE[1],'starter',now()))
        c.commit(); student=c.execute('SELECT id,name,target_role,target_company FROM students WHERE id=?',(sid,)).fetchone()
    snap=core_engine_snapshot(market_tid,student['id'])
    role=c.execute('SELECT * FROM roles WHERE name=? OR id=?',(student['target_role'],student['target_role'])).fetchone() or c.execute('SELECT * FROM roles ORDER BY id LIMIT 1').fetchone()
    req=c.execute('SELECT sk.id skill_id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=? ORDER BY rs.weight DESC',(role['id'],)).fetchall()
    current_levels=snap.get('student_skill_levels',{})
    gaps=[]
    demand_map={x['skill_id']:x for x in snap.get('skill_demand',[])}
    for r in req:
        cur=int(current_levels.get(r['skill_id'],0)); delta=max(int(r['required_level'])-cur,0); score_gap=max(LEVEL_SCORE[int(r['required_level'])]-LEVEL_SCORE.get(min(max(cur,0),3),0),0)
        if delta or score_gap:
            courses=c.execute('SELECT DISTINCT c.id,c.name,c.duration_weeks,c.seats,p.name provider_name FROM course_skills cs JOIN courses c ON c.id=cs.course_id JOIN training_providers p ON p.id=c.provider_id WHERE cs.skill_id=? AND c.tenant_id=? AND c.active=1 ORDER BY c.seats DESC,c.name LIMIT 3',(r['skill_id'],market_tid)).fetchall()
            gaps.append({'skill_id':r['skill_id'],'name':r['name'],'current_level':cur,'current_label':LEVEL_NAME.get(cur,'Not assessed'),'required_level':r['required_level'],'required_label':LEVEL_NAME[r['required_level']],'gap_level':delta,'gap_score':score_gap,'weight':r['weight'],'local_demand':demand_map.get(r['skill_id'],{'openings':0,'postings':0,'demand_score':0}),'courses':[dict(x) for x in courses]})
    gaps.sort(key=lambda x:(-x['gap_score'],-float(x['weight']),-int(x['local_demand'].get('demand_score',0))))
    jobs=snap.get('job_fit',[])
    return {'student':dict(student),'target_role':dict(role),'readiness':snap.get('student_readiness',0),'market':snap['district'],'demand':snap.get('skill_demand',[])[:12],'gaps':gaps[:12],'jobs':jobs[:8],'engine_version':snap['engine_version'],'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.get('/api/student/gap')
def gap(t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id,target_role FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    if not s:
        c.close(); raise HTTPException(404,'Student profile not found')
    role=c.execute('SELECT * FROM roles WHERE name=? OR id=?',(s['target_role'],s['target_role'])).fetchone() or c.execute('SELECT * FROM roles ORDER BY id LIMIT 1').fetchone()
    snap=core_engine_snapshot(t['id'],s['id']); levels=snap.get('student_skill_levels',{})
    rows=[]
    req=c.execute('SELECT sk.id skill_id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=? ORDER BY rs.weight DESC',(role['id'],)).fetchall()
    for r in req:
        cur=int(levels.get(r['skill_id'],0)); current_score=LEVEL_SCORE.get(cur,0); target_score=LEVEL_SCORE[int(r['required_level'])]; rows.append({'skill_id':r['skill_id'],'name':r['name'],'current_level':cur,'current_score':current_score,'current_label':LEVEL_NAME.get(cur,'Not assessed'),'target_level':r['required_level'],'target_score':target_score,'target_label':LEVEL_NAME[r['required_level']],'gap_level':max(int(r['required_level'])-cur,0),'gap_score':max(target_score-current_score,0),'weight':r['weight']})
    den=sum(float(r['weight']) for r in req) or 1
    readiness=snap.get('student_readiness',0)
    c.close(); return {'tenant':t,'role':dict(role),'rows':rows,'readiness':readiness,'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.get('/api/student/readiness')
def readiness(t=Depends(require_role('STUDENT'))):
    g=gap(t); s=g['readiness']; return {'score':s,'label':'Job Ready' if s>=80 else ('Nearly Ready' if s>=60 else 'Needs Development'),'tenant':t}

@app.get('/api/student/roadmap')
def roadmap(t=Depends(require_role('STUDENT'))):
    g=gap(t); c=conn(); out=[]
    for i,x in enumerate(sorted([r for r in g['rows'] if r['gap_level']>0],key=lambda y:y['gap_score'],reverse=True),1):
        cs=c.execute('SELECT c.name FROM course_skills cs JOIN courses c ON c.id=cs.course_id WHERE cs.skill_id=? AND c.tenant_id=? ORDER BY c.seats DESC LIMIT 1',(x['skill_id'],t['id'])).fetchone()
        out.append({'step':i,'skill':x['name'],'from':x['current_label'],'to':x['target_label'],'gap_score':x['gap_score'],'recommended_course':cs['name'] if cs else 'Targeted practical module'})
    c.close(); return {'tenant':t,'role':g['role']['name'],'items':out}

@app.get('/api/jobs/recommended')
def jobs_recommended(t=Depends(require_role('STUDENT')),limit:int=20, x_market_district_id: Optional[str]=Header(None, alias='X-Market-District-ID')):
    market_tid=market_from_header(x_market_district_id) or t['id']
    snap=core_engine_snapshot(market_tid,t['user_id'])
    return {'items':snap.get('job_fit',[])[:max(1,min(limit,50))],'market':snap['district'],'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.post('/api/student/resume')
async def upload_resume(file: UploadFile = File(...), t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id,target_role FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone()
    if not s: c.close(); raise HTTPException(404,'Create student profile first')
    safe=re.sub(r'[^A-Za-z0-9._-]+','_',file.filename or 'resume')
    path=RESUME_DIR / f"{s['id']}_{uuid.uuid4().hex[:10]}_{safe}"
    with path.open('wb') as out: shutil.copyfileobj(file.file,out)
    text=extract_text_from_upload(path,file.filename or safe); found=extract_resume_skills(text)
    row=c.execute('SELECT * FROM roles WHERE name=? OR id=?',(s['target_role'],s['target_role'])).fetchone() or c.execute('SELECT * FROM roles ORDER BY id LIMIT 1').fetchone()
    req=c.execute('SELECT sk.id,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=?',(row['id'],)).fetchall(); ids={x['id'] for x in found}; score=round(sum(x['weight'] for x in req if x['id'] in ids)/sum(x['weight'] for x in req)*100) if req else 0
    cur=c.execute('INSERT INTO student_resumes(tenant_id,student_id,filename,stored_path,extracted_text,extracted_skills,fitness_score,created_at) VALUES(?,?,?,?,?,?,?,?)',(t['id'],s['id'],safe,str(path),text,json.dumps([x['id'] for x in found]),score,now()))
    log(c,t['id'],s['id'],'resume_uploaded','resume',str(cur.lastrowid),{'filename':safe,'skills':[x['name'] for x in found],'fitness_score':score}); c.commit(); c.close()
    return {'status':'processed','filename':safe,'skills':found,'fitness_score':score}

@app.get('/api/student/resume-fitness')
def resume_fitness_route(t=Depends(require_role('STUDENT'))): return resume_fitness(t)

@app.get('/api/student/path-navigator')
def path_navigator(role_id: Optional[str]=None, x_market_district_id: Optional[str]=Header(None, alias='X-Market-District-ID'), t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id,target_role FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone(); role=c.execute('SELECT * FROM roles WHERE id=?',(role_id,)).fetchone() if role_id else None
    if not role and s: role=c.execute('SELECT * FROM roles WHERE name=?',(s['target_role'],)).fetchone()
    if not role: role=c.execute('SELECT * FROM roles ORDER BY id LIMIT 1').fetchone()
    market_tid=market_from_header(x_market_district_id) or t['id']
    snap=core_engine_snapshot(market_tid,s['id'] if market_tid==t['id'] and s else None)
    role_d=next((r for r in snap['role_demand'] if r['id']==role['id']),None)
    req=c.execute('SELECT sk.id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=? ORDER BY rs.weight DESC',(role['id'],)).fetchall(); steps=[]
    for i,r in enumerate(req,1):
        course=c.execute('SELECT c.name FROM courses c JOIN course_skills cs ON cs.course_id=c.id WHERE c.tenant_id=? AND cs.skill_id=? ORDER BY c.seats DESC LIMIT 1',(market_tid,r['id'])).fetchone()
        steps.append({'week_start':(i-1)*2+1,'week_end':min(i*2,12),'skill':r['name'],'target_level':LEVEL_NAME[r['required_level']],'recommended_course':course['name'] if course else 'Project module','priority':r['weight'],'market_demand':next((x for x in snap['skill_demand'] if x['skill_id']==r['id']),None)})
    c.close(); return {'district':snap['district']['district_name'],'state':snap['district']['state_name'],'role':dict(role),'openings':role_d['openings'] if role_d else 0,'companies_hiring':None,'avg_salary':0,'duration_weeks':12,'steps':steps,'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'message':'Roadmap order is generated from the shared demand/gap/course engine for the selected market.'}

@app.get('/api/employment/commitments')
def commitments(t=Depends(tenant_context)):
    c=conn(); rows=c.execute('SELECT ec.*,co.name company_name,r.name role_name FROM employer_commitments ec JOIN companies co ON co.id=ec.company_id JOIN roles r ON r.id=ec.role_id WHERE ec.tenant_id=? AND ec.status="active" AND (? IS NULL OR ec.company_id=?) ORDER BY ec.id',(t['id'],t.get('organization_id') if t.get('role')=='EMPLOYER' else None,t.get('organization_id') if t.get('role')=='EMPLOYER' else None)).fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/employment/commitments')
def create_commitment(payload:dict,t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid=payload.get('company_id'); rid=payload.get('role_id'); slots=max(int(payload.get('committed_slots',1)),1)
    if not c.execute('SELECT 1 FROM companies WHERE id=? AND tenant_id=?',(cid,t['id'])).fetchone(): c.close(); raise HTTPException(403,'Company not in active district')
    if not c.execute('SELECT 1 FROM roles WHERE id=?',(rid,)).fetchone(): c.close(); raise HTTPException(404,'Role not found')
    eid='commit-'+uuid.uuid4().hex[:10]; c.execute('INSERT INTO employer_commitments(id,tenant_id,company_id,role_id,committed_slots,hired_slots,valid_until,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,t['id'],cid,rid,slots,0,payload.get('valid_until'),'active',payload.get('notes',''),now())); c.commit(); c.close(); return {'id':eid,'status':'created'}

@app.get('/api/employment/candidates')
def employment_candidates(t=Depends(tenant_context)):
    c=conn(); students=c.execute('SELECT id,name,qualification,target_role,target_company FROM students WHERE tenant_id=? ORDER BY name',(t['id'],)).fetchall(); out=[]
    company_id=t.get('organization_id') if t.get('role')=='EMPLOYER' else None
    if company_id:
        jobs=c.execute('SELECT j.id,j.role_id,j.title,j.openings,j.location_text,j.salary_min,j.salary_max,co.name company_name,j.company_id FROM jobs j JOIN companies co ON co.id=j.company_id WHERE j.tenant_id=? AND j.company_id=? AND j.status="open" ORDER BY j.created_at DESC',(t['id'],company_id)).fetchall()
    else:
        jobs=c.execute('SELECT j.id,j.role_id,j.title,j.openings,j.location_text,j.salary_min,j.salary_max,co.name company_name,j.company_id FROM jobs j JOIN companies co ON co.id=j.company_id WHERE j.tenant_id=? AND j.status="open" ORDER BY j.created_at DESC',(t['id'],)).fetchall()
    for st in students:
        levels={x['skill_id']:x['level'] for x in c.execute('SELECT skill_id,level FROM student_skills WHERE student_id=?',(st['id'],)).fetchall()}
        for j in jobs[:20]:
            req=c.execute('SELECT rs.skill_id,rs.weight,rs.required_level,sk.name FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=? ORDER BY rs.weight DESC',(j['role_id'],)).fetchall(); den=sum(float(x['weight']) for x in req) or 1
            matched=[dict(x) for x in req if levels.get(x['skill_id'],0)>=int(x['required_level'])]
            missing=[dict(x) for x in req if levels.get(x['skill_id'],0)<int(x['required_level'])]
            score=round(sum(float(x['weight']) for x in matched)/den*100)
            inv=c.execute('SELECT id,status FROM employment_invites WHERE tenant_id=? AND company_id=? AND student_id=? AND job_id=? ORDER BY created_at DESC LIMIT 1',(t['id'],j['company_id'],st['id'],j['id'])).fetchone()
            out.append({'student_id':st['id'],'student_name':st['name'],'qualification':st['qualification'],'target_role':st['target_role'],'job_id':j['id'],'job_title':j['title'],'openings':j['openings'],'location_text':j['location_text'],'salary_min':j['salary_min'],'salary_max':j['salary_max'],'company_id':j['company_id'],'company_name':j['company_name'],'match':score,'matched_skills':[x['name'] for x in matched],'missing_skills':[x['name'] for x in missing],'match_explanation':('Strong match: '+', '.join(x['name'] for x in matched[:3])) if score>=75 else ('Potential match: '+', '.join(x['name'] for x in matched[:3]) if matched else 'Skill evidence is currently limited.'),'invite_id':inv['id'] if inv else None,'invite_status':inv['status'] if inv else None})
    c.close(); return sorted(out,key=lambda x:(-x['match'], x['student_name']))[:30]

@app.post('/api/employment/invite')
def employment_invite(payload:dict,t=Depends(require_role('EMPLOYER'))):
    c=conn(); company_id=payload.get('company_id'); student_id=payload.get('student_id'); job_id=payload.get('job_id')
    if not c.execute('SELECT 1 FROM companies WHERE id=? AND tenant_id=?',(company_id,t['id'])).fetchone(): c.close(); raise HTTPException(403,'Company not in active district')
    if not c.execute('SELECT 1 FROM students WHERE id=? AND tenant_id=?',(student_id,t['id'])).fetchone(): c.close(); raise HTTPException(403,'Student not in active district')
    if not c.execute('SELECT 1 FROM jobs WHERE id=? AND company_id=? AND tenant_id=? AND status="open"',(job_id,company_id,t['id'])).fetchone(): c.close(); raise HTTPException(404,'Job not found or closed')
    existing=c.execute('SELECT id,status FROM employment_invites WHERE tenant_id=? AND company_id=? AND student_id=? AND job_id=? ORDER BY created_at DESC LIMIT 1',(t['id'],company_id,student_id,job_id)).fetchone()
    if existing and existing['status']!='joined': c.close(); return {'id':existing['id'],'status':existing['status'],'existing':True}
    iid='invite-'+uuid.uuid4().hex[:10]; c.execute('INSERT INTO employment_invites(id,tenant_id,company_id,student_id,job_id,status,created_at) VALUES(?,?,?,?,?,?,?)',(iid,t['id'],company_id,student_id,job_id,'invited',now())); log(c,t['id'],'employer','candidate_invited','employment_invite',iid,{'company_id':company_id,'student_id':student_id,'job_id':job_id}); c.commit(); c.close(); return {'id':iid,'status':'invited','existing':False}

@app.get('/api/mentors')
def mentors(t=Depends(tenant_context)):
    c=conn(); s=c.execute('SELECT target_role FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone(); role_text=(s['target_role'] if s else '').lower(); rows=[]
    for r in c.execute('SELECT * FROM mentors WHERE tenant_id=? ORDER BY available_slots DESC,name',(t['id'],)).fetchall():
        skill_text=r['skills'].lower(); match=80 if any(x in skill_text for x in role_text.split()[:2]) else (65 if 'python' in skill_text or 'communication' in skill_text else 45)
        rows.append({**dict(r),'match':match})
    c.close(); return rows

@app.post('/api/mentors/request')
def mentor_request(payload:dict,t=Depends(require_role('STUDENT'))):
    c=conn(); s=c.execute('SELECT id FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(t['id'],)).fetchone(); m=c.execute('SELECT id FROM mentors WHERE id=? AND tenant_id=?',(payload.get('mentor_id'),t['id'])).fetchone()
    if not s or not m: c.close(); raise HTTPException(404,'Student or mentor not found')
    rid='ment-'+uuid.uuid4().hex[:10]; c.execute('INSERT INTO mentorship_requests(id,tenant_id,student_id,mentor_id,status,goal,created_at) VALUES(?,?,?,?,?,?,?)',(rid,t['id'],s['id'],m['id'],'requested',payload.get('goal','Career guidance and weekly project review'),now())); c.commit(); c.close(); return {'id':rid,'status':'requested'}

@app.get('/api/skill-alerts')
def skill_alerts(t=Depends(tenant_context)):
    c=conn(); rows=c.execute('SELECT h.skill_id,sk.name,h.period_label,h.openings FROM skill_demand_history h JOIN skills sk ON sk.id=h.skill_id WHERE h.tenant_id=? ORDER BY sk.name,h.id',(t['id'],)).fetchall(); by={}
    for r in rows: by.setdefault(r['skill_id'],{'name':r['name']})[r['period_label']]=dict(r)
    out=[]
    for sid,x in by.items():
        cur=x.get('current_quarter',{}); prev=x.get('previous_quarter',{}); po=prev.get('openings',0) or 0; co=cur.get('openings',0) or 0; change=round((co-po)/po*100) if po else (100 if co else 0)
        out.append({'skill_id':sid,'skill':x['name'],'previous_openings':po,'current_openings':co,'change_pct':change,'status':'Rising' if change>=15 else ('Declining' if change<=-15 else 'Stable'),'recommendation':'Upskill now' if change>=15 else ('Reskill review' if change<=-15 else 'Maintain + monitor')})
    c.close(); return sorted(out,key=lambda x:abs(x['change_pct']),reverse=True)

@app.get('/api/industry/companies')
def company_list(page:int=1,page_size:int=20,sector:Optional[str]=None,search:Optional[str]=None,t=Depends(tenant_context)):
    page=max(1,page); page_size=min(max(page_size,1),50); c=conn(); q='SELECT * FROM companies WHERE tenant_id=?'; args=[t['id']]
    if sector: q+=' AND sector=?'; args.append(sector)
    if search: q+=' AND (name LIKE ? OR sector LIKE ?)'; args += [f'%{search}%',f'%{search}%']
    total=c.execute(q.replace('SELECT *','SELECT COUNT(*)'),args).fetchone()[0]; rows=c.execute(q+' ORDER BY name LIMIT ? OFFSET ?',args+[page_size,(page-1)*page_size]).fetchall(); c.close(); return {'page':page,'page_size':page_size,'total':total,'items':[dict(r) for r in rows]}

class CompanyIn(BaseModel): name:str; sector:str; size:str='MSME'; website:str=''

# ------------------------------
# Training Provider workspace
# ------------------------------
class ProviderCourseIn(BaseModel):
    name: str
    duration_weeks: int = Field(ge=1, le=104)
    seats: int = Field(ge=1, le=10000)
    skill_ids: list[str] = []

class ProviderTrainerIn(BaseModel):
    name: str
    specialization: str = ''
    skills: str = ''
    experience_years: int = Field(default=0, ge=0, le=60)
    availability: str = 'Available'

class ProviderEquipmentIn(BaseModel):
    name: str
    required_qty: int = Field(default=0, ge=0)
    available_qty: int = Field(default=0, ge=0)
    utilization_pct: int = Field(default=0, ge=0, le=100)

class ProviderPlacementIn(BaseModel):
    course_id: str
    employer_name: str
    students_placed: int = Field(default=0, ge=0)
    openings: int = Field(default=0, ge=0)
    placement_date: str
    status: str = 'Verified'
    notes: str = ''

def provider_scope(t):
    if t.get('role') != 'TRAINING_PROVIDER':
        raise HTTPException(403, 'Training Provider workspace is required.')
    provider_id=t.get('organization_id')
    c=conn()
    p=c.execute('SELECT id,name,provider_type FROM training_providers WHERE id=? AND tenant_id=?',(provider_id,t['id'])).fetchone()
    c.close()
    if not p: raise HTTPException(403,'Training provider is not registered in the signed-in district.')
    return dict(p)

@app.get('/api/provider/overview')
def provider_overview(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn()
    courses=c.execute('SELECT COUNT(*) n,COALESCE(SUM(seats),0) seats FROM courses WHERE tenant_id=? AND provider_id=? AND active=1',(t['id'],p['id'])).fetchone()
    trainer_count=c.execute('SELECT COUNT(*) n FROM provider_trainers WHERE tenant_id=? AND provider_id=? AND status="Active"',(t['id'],p['id'])).fetchone()['n']
    equipment_count=c.execute('SELECT COUNT(*) n FROM provider_equipment WHERE tenant_id=? AND provider_id=?',(t['id'],p['id'])).fetchone()['n']
    placements=c.execute('SELECT COALESCE(SUM(students_placed),0) placed,COALESCE(SUM(openings),0) openings FROM provider_placements WHERE tenant_id=? AND provider_id=? AND status="Verified"',(t['id'],p['id'])).fetchone()
    market=core_engine_snapshot(t['id'])
    c.close()
    return {'provider':p,'district':t['district_name'],'state':t['state_name'],'course_count':courses['n'],'training_capacity':courses['seats'],'trainer_count':trainer_count,'equipment_count':equipment_count,'placed_students':placements['placed'],'placement_openings':placements['openings'],'market_openings':sum(x['openings'] for x in market.get('role_demand',[])),'engine_version':ENGINE_VERSION,'provenance':market['provenance']}

@app.get('/api/provider/courses')
def provider_courses(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn()
    rows=c.execute('SELECT id,name,duration_weeks,seats,active FROM courses WHERE tenant_id=? AND provider_id=? ORDER BY name',(t['id'],p['id'])).fetchall()
    out=[]
    for r in rows:
        skills=c.execute('SELECT sk.id,sk.name,cs.taught_level FROM course_skills cs JOIN skills sk ON sk.id=cs.skill_id WHERE cs.course_id=? ORDER BY sk.name',(r['id'],)).fetchall()
        out.append({**dict(r),'skills':[dict(x) for x in skills], 'status':'Active' if r['active'] else 'Inactive'})
    c.close(); return out

@app.post('/api/provider/courses')
def provider_course_create(x:ProviderCourseIn,t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); cid='provider-course-'+uuid.uuid4().hex[:12]
    valid=[sid for sid in x.skill_ids if c.execute('SELECT id FROM skills WHERE id=?',(sid,)).fetchone()]
    c.execute('INSERT INTO courses(id,tenant_id,provider_id,name,duration_weeks,seats,active,created_at) VALUES(?,?,?,?,?,?,1,?)',(cid,t['id'],p['id'],x.name.strip(),x.duration_weeks,x.seats,now()))
    for sid in valid: c.execute('INSERT OR IGNORE INTO course_skills(course_id,skill_id,taught_level) VALUES(?,?,2)',(cid,sid))
    log(c,t['id'],'training_provider','course_created','course',cid,x.model_dump()); c.commit(); c.close(); return {'id':cid,'status':'created'}

@app.put('/api/provider/courses/{course_id}')
def provider_course_update(course_id:str,x:ProviderCourseIn,t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); ok=c.execute('SELECT id FROM courses WHERE id=? AND tenant_id=? AND provider_id=?',(course_id,t['id'],p['id'])).fetchone()
    if not ok: c.close(); raise HTTPException(404,'Course not found in your centre')
    c.execute('UPDATE courses SET name=?,duration_weeks=?,seats=? WHERE id=?',(x.name.strip(),x.duration_weeks,x.seats,course_id))
    c.execute('DELETE FROM course_skills WHERE course_id=?',(course_id,))
    for sid in x.skill_ids:
        if c.execute('SELECT id FROM skills WHERE id=?',(sid,)).fetchone(): c.execute('INSERT OR IGNORE INTO course_skills(course_id,skill_id,taught_level) VALUES(?,?,2)',(course_id,sid))
    log(c,t['id'],'training_provider','course_updated','course',course_id,x.model_dump()); c.commit(); c.close(); return {'status':'updated'}

@app.get('/api/provider/skills')
def provider_skills(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn()
    rows=c.execute('''SELECT sk.id,sk.name,sk.category,COALESCE(SUM(c.seats),0) training_supply,
      COUNT(DISTINCT c.id) course_count FROM skills sk LEFT JOIN course_skills cs ON cs.skill_id=sk.id
      LEFT JOIN courses c ON c.id=cs.course_id AND c.tenant_id=? AND c.provider_id=? AND c.active=1 GROUP BY sk.id ORDER BY training_supply DESC,sk.name''',(t['id'],p['id'])).fetchall()
    snap=core_engine_snapshot(t['id']); dm={x['skill_id']:x for x in snap.get('skill_demand',[])}
    out=[]
    for r in rows:
        d=dm.get(r['id'],{}); demand=int(d.get('openings',0) or 0); supply=int(r['training_supply'] or 0); gap=max(demand-supply,0)
        out.append({**dict(r),'demand_openings':demand,'demand_score':d.get('demand_score',0),'growth_pct':d.get('growth_pct',0),'gap':gap,'priority':'Critical' if demand and gap>0 and gap>=max(10,demand*0.35) else ('High' if gap>0 else 'Covered'),'action':'Increase capacity' if gap>0 else 'Maintain coverage'})
    c.close(); return {'skills':out,'district':t['district_name'],'provider':p}

@app.get('/api/provider/capacity')
def provider_capacity(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); courses=c.execute('SELECT id,name,seats,active FROM courses WHERE tenant_id=? AND provider_id=? ORDER BY name',(t['id'],p['id'])).fetchall()
    snap=core_engine_snapshot(t['id']); total=max(1,sum(int(x['openings']) for x in snap.get('role_demand',[])))
    out=[]
    for x in courses:
        health=next((h for h in snap.get('course_health',[]) if h['course_id']==x['id']),None); demand=total if snap.get('role_demand') else 0
        util=round(min(100,(demand/max(int(x['seats']),1))*100)) if demand else 0
        out.append({**dict(x),'demand_openings':demand,'utilization':util,'health_score':health['health_score'] if health else 0,'recommendation':('Increase seats by '+str(max(10,round(demand*0.25))) if demand>int(x['seats']) else ('Review / reduce new intake' if demand and int(x['seats'])>demand*2 else 'Maintain capacity'))})
    total_capacity=sum(int(x['seats']) for x in courses if x['active']); openings=sum(int(x['openings']) for x in snap.get('role_demand',[])); c.close()
    return {'courses':out,'total_capacity':total_capacity,'market_openings':openings,'capacity_gap':max(openings-total_capacity,0),'provider':p}

@app.get('/api/provider/resources')
def provider_resources(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); trainers=[dict(x) for x in c.execute('SELECT * FROM provider_trainers WHERE tenant_id=? AND provider_id=? ORDER BY name',(t['id'],p['id'])).fetchall()]; equipment=[dict(x) for x in c.execute('SELECT * FROM provider_equipment WHERE tenant_id=? AND provider_id=? ORDER BY name',(t['id'],p['id'])).fetchall()]; c.close(); return {'trainers':trainers,'equipment':equipment,'provider':p}

@app.post('/api/provider/trainers')
def provider_trainer_create(x:ProviderTrainerIn,t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); tid='trainer-'+uuid.uuid4().hex[:12]; c.execute('INSERT INTO provider_trainers(id,tenant_id,provider_id,name,specialization,skills,experience_years,availability,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,t['id'],p['id'],x.name.strip(),x.specialization,x.skills,x.experience_years,x.availability,'Active',now(),now())); log(c,t['id'],'training_provider','trainer_created','trainer',tid,x.model_dump()); c.commit(); c.close(); return {'id':tid,'status':'created'}

@app.post('/api/provider/equipment')
def provider_equipment_create(x:ProviderEquipmentIn,t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); eid='equipment-'+uuid.uuid4().hex[:12]; gap=max(x.required_qty-x.available_qty,0); status='Shortage' if gap else ('High utilization' if x.utilization_pct>=85 else 'Adequate'); c.execute('INSERT INTO provider_equipment(id,tenant_id,provider_id,name,required_qty,available_qty,utilization_pct,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,t['id'],p['id'],x.name.strip(),x.required_qty,x.available_qty,x.utilization_pct,status,now(),now())); log(c,t['id'],'training_provider','equipment_created','equipment',eid,x.model_dump()); c.commit(); c.close(); return {'id':eid,'status':'created'}

@app.get('/api/provider/placements')
def provider_placements(t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); rows=c.execute('SELECT pp.*,c.name course_name FROM provider_placements pp JOIN courses c ON c.id=pp.course_id WHERE pp.tenant_id=? AND pp.provider_id=? ORDER BY placement_date DESC,created_at DESC',(t['id'],p['id'])).fetchall(); c.close(); return [dict(x) for x in rows]

@app.post('/api/provider/placements')
def provider_placement_create(x:ProviderPlacementIn,t=Depends(require_role('TRAINING_PROVIDER'))):
    p=provider_scope(t); c=conn(); ok=c.execute('SELECT id FROM courses WHERE id=? AND tenant_id=? AND provider_id=?',(x.course_id,t['id'],p['id'])).fetchone()
    if not ok: c.close(); raise HTTPException(403,'Course does not belong to your centre')
    pid='placement-'+uuid.uuid4().hex[:12]; c.execute('INSERT INTO provider_placements(id,tenant_id,provider_id,course_id,employer_name,students_placed,openings,placement_date,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,t['id'],p['id'],x.course_id,x.employer_name.strip(),x.students_placed,x.openings,x.placement_date,x.status,x.notes,now(),now())); log(c,t['id'],'training_provider','placement_recorded','placement',pid,x.model_dump()); c.commit(); c.close(); return {'id':pid,'status':'created'}

@app.post('/api/industry/companies')
def company_create(x:CompanyIn,t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid='cmp-'+uuid.uuid4().hex[:10]; c.execute('INSERT INTO companies(id,tenant_id,name,sector,size,website,created_at) VALUES(?,?,?,?,?,?,?)',(cid,t['id'],x.name,x.sector,x.size,x.website,now())); log(c,t['id'],'admin','company_created','company',cid,x.model_dump()); c.commit(); c.close(); return {'id':cid,**x.model_dump()}

class JobIn(BaseModel): company_id:str; role_id:str; title:str; openings:int=Field(ge=1); salary_min:int=0; salary_max:int=0; location_text:str='' 
@app.post('/api/industry/jobs')
def create_job(x:JobIn,t=Depends(require_role('EMPLOYER'))):
    c=conn(); ok=c.execute('SELECT id FROM companies WHERE id=? AND tenant_id=?',(x.company_id,t['id'])).fetchone()
    if not ok: raise HTTPException(403,'Company does not belong to active district')
    jid='job-'+uuid.uuid4().hex[:10]; c.execute('INSERT INTO jobs(id,tenant_id,company_id,role_id,title,openings,location_text,salary_min,salary_max,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,t['id'],x.company_id,x.role_id,x.title,x.openings,x.location_text,x.salary_min,x.salary_max,now())); log(c,t['id'],'employer','job_created','job',jid,x.model_dump()); c.commit(); c.close(); return {'id':jid,'status':'created'}

@app.get('/api/employer/company')
def employer_company(t=Depends(require_role('EMPLOYER'))):
    c=conn(); company=c.execute('SELECT co.*,d.name district_name,s.name state_name FROM companies co JOIN tenants tt ON tt.id=co.tenant_id JOIN districts d ON d.id=tt.district_id JOIN states s ON s.id=d.state_id WHERE co.id=? AND co.tenant_id=?',(t['organization_id'],t['id'])).fetchone()
    if not company: c.close(); raise HTTPException(404,'Employer company not found')
    jobs=c.execute('SELECT COUNT(*) n,COALESCE(SUM(openings),0) openings FROM jobs WHERE company_id=? AND tenant_id=? AND status="open"',(t['organization_id'],t['id'])).fetchone()
    commitments=c.execute('SELECT COUNT(*) n FROM employer_commitments WHERE company_id=? AND tenant_id=? AND status="active"',(t['organization_id'],t['id'])).fetchone()['n']
    feedback=c.execute('SELECT COUNT(*) n FROM employer_feedback WHERE company_id=? AND tenant_id=?',(t['organization_id'],t['id'])).fetchone()['n']
    c.close(); return {**dict(company),'open_positions':jobs['n'],'openings':jobs['openings'],'active_commitments':commitments,'feedback_count':feedback,'candidates_matched':0}

class EmployerCompanyUpdate(BaseModel): name:str; sector:str; size:str; website:str=''
@app.put('/api/employer/company')
def employer_company_update(x:EmployerCompanyUpdate,t=Depends(require_role('EMPLOYER'))):
    c=conn(); ok=c.execute('SELECT id FROM companies WHERE id=? AND tenant_id=?',(t['organization_id'],t['id'])).fetchone()
    if not ok: c.close(); raise HTTPException(404,'Employer company not found')
    c.execute('UPDATE companies SET name=?,sector=?,size=?,website=? WHERE id=? AND tenant_id=?',(x.name.strip(),x.sector.strip(),x.size.strip(),x.website.strip(),t['organization_id'],t['id']))
    log(c,t['id'],'employer','company_updated','company',t['organization_id'],x.model_dump()); c.commit(); c.close(); return {'status':'updated'}

@app.get('/api/employer/dashboard')
def employer_dashboard(t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid=t['organization_id']
    jobs=c.execute('SELECT COUNT(*) n,COALESCE(SUM(openings),0) openings FROM jobs WHERE tenant_id=? AND company_id=? AND status="open"',(t['id'],cid)).fetchone()
    closed=c.execute('SELECT COUNT(*) n FROM jobs WHERE tenant_id=? AND company_id=? AND status!="open"',(t['id'],cid)).fetchone()['n']
    invites=c.execute('SELECT COUNT(*) n FROM employment_invites WHERE tenant_id=? AND company_id=?',(t['id'],cid)).fetchone()['n']
    hired=c.execute('SELECT COUNT(*) n FROM employment_invites WHERE tenant_id=? AND company_id=? AND status IN ("hired","joined")',(t['id'],cid)).fetchone()['n']
    commitments=c.execute('SELECT COUNT(*) n FROM employer_commitments WHERE tenant_id=? AND company_id=? AND status="active"',(t['id'],cid)).fetchone()['n']
    feedback=c.execute('SELECT COUNT(*) n FROM employer_feedback WHERE tenant_id=? AND company_id=?',(t['id'],cid)).fetchone()['n']
    matches=0; students=c.execute('SELECT id FROM students WHERE tenant_id=?',(t['id'],)).fetchall(); job_rows=c.execute('SELECT id,role_id FROM jobs WHERE tenant_id=? AND company_id=? AND status="open"',(t['id'],cid)).fetchall()
    for j in job_rows:
        req=c.execute('SELECT skill_id,weight FROM role_skills WHERE role_id=?',(j['role_id'],)).fetchall(); den=sum(r['weight'] for r in req) or 1
        for st in students:
            lv={x['skill_id']:x['level'] for x in c.execute('SELECT skill_id,level FROM student_skills WHERE student_id=?',(st['id'],)).fetchall()}; score=round(sum(r['weight'] for r in req if lv.get(r['skill_id'],0)>=2)/den*100)
            if score>=50: matches+=1
    alerts=[]
    if jobs['openings'] and matches < jobs['openings']: alerts.append({'type':'critical','title':'Candidate shortage','detail':f'{jobs["openings"]} open positions but only {matches} candidate/job matches at 50%+ skill alignment.','cta':'Review Candidate Pool','page':'candidates'})
    if commitments and hired < jobs['openings']: alerts.append({'type':'normal','title':'Hiring commitments need progress','detail':f'{commitments} active commitment(s) and {hired} confirmed hires.','cta':'Open Employment Commitments','page':'commitments'})
    if feedback==0: alerts.append({'type':'normal','title':'Close the feedback loop','detail':'No employer feedback has been logged for this company yet.','cta':'Submit Employer Feedback','page':'feedback'})
    c.close(); return {'open_positions':jobs['n'],'openings':jobs['openings'],'closed_jobs':closed,'matches':matches,'candidates_matched':matches,'invited':invites,'hired':hired,'commitments':commitments,'feedback_count':feedback,'alerts':alerts}

@app.get('/api/employer/jobs')
def employer_jobs(t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid=t['organization_id']; rows=c.execute('SELECT j.*,r.name role_name FROM jobs j JOIN roles r ON r.id=j.role_id WHERE j.tenant_id=? AND j.company_id=? ORDER BY CASE WHEN j.status="open" THEN 0 ELSE 1 END,j.created_at DESC',(t['id'],cid)).fetchall(); stats=c.execute('SELECT COUNT(*) n,COALESCE(SUM(openings),0) openings FROM jobs WHERE tenant_id=? AND company_id=? AND status="open"',(t['id'],cid)).fetchone(); closed=c.execute('SELECT COUNT(*) n FROM jobs WHERE tenant_id=? AND company_id=? AND status!="open"',(t['id'],cid)).fetchone()['n']; c.close(); return {'company':{'id':cid},'jobs':[dict(r) for r in rows],'open_positions':stats['n'],'openings':stats['openings'],'closed_jobs':closed,'matches':0}

@app.put('/api/employer/jobs/{job_id}')
def employer_job_update(job_id:str,payload:dict,t=Depends(require_role('EMPLOYER'))):
    c=conn(); ok=c.execute('SELECT id,title,openings,location_text,salary_min,salary_max,status,role_id FROM jobs WHERE id=? AND tenant_id=? AND company_id=?',(job_id,t['id'],t['organization_id'])).fetchone()
    if not ok: c.close(); raise HTTPException(404,'Job not found for employer')
    status=(payload.get('status') or ok['status']).strip().lower()
    if status not in {'open','closed'}: c.close(); raise HTTPException(400,'Job status must be open or closed')
    title=str(payload.get('title',ok['title']) or '').strip()
    openings=int(payload.get('openings',ok['openings']) or 0)
    location_text=str(payload.get('location_text',ok['location_text'] or '') or '').strip()
    salary_min=int(payload.get('salary_min',ok['salary_min'] or 0) or 0)
    salary_max=int(payload.get('salary_max',ok['salary_max'] or 0) or 0)
    if not title: c.close(); raise HTTPException(400,'Job title is required')
    if openings<1: c.close(); raise HTTPException(400,'Vacancies must be at least 1')
    if salary_min<0 or salary_max<0: c.close(); raise HTTPException(400,'Salary cannot be negative')
    if salary_max and salary_min>salary_max: c.close(); raise HTTPException(400,'Maximum salary must be greater than or equal to minimum salary')
    c.execute('UPDATE jobs SET status=?,title=?,openings=?,location_text=?,salary_min=?,salary_max=? WHERE id=? AND tenant_id=? AND company_id=?',(status,title,openings,location_text,salary_min,salary_max,job_id,t['id'],t['organization_id']))
    log(c,t['id'],'employer','job_updated','job',job_id,{'status':status,'title':title,'openings':openings,'location_text':location_text,'salary_min':salary_min,'salary_max':salary_max})
    c.commit(); c.close(); return {'status':'updated'}

@app.get('/api/employer/skill-requirements')
def employer_skill_requirements(t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid=t['organization_id']
    jobs=c.execute('SELECT id,role_id,openings FROM jobs WHERE tenant_id=? AND company_id=? AND status="open"',(t['id'],cid)).fetchall()
    agg={}
    for j in jobs:
        for r in c.execute('SELECT rs.skill_id,rs.weight,rs.required_level,sk.name,sk.category FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=?',(j['role_id'],)).fetchall():
            x=agg.setdefault(r['skill_id'],{'skill_id':r['skill_id'],'name':r['name'],'category':r['category'],'openings':0,'jobs':0,'weight':0,'required_level':1})
            x['openings']+=j['openings']; x['jobs']+=1; x['weight']=max(x['weight'],int(r['weight'])); x['required_level']=max(x['required_level'],int(r['required_level']))
    overrides={r['skill_id']:dict(r) for r in c.execute('SELECT skill_id,importance,proficiency_level,notes FROM employer_skill_requirements WHERE tenant_id=? AND company_id=?',(t['id'],cid)).fetchall()}
    # Include employer-added requirements even when they are not present in an active job yet.
    if overrides:
        for r in c.execute('SELECT sk.id skill_id,sk.name,sk.category FROM skills sk WHERE sk.id IN ('+','.join('?' for _ in overrides)+')', tuple(overrides.keys())).fetchall():
            x=agg.setdefault(r['skill_id'],{'skill_id':r['skill_id'],'name':r['name'],'category':r['category'],'openings':0,'jobs':0,'weight':0,'required_level':1})
            x['custom']=True
    supply={}
    for r in c.execute('SELECT cs.skill_id,COALESCE(SUM(c.seats),0) seats FROM course_skills cs JOIN courses c ON c.id=cs.course_id WHERE c.tenant_id=? AND c.active=1 GROUP BY cs.skill_id',(t['id'],)).fetchall(): supply[r['skill_id']]=int(r['seats'])
    out=[]
    for x in agg.values():
        o=overrides.get(x['skill_id'],{}); x['importance']=o.get('importance') or ('Critical' if x['weight']>=4 or x['openings']>=20 else ('High' if x['weight']>=3 or x['openings']>=10 else 'Important')); x['proficiency_level']=int(o.get('proficiency_level') or x['required_level']); x['notes']=o.get('notes') or ''
        x['training_supply']=supply.get(x['skill_id'],0); x['coverage']=round(x['training_supply']/x['openings']*100) if x['openings'] else 0; x['action']='Request training expansion' if x['training_supply']<x['openings'] else ('Employer-defined requirement' if x.get('custom') else 'Maintain + validate'); out.append(x)
    out.sort(key=lambda z:(-z['weight'],-z['openings'],z['name']))
    c.close(); return {'open_jobs':len(jobs),'openings':sum(x['openings'] for x in jobs),'skills':out,'critical_count':sum(1 for x in out if x['importance']=='Critical')}

class EmployerSkillRequirementIn(BaseModel):
    skill_id:str; importance:str='High'; proficiency_level:int=Field(2,ge=1,le=3); notes:str=''

@app.post('/api/employer/skill-requirements')
def employer_skill_requirement_save(x:EmployerSkillRequirementIn,t=Depends(require_role('EMPLOYER'))):
    if x.importance not in {'Critical','High','Important','Medium'}: raise HTTPException(400,'Importance must be Critical, High, Important or Medium')
    c=conn();
    if not c.execute('SELECT id FROM companies WHERE id=? AND tenant_id=?',(t['organization_id'],t['id'])).fetchone(): c.close(); raise HTTPException(404,'Employer company not found')
    if not c.execute('SELECT id FROM skills WHERE id=?',(x.skill_id,)).fetchone(): c.close(); raise HTTPException(404,'Skill not found')
    c.execute('INSERT INTO employer_skill_requirements(company_id,tenant_id,skill_id,importance,proficiency_level,notes,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(company_id,skill_id) DO UPDATE SET importance=excluded.importance,proficiency_level=excluded.proficiency_level,notes=excluded.notes,updated_at=excluded.updated_at',(t['organization_id'],t['id'],x.skill_id,x.importance,x.proficiency_level,x.notes.strip(),now())); log(c,t['id'],'employer','skill_requirement_updated','skill',x.skill_id,x.model_dump()); c.commit(); c.close(); return {'status':'saved'}

@app.get('/api/employer/training-partnership')
def employer_training_partnership(t=Depends(require_role('EMPLOYER'))):
    c=conn(); rows=c.execute('SELECT etr.*,sk.name skill_name FROM employer_training_requests etr LEFT JOIN skills sk ON sk.id=etr.skill_id WHERE etr.tenant_id=? AND etr.company_id=? ORDER BY etr.created_at DESC',(t['id'],t['organization_id'])).fetchall(); providers=c.execute('SELECT COUNT(*) n FROM training_providers WHERE tenant_id=?',(t['id'],)).fetchone()['n']; c.close(); return {'requests':[dict(x) for x in rows],'pending':sum(1 for x in rows if x['status']=='pending'),'actioned':sum(1 for x in rows if x['status']=='actioned'),'providers':providers}

class TrainingRequestIn(BaseModel): request_type:str; skill_id:Optional[str]=None; title:str; details:str
@app.post('/api/employer/training-partnership')
def employer_training_partnership_create(x:TrainingRequestIn,t=Depends(require_role('EMPLOYER'))):
    c=conn();
    if not c.execute('SELECT id FROM companies WHERE id=? AND tenant_id=?',(t['organization_id'],t['id'])).fetchone(): c.close(); raise HTTPException(404,'Employer company not found')
    if x.skill_id and not c.execute('SELECT id FROM skills WHERE id=?',(x.skill_id,)).fetchone(): c.close(); raise HTTPException(404,'Skill not found')
    rid='tp-'+uuid.uuid4().hex[:12]; c.execute('INSERT INTO employer_training_requests(id,tenant_id,company_id,request_type,skill_id,title,details,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,t['id'],t['organization_id'],x.request_type.strip(),x.skill_id,x.title.strip(),x.details.strip(),'pending',now(),now())); log(c,t['id'],'employer','training_partnership_requested','training_request',rid,x.model_dump()); c.commit(); c.close(); return {'id':rid,'status':'created'}

@app.get('/api/employer/hiring-outcomes')
def employer_hiring_outcomes(t=Depends(require_role('EMPLOYER'))):
    c=conn(); cid=t['organization_id']
    inv=c.execute('SELECT ei.*,s.name student_name,s.qualification,j.title job_title,j.openings job_openings FROM employment_invites ei JOIN students s ON s.id=ei.student_id LEFT JOIN jobs j ON j.id=ei.job_id WHERE ei.tenant_id=? AND ei.company_id=? ORDER BY ei.created_at DESC',(t['id'],cid)).fetchall()
    commits=c.execute('SELECT COALESCE(SUM(committed_slots),0) committed,COALESCE(SUM(hired_slots),0) hired FROM employer_commitments WHERE tenant_id=? AND company_id=? AND status IN ("active","fulfilled")',(t['id'],cid)).fetchone()
    openpos=c.execute('SELECT COALESCE(SUM(openings),0) n FROM jobs WHERE tenant_id=? AND company_id=? AND status="open"',(t['id'],cid)).fetchone()['n']
    rows=[dict(x) for x in inv]
    funnel={k:sum(1 for x in rows if x['status'] in vals) for k,vals in {'invited':{'invited','interviewed','offered','hired','joined'},'interviewed':{'interviewed','offered','hired','joined'},'offered':{'offered','hired','joined'},'hired':{'hired','joined'},'joined':{'joined'}}.items()}
    c.close(); return {'open_positions':openpos,'invited':funnel['invited'],'interviewed':funnel['interviewed'],'offered':funnel['offered'],'hired':funnel['hired'],'joined':funnel['joined'],'commitment_fulfilment':round((commits['hired']/commits['committed']*100) if commits['committed'] else 0),'commitment_committed':commits['committed'],'commitment_hired':commits['hired'],'invitations':rows,'retention_data_available':False,'retention_note':'Retention and salary outcomes require post-joining employer outcome capture in a production deployment.'}

class InviteStatusIn(BaseModel): status:str
@app.put('/api/employment/invites/{invite_id}')
def employment_invite_update(invite_id:str,x:InviteStatusIn,t=Depends(require_role('EMPLOYER'))):
    status=x.status.strip().lower()
    if status not in {'invited','interviewed','offered','hired','joined'}: raise HTTPException(400,'Invalid hiring status')
    c=conn(); ok=c.execute('SELECT id FROM employment_invites WHERE id=? AND tenant_id=? AND company_id=?',(invite_id,t['id'],t['organization_id'])).fetchone()
    if not ok: c.close(); raise HTTPException(404,'Invitation not found')
    c.execute('UPDATE employment_invites SET status=? WHERE id=? AND tenant_id=? AND company_id=?',(status,invite_id,t['id'],t['organization_id'])); log(c,t['id'],'employer','interview_status_updated','employment_invite',invite_id,{'status':status}); c.commit(); c.close(); return {'status':'updated'}

@app.get('/api/industry/demand')
def demand(t=Depends(tenant_context)):
    c=conn(); rows=c.execute('SELECT r.id,r.name,COUNT(j.id) job_count,SUM(j.openings) openings FROM jobs j JOIN roles r ON r.id=j.role_id WHERE j.tenant_id=? AND j.status="open" GROUP BY r.id ORDER BY openings DESC',(t['id'],)).fetchall();
    # supply by courses
    out=[]
    for r in rows:
        rs=c.execute('SELECT sk.id,sk.name FROM role_skills rsk JOIN skills sk ON sk.id=rsk.skill_id WHERE rsk.role_id=?',(r['id'],)).fetchall(); out.append({**dict(r),'skills':[dict(x) for x in rs]})
    c.close(); return {'tenant':t,'roles':out}

@app.get('/api/training/providers')
def providers(t=Depends(tenant_context)):
    c=conn(); p=c.execute('SELECT tp.*,COUNT(c.id) course_count,COALESCE(SUM(c.seats),0) seats FROM training_providers tp LEFT JOIN courses c ON c.provider_id=tp.id WHERE tp.tenant_id=? GROUP BY tp.id ORDER BY tp.name',(t['id'],)).fetchall(); c.close(); return [dict(x) for x in p]

@app.get('/api/district/skill-academy')
def academy(t=Depends(tenant_context)):
    c=conn(); rows=c.execute('SELECT c.id,c.name, c.duration_weeks,c.seats,tp.name provider_name, GROUP_CONCAT(sk.name, ", ") skills FROM courses c JOIN training_providers tp ON tp.id=c.provider_id LEFT JOIN course_skills cs ON cs.course_id=c.id LEFT JOIN skills sk ON sk.id=cs.skill_id WHERE c.tenant_id=? GROUP BY c.id ORDER BY c.name',(t['id'],)).fetchall();
    c.close(); return {'district':t['district_name'],'state':t['state_name'],'courses':[dict(x) for x in rows]}

@app.get('/api/district/alignment')
def alignment(t=Depends(tenant_context)):
    c=conn(); demand_rows=c.execute('SELECT r.id,r.name,SUM(j.openings) openings FROM jobs j JOIN roles r ON r.id=j.role_id WHERE j.tenant_id=? AND j.status="open" GROUP BY r.id',(t['id'],)).fetchall(); total_open=sum(x['openings'] for x in demand_rows) or 1
    out=[]
    for x in demand_rows:
        req=c.execute('SELECT cs.course_id,AVG(CASE WHEN cs.taught_level>=rs.required_level THEN 100 ELSE cs.taught_level*100.0/rs.required_level END) score FROM role_skills rs JOIN course_skills cs ON cs.skill_id=rs.skill_id JOIN courses co ON co.id=cs.course_id WHERE rs.role_id=? AND co.tenant_id=? GROUP BY cs.course_id',(x['id'],t['id'])).fetchall()
        score=round(sum(r['score'] for r in req)/len(req)) if req else 0
        out.append({'role':x['name'],'openings':x['openings'],'demand_share':round(x['openings']/total_open*100),'alignment_score':score,'action':'Scale seats' if score>=75 and x['openings']>=5 else ('Upgrade curriculum' if score else 'Create course')})
    c.close(); return out

class FeedbackIn(BaseModel): company_id:str; role_id:Optional[str]=None; rating:int=Field(ge=1,le=5); missing_skills:list[str]=[]; comment:str=''
@app.get('/api/employer/feedback')
def feedback_history(t=Depends(require_role('EMPLOYER'))):
    c=conn()
    rows=c.execute('SELECT ef.*,co.name company_name,r.name role_name FROM employer_feedback ef JOIN companies co ON co.id=ef.company_id LEFT JOIN roles r ON r.id=ef.role_id WHERE ef.tenant_id=? AND (? IS NULL OR ef.company_id=?) ORDER BY ef.created_at DESC',(t['id'],t.get('organization_id') if t.get('role')=='EMPLOYER' else None,t.get('organization_id') if t.get('role')=='EMPLOYER' else None)).fetchall()
    c.close()
    return [dict(x) for x in rows]

@app.post('/api/employer/feedback')
def feedback(x:FeedbackIn,t=Depends(require_role('EMPLOYER'))):
    c=conn(); ok=c.execute('SELECT id FROM companies WHERE id=? AND tenant_id=?',(x.company_id,t['id'])).fetchone();
    if not ok: raise HTTPException(403,'Company is outside active district')
    c.execute('INSERT INTO employer_feedback(tenant_id,company_id,role_id,rating,missing_skills,comment,created_at) VALUES(?,?,?,?,?,?,?)',(t['id'],x.company_id,x.role_id,x.rating,','.join(x.missing_skills),x.comment,now())); log(c,t['id'],'employer','feedback_submitted','company',x.company_id,x.model_dump()); c.commit(); c.close(); return {'status':'saved'}

@app.get('/api/industry/radar')
def radar(t=Depends(tenant_context)):
    snap=core_engine_snapshot(t['id']); signals=[]
    for x in snap['skill_demand']:
        if x['openings']<=0: continue
        signals.append({**x,'signal':'Rising' if x['growth_pct']>0 else 'Watch','change_pct':x['growth_pct']})
    return {'tenant':t,'signals':signals,'engine_version':ENGINE_VERSION,'provenance':snap['provenance']}

@app.get('/api/industry/course-alerts')
def course_alerts(t=Depends(tenant_context)):
    snap=core_engine_snapshot(t['id']); return [{**x,'alignment':x['health_score'],'action':x['action']} for x in snap['course_health']]

@app.get('/api/curriculum/{course_id}')
def curriculum(course_id:str,t=Depends(tenant_context)):
    snap=core_engine_snapshot(t['id']); health=next((x for x in snap['course_health'] if x['course_id']==course_id),None)
    c=conn(); course=c.execute('SELECT id,name,seats FROM courses WHERE id=? AND tenant_id=?',(course_id,t['id'])).fetchone();
    if not course: c.close(); raise HTTPException(404,'Course not found in active district')
    taught=[dict(r) for r in c.execute('SELECT sk.id,sk.name,cs.taught_level FROM course_skills cs JOIN skills sk ON sk.id=cs.skill_id WHERE cs.course_id=?',(course_id,)).fetchall()]; c.close()
    additions=[]
    if health:
        additions=[{'name':x,'reason':'High local demand but not currently covered by this course.'} for x in health.get('missing_skills',[])]
    return {'course':dict(course),'current_modules':taught,'recommended_additions':additions,'recommended_practical_hours_increase':20 if additions else 0,'course_health':health,'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'assumptions':'Derived from the shared local labour-demand and training-supply engine.'}


@app.get('/api/district/admin-dashboard')
def district_admin_dashboard(t=Depends(require_role('DSC_ADMIN'))):
    snap=core_engine_snapshot(t['id'])
    c=conn()
    companies=c.execute('SELECT COUNT(*) FROM companies WHERE tenant_id=? AND status="active"',(t['id'],)).fetchone()[0]
    jobs=c.execute('SELECT COUNT(*) postings,COALESCE(SUM(openings),0) openings FROM jobs WHERE tenant_id=? AND status="open"',(t['id'],)).fetchone()
    providers=c.execute('SELECT COUNT(*) FROM training_providers WHERE tenant_id=?',(t['id'],)).fetchone()[0]
    cap=c.execute('SELECT COALESCE(SUM(seats),0) FROM courses WHERE tenant_id=? AND active=1',(t['id'],)).fetchone()[0]
    trainers=c.execute('SELECT COUNT(*) FROM provider_trainers WHERE tenant_id=? AND status="Active"',(t['id'],)).fetchone()[0]
    equipment_gap=c.execute('SELECT COALESCE(SUM(required_qty-available_qty),0) FROM provider_equipment WHERE tenant_id=? AND required_qty>available_qty',(t['id'],)).fetchone()[0]
    commitments=c.execute('SELECT COUNT(*) n,COALESCE(SUM(committed_slots),0) committed,COALESCE(SUM(hired_slots),0) hired FROM employer_commitments WHERE tenant_id=? AND status IN ("active","fulfilled")',(t['id'],)).fetchone()
    feedback=c.execute('SELECT COUNT(*) FROM employer_feedback WHERE tenant_id=?',(t['id'],)).fetchone()[0]
    placed=c.execute('SELECT COALESCE(SUM(students_placed),0) placed,COALESCE(SUM(openings),0) openings FROM provider_placements WHERE tenant_id=? AND status="Verified"',(t['id'],)).fetchone()
    c.close()
    critical=sorted(snap.get('skill_demand',[]),key=lambda x:(x.get('gap',0),x.get('openings',0)),reverse=True)[:5]
    return {'district':t['district_name'],'state':t['state_name'],'metrics':{'companies':companies,'job_postings':jobs['postings'],'openings':jobs['openings'],'providers':providers,'training_capacity':cap,'active_trainers':trainers,'equipment_gap_units':equipment_gap,'commitments':commitments['n'],'committed_slots':commitments['committed'],'hired_slots':commitments['hired'],'feedback_count':feedback,'placed_students':placed['placed'],'placement_openings':placed['openings']},'top_skills':critical,'course_health':snap.get('course_health',[])[:8],'recommendations':snap.get('recommendations',[]),'engine_version':ENGINE_VERSION,'provenance':snap['provenance']}

@app.get('/api/district/recruiters')
def district_recruiters(t=Depends(require_role('DSC_ADMIN'))):
    c=conn(); rows=c.execute('''SELECT co.id,co.name,co.sector,co.size,COUNT(j.id) open_postings,COALESCE(SUM(j.openings),0) openings,
      MAX(j.created_at) last_job FROM companies co LEFT JOIN jobs j ON j.company_id=co.id AND j.status='open'
      WHERE co.tenant_id=? AND co.status='active' GROUP BY co.id ORDER BY openings DESC,co.name''',(t['id'],)).fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/district/course-library')
def district_course_library(t=Depends(require_role('DSC_ADMIN'))):
    c=conn(); rows=c.execute('''SELECT c.id,c.name,c.duration_weeks,c.seats,c.active,tp.id provider_id,tp.name provider_name,tp.provider_type,
      COALESCE((SELECT SUM(pp.students_placed) FROM provider_placements pp WHERE pp.course_id=c.id AND pp.status='Verified'),0) placed_students
      FROM courses c JOIN training_providers tp ON tp.id=c.provider_id WHERE c.tenant_id=? ORDER BY c.name''',(t['id'],)).fetchall(); out=[]
    for r in rows:
        skills=c.execute('SELECT sk.id,sk.name,cs.taught_level FROM course_skills cs JOIN skills sk ON sk.id=cs.skill_id WHERE cs.course_id=? ORDER BY sk.name',(r['id'],)).fetchall()
        out.append({**dict(r),'status':'Active' if r['active'] else 'Inactive','skills':[dict(x) for x in skills]})
    c.close(); return out

@app.get('/api/district/guarantees')
def district_guarantees(t=Depends(require_role('DSC_ADMIN'))):
    c=conn(); rows=c.execute('''SELECT ec.*,co.name company_name,co.sector,r.name role_name,
      CASE WHEN ec.committed_slots=0 THEN 0 ELSE ROUND(ec.hired_slots*100.0/ec.committed_slots) END fulfilment_pct
      FROM employer_commitments ec JOIN companies co ON co.id=ec.company_id JOIN roles r ON r.id=ec.role_id
      WHERE ec.tenant_id=? ORDER BY CASE ec.status WHEN 'active' THEN 0 WHEN 'fulfilled' THEN 1 ELSE 2 END, ec.id''',(t['id'],)).fetchall(); c.close(); return [dict(r) for r in rows]

@app.put('/api/district/guarantees/{commitment_id}')
def district_guarantee_update(commitment_id:str,payload:dict,t=Depends(require_role('DSC_ADMIN'))):
    hired=max(int(payload.get('hired_slots',0)),0); status=payload.get('status')
    c=conn(); r=c.execute('SELECT * FROM employer_commitments WHERE id=? AND tenant_id=?',(commitment_id,t['id'])).fetchone()
    if not r: c.close(); raise HTTPException(404,'Employment commitment not found')
    if hired>r['committed_slots']: c.close(); raise HTTPException(400,'Hired slots cannot exceed committed slots')
    new_status=status or ('fulfilled' if hired==r['committed_slots'] else 'active')
    c.execute('UPDATE employer_commitments SET hired_slots=?,status=? WHERE id=? AND tenant_id=?',(hired,new_status,commitment_id,t['id']))
    log(c,t['id'],'dsc_admin','district_commitment_reviewed','commitment',commitment_id,{'hired_slots':hired,'status':new_status}); c.commit(); c.close(); return {'status':'updated','hired_slots':hired,'commitment_status':new_status}

@app.get('/api/district/feedback')
def district_feedback(t=Depends(require_role('DSC_ADMIN'))):
    c=conn(); rows=c.execute('''SELECT ef.*,co.name company_name,co.sector,r.name role_name,
      COALESCE(fr.status,'new') review_status,COALESCE(fr.admin_note,'') admin_note,fr.reviewed_at
      FROM employer_feedback ef JOIN companies co ON co.id=ef.company_id LEFT JOIN roles r ON r.id=ef.role_id
      LEFT JOIN feedback_reviews fr ON fr.feedback_id=ef.id AND fr.tenant_id=ef.tenant_id
      WHERE ef.tenant_id=? ORDER BY ef.created_at DESC''',(t['id'],)).fetchall(); c.close(); return [dict(r) for r in rows]

@app.put('/api/district/feedback/{feedback_id}/review')
def district_feedback_review(feedback_id:int,payload:dict,t=Depends(require_role('DSC_ADMIN'))):
    status=(payload.get('status') or 'reviewed').strip(); note=(payload.get('admin_note') or '').strip()
    if status not in {'new','reviewed','actioned','dismissed'}: raise HTTPException(400,'Invalid review status')
    c=conn(); ok=c.execute('SELECT id FROM employer_feedback WHERE id=? AND tenant_id=?',(feedback_id,t['id'])).fetchone()
    if not ok: c.close(); raise HTTPException(404,'Feedback not found')
    rid=f'feedback-review-{t["id"]}-{feedback_id}'
    c.execute('''INSERT INTO feedback_reviews(id,tenant_id,feedback_id,status,admin_note,reviewed_at,created_at) VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(tenant_id,feedback_id) DO UPDATE SET status=excluded.status,admin_note=excluded.admin_note,reviewed_at=excluded.reviewed_at''',(rid,t['id'],feedback_id,status,note,now(),now()))
    log(c,t['id'],'dsc_admin','feedback_reviewed','employer_feedback',str(feedback_id),{'status':status,'admin_note':note}); c.commit(); c.close(); return {'status':'saved'}

@app.get('/api/district/placements')
def district_placements(t=Depends(require_role('DSC_ADMIN'))):
    c=conn(); rows=c.execute('''SELECT pp.id,pp.employer_name,pp.students_placed,pp.openings,pp.placement_date,pp.status,pp.notes,
      c.name course_name,tp.name provider_name FROM provider_placements pp JOIN courses c ON c.id=pp.course_id JOIN training_providers tp ON tp.id=pp.provider_id
      WHERE pp.tenant_id=? ORDER BY pp.placement_date DESC,pp.created_at DESC''',(t['id'],)).fetchall()
    agg=c.execute('SELECT COALESCE(SUM(students_placed),0) placed,COALESCE(SUM(openings),0) openings,COUNT(*) records FROM provider_placements WHERE tenant_id=? AND status="Verified"',(t['id'],)).fetchone(); c.close()
    return {'items':[dict(r) for r in rows],'summary':dict(agg)}

@app.get('/api/district/plan')
def plan(t=Depends(tenant_context),target_year:int=2027):
    c=conn(); p=c.execute('SELECT plan_json,status FROM district_plans WHERE tenant_id=? AND target_year=?',(t['id'],target_year)).fetchone(); c.close()
    if p: return {'status':p['status'],**json.loads(p['plan_json'])}
    # build from current data
    snap=core_engine_snapshot(t['id']); total_capacity=sum(x['seats'] for x in snap['course_health']); total_demand=sum(x['openings'] for x in snap['role_demand'])
    actions=[]
    for r in snap['role_demand']:
        health=next((x for x in snap['course_health'] if x['course'].lower() in r['name'].lower()),None)
        actions.append({'role':r['name'],'demand_openings':r['openings'],'alignment':health['health_score'] if health else 0,'recommended_action':('Scale training / update curriculum' if r['openings']>0 and (health is None or health['health_score']<70) else 'Maintain aligned capacity')})
    p={'district':t['district_name'],'state':t['state_name'],'target_year':target_year,'current_training_capacity':total_capacity,'current_openings':total_demand,'capacity_gap':max(total_demand*2-total_capacity,0),'actions':actions,'recommendations':snap['recommendations'],'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'stakeholders':['District Skill Committee','Training Providers','Local Employers','Students / Job Seekers']}
    return {'status':'draft','generated':True,**p}

@app.post('/api/district/plan/save')
def plan_save(payload:dict,t=Depends(require_role('DSC_ADMIN'))):
    year=int(payload.get('target_year',2027)); body={k:v for k,v in payload.items() if k!='target_year'}; c=conn(); pid='plan-'+t['district_id']+'-'+str(year); c.execute('INSERT INTO district_plans(id,tenant_id,target_year,status,plan_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,plan_json=excluded.plan_json,updated_at=excluded.updated_at',(pid,t['id'],year,'saved',json.dumps(body),now(),now())); log(c,t['id'],'dsc_admin','district_plan_saved','district_plan',pid,body); c.commit(); c.close(); return {'status':'saved','plan_id':pid}

@app.get('/api/analytics/summary')
def summary(t=Depends(tenant_context)):
    c=conn(); vals={
      'companies':c.execute('SELECT COUNT(*) FROM companies WHERE tenant_id=?',(t['id'],)).fetchone()[0],
      'open_jobs':c.execute('SELECT COALESCE(SUM(openings),0) FROM jobs WHERE tenant_id=? AND status="open"',(t['id'],)).fetchone()[0],
      'training_providers':c.execute('SELECT COUNT(*) FROM training_providers WHERE tenant_id=?',(t['id'],)).fetchone()[0],
      'training_capacity':c.execute('SELECT COALESCE(SUM(seats),0) FROM courses WHERE tenant_id=? AND active=1',(t['id'],)).fetchone()[0],
      'students':c.execute('SELECT COUNT(*) FROM students WHERE tenant_id=?',(t['id'],)).fetchone()[0],
      'feedback_count':c.execute('SELECT COUNT(*) FROM employer_feedback WHERE tenant_id=?',(t['id'],)).fetchone()[0]
    }; c.close(); snap=core_engine_snapshot(t['id']); return {'tenant':t,**vals,'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'run_id':snap['run_id']}

@app.get('/api/roles')
def get_roles():
    c=conn(); rows=c.execute('SELECT * FROM roles ORDER BY name').fetchall(); c.close(); return [dict(x) for x in rows]
@app.get('/api/skills')
def get_skills():
    c=conn(); rows=c.execute('SELECT * FROM skills ORDER BY category,name').fetchall(); c.close(); return [dict(x) for x in rows]

@app.get('/api/admin/audit')
def audit(t=Depends(tenant_context),limit:int=50):
    c=conn(); rows=c.execute('SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id DESC LIMIT ?',(t['id'],limit)).fetchall(); c.close(); return [dict(x) for x in rows]


# ---------- Fully working student workflow endpoints ----------
def _current_student(c, tenant_id):
    st=c.execute('SELECT id,name,target_role,target_company FROM students WHERE tenant_id=? ORDER BY id LIMIT 1',(tenant_id,)).fetchone()
    if not st: raise HTTPException(404,'Student profile not found')
    return st

def _role_for(c, role_id=None, student=None):
    if role_id:
        r=c.execute('SELECT * FROM roles WHERE id=?',(role_id,)).fetchone()
        if r: return r
    if student:
        r=c.execute('SELECT * FROM roles WHERE name=?',(student['target_role'],)).fetchone()
        if r: return r
    return c.execute('SELECT * FROM roles ORDER BY name LIMIT 1').fetchone()

class PathGenerateIn(BaseModel):
    role_id: str
    market_district_id: Optional[str] = None

@app.post('/api/student/path-navigator/generate')
def generate_path(x:PathGenerateIn,t=Depends(require_role('STUDENT'))):
    c=conn(); st=_current_student(c,t['id']); role=_role_for(c,x.role_id,st)
    market_tid=market_tenant_id(x.market_district_id) or t['id']
    if not role: c.close(); raise HTTPException(404,'Target role not found')
    # Calculate the shared intelligence snapshot before opening a write transaction.
    engine=core_engine_snapshot(market_tid,st['id'])
    demand_map={x['skill_id']:x for x in engine.get('skill_demand',[])}
    # retire prior active paths but keep history
    c.execute('UPDATE learning_paths SET status="archived",updated_at=? WHERE tenant_id=? AND student_id=? AND status="active"',(now(),t['id'],st['id']))
    pid='path-'+uuid.uuid4().hex[:12]
    c.execute('INSERT INTO learning_paths(id,tenant_id,student_id,role_id,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(pid,t['id'],st['id'],role['id'],f"12-week path to {role['name']}",'active',now(),now()))
    req=c.execute('SELECT sk.id skill_id,sk.name,rs.required_level,rs.weight FROM role_skills rs JOIN skills sk ON sk.id=rs.skill_id WHERE rs.role_id=?',(role['id'],)).fetchall()
    current={r['skill_id']:r['level'] for r in c.execute('SELECT skill_id,level FROM student_skills WHERE student_id=?',(st['id'],)).fetchall()}
    req=sorted(req,key=lambda r:(-max(0,int(r['required_level'])-int(current.get(r['skill_id'],0))),-int(demand_map.get(r['skill_id'],{}).get('demand_score',0)),-float(r['weight']),-int(r['required_level'])))
    i=0
    for r in req:
        if current.get(r['skill_id'],0)>=r['required_level']: continue
        i += 1
        start=(i-1)*2+1; end=min(i*2,12)
        course=c.execute('SELECT c.id,c.name FROM courses c JOIN course_skills cs ON cs.course_id=c.id WHERE c.tenant_id=? AND cs.skill_id=? ORDER BY c.seats DESC,c.name LIMIT 1',(market_tid,r['skill_id'])).fetchone()
        projects={
          'python':'Build a data API and deploy it locally', 'java':'Build a REST service with tests', 'cloud':'Deploy a small application with cloud-style infrastructure',
          'sql':'Design a normalized database and write reporting queries', 'ai':'Build a small ML/AI feature with evaluation', 'docker':'Containerize your project and run it locally',
          'cyber':'Complete a secure API hardening lab', 'communication':'Deliver a 5-minute technical project presentation', 'ev':'Diagnose a simulated EV fault case',
          'bms':'Analyze a battery-management fault scenario', 'cnc':'Create a CNC production setup workflow', 'plc':'Build a PLC automation sequence', 'solar':'Design a solar installation plan',
          'welding':'Complete a welding quality-control practical', 'excel':'Build an operational dashboard in Excel'
        }
        c.execute('INSERT INTO learning_path_steps(id,path_id,step_no,week_start,week_end,skill_id,target_level,course_id,project,status) VALUES(?,?,?,?,?,?,?,?,?,?)',('step-'+uuid.uuid4().hex[:12],pid,i,start,end,r['skill_id'],r['required_level'],course['id'] if course else None,projects.get(r['skill_id'],f'Build one practical project using {r["name"]}'),'pending'))
    # Fill the remaining time with integrative milestones so every generated plan spans 12 weeks.
    milestones=[('integration','Build an employer-aligned end-to-end portfolio project',1),('interview','Run a mock interview using the target role skill checklist',2),('proof','Publish a proof-of-work update and refresh your resume',3)]
    used_weeks=i*2
    for label,project,marker in milestones:
        if used_weeks>=12: break
        i += 1; start=used_weeks+1; end=min(used_weeks+2,12); used_weeks=end
        # Reuse communication as the assessed milestone skill because completion is still measurable.
        skill_id='communication'; target=2; c.execute('INSERT INTO learning_path_steps(id,path_id,step_no,week_start,week_end,skill_id,target_level,course_id,project,status) VALUES(?,?,?,?,?,?,?,?,?,?)',('step-'+uuid.uuid4().hex[:12],pid,i,start,end,skill_id,target,None,project,'pending'))
    c.commit();
    payload=_path_response(c,pid,t,role)
    c.close(); return payload

def _path_response(c,pid,t,role):
    p=c.execute('SELECT * FROM learning_paths WHERE id=? AND tenant_id=?',(pid,t['id'])).fetchone()
    rows=c.execute('SELECT lps.*,sk.name skill_name,c.name course_name FROM learning_path_steps lps JOIN skills sk ON sk.id=lps.skill_id LEFT JOIN courses c ON c.id=lps.course_id WHERE lps.path_id=? ORDER BY step_no',(pid,)).fetchall()
    completed=sum(1 for x in rows if x['status']=='completed'); total=len(rows)
    snap=core_engine_snapshot(t['id']); return {'path_id':pid,'district':t['district_name'],'role':dict(role),'duration_weeks':12,'progress_pct':round(completed/total*100) if total else 100,'engine_version':ENGINE_VERSION,'provenance':snap['provenance'],'steps':[{'id':x['id'],'step':x['step_no'],'week_start':x['week_start'],'week_end':x['week_end'],'skill':x['skill_name'],'target_level':LEVEL_NAME[x['target_level']],'course_id':x['course_id'],'recommended_course':x['course_name'] or 'Project module','project':x['project'],'status':x['status'],'completed_at':x['completed_at']} for x in rows]}

@app.get('/api/student/path-navigator')
def get_path(role_id:Optional[str]=None,t=Depends(tenant_context)):
    c=conn(); st=_current_student(c,t['id']); active=c.execute('SELECT id,role_id FROM learning_paths WHERE tenant_id=? AND student_id=? AND status="active" ORDER BY updated_at DESC LIMIT 1',(t['id'],st['id'])).fetchone()
    if role_id:
        role=_role_for(c,role_id,st)
    else:
        role=_role_for(c,active['role_id'] if active else None,st)
    if active and (not role_id or active['role_id']==role['id']): payload=_path_response(c,active['id'],t,role); c.close(); return payload
    c.close()
    # Return a preview only; explicit POST creates the persisted path.
    return {'path_id':None,'district':t['district_name'],'role':dict(role),'duration_weeks':12,'progress_pct':0,'steps':[],'requires_generation':True,'message':'Choose Generate 12-week plan to persist the path.'}

@app.post('/api/student/path-navigator/steps/{step_id}/complete')
def complete_path_step(step_id:str,t=Depends(require_role('STUDENT'))):
    c=conn(); st=_current_student(c,t['id'])
    row=c.execute('SELECT lps.*,lp.student_id,lp.tenant_id,lp.role_id FROM learning_path_steps lps JOIN learning_paths lp ON lp.id=lps.path_id WHERE lps.id=? AND lp.tenant_id=? AND lp.student_id=?',(step_id,t['id'],st['id'])).fetchone()
    if not row: c.close(); raise HTTPException(404,'Path step not found')
    c.execute('UPDATE learning_path_steps SET status="completed",completed_at=? WHERE id=?',(now(),step_id))
    # Completing a verified practical milestone advances that skill to the target level.
    current=c.execute('SELECT level FROM student_skills WHERE student_id=? AND skill_id=?',(st['id'],row['skill_id'])).fetchone()
    if not current or current['level']<row['target_level']:
        score=LEVEL_SCORE[row['target_level']]
        c.execute('INSERT INTO student_skills(student_id,skill_id,level,score,source,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(student_id,skill_id) DO UPDATE SET level=excluded.level,score=excluded.score,source=excluded.source,updated_at=excluded.updated_at',(st['id'],row['skill_id'],row['target_level'],score,'path_milestone',now()))
        c.execute('INSERT INTO assessments(tenant_id,student_id,skill_id,level,score,source,created_at) VALUES(?,?,?,?,?,?,?)',(t['id'],st['id'],row['skill_id'],row['target_level'],score,'path_milestone',now()))
    c.execute('UPDATE learning_paths SET updated_at=? WHERE id=?',(now(),row['path_id']))
    log(c,t['id'],st['id'],'path_step_completed','learning_path_step',step_id,{'skill_id':row['skill_id'],'target_level':row['target_level']}); c.commit()
    role=c.execute('SELECT * FROM roles WHERE id=?',(row['role_id'],)).fetchone(); payload=_path_response(c,row['path_id'],t,role); c.close(); return payload

@app.get('/api/mentors/requests')
def mentor_requests(t=Depends(tenant_context)):
    c=conn(); st=_current_student(c,t['id']); rows=c.execute('SELECT mr.*,m.name mentor_name,m.job_title,m.company FROM mentorship_requests mr JOIN mentors m ON m.id=mr.mentor_id WHERE mr.tenant_id=? AND mr.student_id=? ORDER BY mr.created_at DESC',(t['id'],st['id'])).fetchall(); c.close(); return [dict(x) for x in rows]

@app.get('/api/employment/invites')
def employment_invites(t=Depends(tenant_context)):
    c=conn(); rows=c.execute('SELECT ei.*,co.name company_name,j.title job_title,s.name student_name FROM employment_invites ei JOIN companies co ON co.id=ei.company_id LEFT JOIN jobs j ON j.id=ei.job_id JOIN students s ON s.id=ei.student_id WHERE ei.tenant_id=? ORDER BY ei.created_at DESC',(t['id'],)).fetchall(); c.close(); return [dict(x) for x in rows]

class CommitmentUpdateIn(BaseModel):
    hired_slots:int=Field(ge=0)
    status:Optional[str]=None

@app.put('/api/employment/commitments/{commitment_id}')
def update_commitment(commitment_id:str,x:CommitmentUpdateIn,t=Depends(require_role('EMPLOYER'))):
    c=conn(); r=c.execute('SELECT * FROM employer_commitments WHERE id=? AND tenant_id=?',(commitment_id,t['id'])).fetchone()
    if not r: c.close(); raise HTTPException(404,'Commitment not found')
    if x.hired_slots>r['committed_slots']: c.close(); raise HTTPException(400,'Hired slots cannot exceed committed slots')
    status=x.status or ('fulfilled' if x.hired_slots==r['committed_slots'] else r['status'])
    c.execute('UPDATE employer_commitments SET hired_slots=?,status=? WHERE id=?',(x.hired_slots,status,commitment_id)); log(c,t['id'],'dsc_admin','commitment_updated','commitment',commitment_id,x.model_dump()); c.commit(); c.close(); return {'status':'updated','hired_slots':x.hired_slots,'commitment_status':status}

@app.post('/api/skill-alerts/{skill_id}/act')
def create_reskill_action(skill_id:str,t=Depends(require_role('STUDENT'))):
    c=conn(); st=_current_student(c,t['id']); sk=c.execute('SELECT id,name FROM skills WHERE id=?',(skill_id,)).fetchone()
    if not sk: c.close(); raise HTTPException(404,'Skill not found')
    existing=c.execute('SELECT * FROM reskilling_actions WHERE tenant_id=? AND student_id=? AND skill_id=? AND status="planned" ORDER BY created_at DESC LIMIT 1',(t['id'],st['id'],skill_id)).fetchone()
    if existing: c.close(); return dict(existing)
    rid='reskill-'+uuid.uuid4().hex[:12]; c.execute('INSERT INTO reskilling_actions(id,tenant_id,student_id,skill_id,action,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(rid,t['id'],st['id'],skill_id,'Review current demand and add this skill to your learning plan','planned',now(),now())); log(c,t['id'],st['id'],'reskilling_action_created','reskilling_action',rid,{'skill_id':skill_id}); c.commit(); out=dict(c.execute('SELECT * FROM reskilling_actions WHERE id=?',(rid,)).fetchone()); c.close(); return out

@app.get('/api/skill-alerts/actions')
def list_reskill_actions(t=Depends(tenant_context)):
    c=conn(); st=_current_student(c,t['id']); rows=c.execute('SELECT ra.*,sk.name skill_name FROM reskilling_actions ra JOIN skills sk ON sk.id=ra.skill_id WHERE ra.tenant_id=? AND ra.student_id=? ORDER BY ra.created_at DESC',(t['id'],st['id'])).fetchall(); c.close(); return [dict(x) for x in rows]
