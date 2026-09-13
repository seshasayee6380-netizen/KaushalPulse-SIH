PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS states (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  code TEXT NOT NULL UNIQUE,
  state_type TEXT NOT NULL DEFAULT 'state'
);
CREATE TABLE IF NOT EXISTS districts (
  id TEXT PRIMARY KEY,
  state_id TEXT NOT NULL,
  name TEXT NOT NULL,
  lgd_code TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  FOREIGN KEY(state_id) REFERENCES states(id),
  UNIQUE(state_id, name)
);
CREATE INDEX IF NOT EXISTS idx_district_state ON districts(state_id);
CREATE INDEX IF NOT EXISTS idx_district_name ON districts(name);

CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY,
  district_id TEXT NOT NULL UNIQUE,
  tenant_type TEXT NOT NULL DEFAULT 'district',
  status TEXT NOT NULL DEFAULT 'active',
  FOREIGN KEY(district_id) REFERENCES districts(id)
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  tenant_id TEXT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS students (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT,
  name TEXT NOT NULL,
  qualification TEXT,
  target_role TEXT,
  target_company TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_students_tenant ON students(tenant_id);

CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_skills (
  student_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3),
  score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
  source TEXT NOT NULL DEFAULT 'self_assessment',
  updated_at TEXT NOT NULL,
  PRIMARY KEY(student_id, skill_id),
  FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY(skill_id) REFERENCES skills(id)
);
CREATE INDEX IF NOT EXISTS idx_student_skills_student ON student_skills(student_id);

CREATE TABLE IF NOT EXISTS roles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  sector TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS role_skills (
  role_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  required_level INTEGER NOT NULL CHECK(required_level BETWEEN 1 AND 3),
  weight REAL NOT NULL DEFAULT 1,
  PRIMARY KEY(role_id, skill_id),
  FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
  FOREIGN KEY(skill_id) REFERENCES skills(id)
);

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  sector TEXT NOT NULL,
  size TEXT NOT NULL,
  website TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_company_tenant_company ON companies(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_company_tenant_sector ON companies(tenant_id, sector);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  role_id TEXT NOT NULL,
  title TEXT NOT NULL,
  openings INTEGER NOT NULL DEFAULT 1,
  location_text TEXT,
  salary_min INTEGER,
  salary_max INTEGER,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(company_id) REFERENCES companies(id),
  FOREIGN KEY(role_id) REFERENCES roles(id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_role ON jobs(tenant_id, role_id);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status ON jobs(tenant_id, status);

CREATE TABLE IF NOT EXISTS employer_skill_requirements (
  company_id TEXT NOT NULL, tenant_id TEXT NOT NULL, skill_id TEXT NOT NULL, importance TEXT NOT NULL DEFAULT 'High',
  proficiency_level INTEGER NOT NULL DEFAULT 2 CHECK(proficiency_level BETWEEN 1 AND 3), notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
  PRIMARY KEY(company_id, skill_id), FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(skill_id) REFERENCES skills(id)
);
CREATE INDEX IF NOT EXISTS idx_employer_skill_requirements ON employer_skill_requirements(tenant_id,company_id);

CREATE TABLE IF NOT EXISTS training_providers (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  provider_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE TABLE IF NOT EXISTS courses (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  name TEXT NOT NULL,
  duration_weeks INTEGER NOT NULL,
  seats INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(provider_id) REFERENCES training_providers(id)
);
CREATE TABLE IF NOT EXISTS course_skills (
  course_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  taught_level INTEGER NOT NULL CHECK(taught_level BETWEEN 1 AND 3),
  PRIMARY KEY(course_id, skill_id),
  FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
  FOREIGN KEY(skill_id) REFERENCES skills(id)
);
CREATE INDEX IF NOT EXISTS idx_courses_tenant ON courses(tenant_id);

CREATE TABLE IF NOT EXISTS assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  level INTEGER NOT NULL,
  score INTEGER NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(student_id) REFERENCES students(id),
  FOREIGN KEY(skill_id) REFERENCES skills(id)
);
CREATE INDEX IF NOT EXISTS idx_assessments_tenant_student ON assessments(tenant_id, student_id);

CREATE TABLE IF NOT EXISTS employer_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  role_id TEXT,
  rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
  missing_skills TEXT,
  comment TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON employer_feedback(tenant_id);

CREATE TABLE IF NOT EXISTS district_plans (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  target_year INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  plan_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_plan_tenant_year ON district_plans(tenant_id, target_year);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT,
  actor TEXT,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  payload TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_log(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS provider_trainers (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, name TEXT NOT NULL, specialization TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '', experience_years INTEGER NOT NULL DEFAULT 0, availability TEXT NOT NULL DEFAULT 'Available', status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id)
);
CREATE TABLE IF NOT EXISTS provider_equipment (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, name TEXT NOT NULL, required_qty INTEGER NOT NULL DEFAULT 0, available_qty INTEGER NOT NULL DEFAULT 0, utilization_pct INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Adequate', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id)
);
CREATE TABLE IF NOT EXISTS provider_placements (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, provider_id TEXT NOT NULL, course_id TEXT NOT NULL, employer_name TEXT NOT NULL, students_placed INTEGER NOT NULL DEFAULT 0, openings INTEGER NOT NULL DEFAULT 0, placement_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Verified', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id), FOREIGN KEY(provider_id) REFERENCES training_providers(id), FOREIGN KEY(course_id) REFERENCES courses(id)
);
CREATE TABLE IF NOT EXISTS placement_simulations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  course_id TEXT,
  before_score INTEGER NOT NULL,
  projected_score INTEGER NOT NULL,
  assumptions TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_simulation_tenant ON placement_simulations(tenant_id);

CREATE TABLE IF NOT EXISTS student_resumes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  extracted_text TEXT NOT NULL,
  extracted_skills TEXT NOT NULL,
  fitness_score INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_resume_tenant_student ON student_resumes(tenant_id, student_id);

CREATE TABLE IF NOT EXISTS employer_commitments (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  role_id TEXT NOT NULL,
  committed_slots INTEGER NOT NULL,
  hired_slots INTEGER NOT NULL DEFAULT 0,
  valid_until TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  notes TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(company_id) REFERENCES companies(id),
  FOREIGN KEY(role_id) REFERENCES roles(id)
);
CREATE INDEX IF NOT EXISTS idx_commitment_tenant ON employer_commitments(tenant_id);

CREATE TABLE IF NOT EXISTS mentors (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  job_title TEXT NOT NULL,
  company TEXT NOT NULL,
  years_experience INTEGER NOT NULL,
  skills TEXT NOT NULL,
  available_slots INTEGER NOT NULL DEFAULT 1,
  bio TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS idx_mentor_tenant ON mentors(tenant_id);

CREATE TABLE IF NOT EXISTS mentorship_requests (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  mentor_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  goal TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(student_id) REFERENCES students(id),
  FOREIGN KEY(mentor_id) REFERENCES mentors(id)
);
CREATE INDEX IF NOT EXISTS idx_mentorship_tenant_student ON mentorship_requests(tenant_id, student_id);

CREATE TABLE IF NOT EXISTS skill_demand_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  period_label TEXT NOT NULL,
  job_count INTEGER NOT NULL DEFAULT 0,
  openings INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(skill_id) REFERENCES skills(id)
);
CREATE INDEX IF NOT EXISTS idx_skill_history_tenant_skill ON skill_demand_history(tenant_id, skill_id);

CREATE TABLE IF NOT EXISTS employment_invites (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  job_id TEXT,
  status TEXT NOT NULL DEFAULT 'invited',
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(company_id) REFERENCES companies(id),
  FOREIGN KEY(student_id) REFERENCES students(id)
);
CREATE INDEX IF NOT EXISTS idx_invites_tenant_student ON employment_invites(tenant_id, student_id);


CREATE TABLE IF NOT EXISTS demo_accounts (
  demo_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_demo_accounts_user ON demo_accounts(user_id);
