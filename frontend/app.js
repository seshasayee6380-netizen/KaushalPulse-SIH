const API = 'http://127.0.0.1:8010';
let tenantId = localStorage.getItem('kp_tenant') || '';
let stateId = localStorage.getItem('kp_state') || '';
let marketDistrictId = localStorage.getItem('kp_market_district') || '';
let marketStateId = localStorage.getItem('kp_market_state') || '';
let nationalLocations = [];
let locationReady = false;
let sessionToken = localStorage.getItem('kp_session') || '';
let currentUser = JSON.parse(localStorage.getItem('kp_user') || 'null');
let page = 'home';
const ROLE_NAV = {
 STUDENT:{title:'STUDENT',items:[['Dashboard','home'],['Career Alignment Hub','alignmentHub'],['My Profile','profile'],['Skill Assessment','assessment'],['Skill Gap','gap'],['Resume Fitness Score','resume'],['AI Skill-Path Navigator','path'],['Job Recommendations','jobs'],['AI Mentor Marketplace','mentors'],['Skill Obsolescence Alerts','alerts2']]},
 EMPLOYER:{title:'EMPLOYER',items:[['Dashboard','home'],['My Company','companies'],['Jobs & Hiring','demand'],['Skill Requirements','employerSkills'],['Candidate Pool','candidates'],['Training Partnership','trainingPartnership'],['Employment Commitments','commitments'],['Hiring Outcomes','outcomes'],['Employer Feedback','feedback']]},
 TRAINING_PROVIDER:{title:'TRAINING PROVIDER',items:[['Dashboard','home'],['My Centre','providerCentre'],['Courses','providerCourses'],['Skills Taught','providerSkills'],['Training Capacity','providerCapacity'],['Trainers & Equipment','providerResources'],['Placements','providerPlacements'],['Course Health','alignment'],['Industry Requirements','curriculum']]},
 DSC_ADMIN:{title:'DISTRICT ADMIN',items:[['Dashboard','districtDashboard'],['District Job Board','districtJobs'],['Active Recruiters','districtRecruiters'],['Course Health Score','districtCourseHealth'],['Curated Course Library','districtLibrary'],['Employment Guarantee Board','districtGuarantees'],['District Training Plan','districtPlan'],['Employer Feedback','districtFeedback'],['Placement Outcomes','districtPlacements']]}};


const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const lvl = {1:'Beginner',2:'Intermediate',3:'Advanced'};
const arr = (v) => Array.isArray(v) ? v : [];
const obj = (v, fallback={}) => (v && typeof v==='object' ? v : fallback);

function setStatus(text, ok=true){
  const e=$('#status'); if(!e) return;
  e.textContent=text; e.style.borderColor = ok ? '#3d5ba4' : '#a16a37';
}
function card(html, cls=''){ return `<section class="card ${cls}">${html}</section>`; }
function metric(label,value,sub=''){ return `<div><div class="muted">${esc(label)}</div><div class="metric">${esc(value)}</div>${sub?`<div class="muted">${esc(sub)}</div>`:''}</div>`; }
function explain(title, body){ return ''; }
function actionButton(label, fn, cls=''){ return `<button class="btn ${cls}" onclick="${fn}">${esc(label)}</button>`; }

async function api(path, options={}){
  const headers = new Headers(options.headers || {});
  if(tenantId) headers.set('X-Tenant-ID', tenantId);
  if(sessionToken) headers.set('X-Session-Token', sessionToken);
  if(marketDistrictId) headers.set('X-Market-District-ID', marketDistrictId);
  const r = await fetch(API + path, {...options, headers});
  if(!r.ok){
    let msg = `HTTP ${r.status}`;
    try { const j=await r.json(); msg=j.detail || msg; } catch { try { msg=await r.text(); } catch{} }
    if(r.status===401 && sessionToken){
      sessionToken=''; currentUser=null; tenantId=''; stateId='';
      localStorage.removeItem('kp_session'); localStorage.removeItem('kp_user'); localStorage.removeItem('kp_tenant'); localStorage.removeItem('kp_state');
      try{ showLogin(); setStatus('Session expired · please sign in again',false); }catch{}
    }
    throw new Error(msg);
  }
  const ct=r.headers.get('content-type')||'';
  return ct.includes('application/json') ? r.json() : r.text();
}

function roleLabel(role){ return ({STUDENT:'Student',EMPLOYER:'Employer',TRAINING_PROVIDER:'Training Provider',DSC_ADMIN:'District Administrator'})[role]||role; }

function showLogin(){
  document.querySelector('#appShell').classList.add('hidden');
  const ls=$('#loginScreen');
  ls.innerHTML=`<div class="login-wrap"><div class="login-card"><section class="login-hero"><div class="brand" style="margin:0">Kaushal<span>Pulse</span></div><div class="role-badge" style="margin-top:28px">Disha for your skills</div><div class="login-title">One platform.<br>Four trusted workspaces.</div><div class="login-tag">Sign in with the identity appropriate to your role. Your workspace, permissions and district access come from the account.</div><div class="login-hint"><b>Secure role-based access</b><br>Students use email + password. Employers, training providers and district administrators also provide their registered organisation identity.</div></section><section class="login-panel"><h2 style="margin:0">Sign in</h2><div class="muted" style="margin-top:5px">Choose your account type</div><div class="role-grid">${['STUDENT','EMPLOYER','TRAINING_PROVIDER','DSC_ADMIN'].map(r=>`<button type="button" class="role-btn" data-role="${r}" onclick="selectLoginRole('${r}')"><b>${roleLabel(r)}</b><div class="muted" style="font-size:11px;margin-top:3px">${r==='STUDENT'?'Learner account':r==='EMPLOYER'?'Company hiring account':r==='TRAINING_PROVIDER'?'Institute / centre account':'District administration'}</div></button>`).join('')}</div><form id="loginForm" onsubmit="submitLogin(event)"><div class="field"><label>Email address</label><input id="loginEmail" type="email" autocomplete="username" placeholder="name@example.com" required></div><div id="identifierWrap" class="field hidden"><label id="identifierLabel">Identity number</label><input id="loginIdentifier" placeholder="Enter your registered ID"></div><div class="field"><label>Password</label><input id="loginPassword" type="password" autocomplete="current-password" placeholder="Your password" required></div><div id="roleDesc" class="role-desc"></div><div id="loginError" class="notice danger hidden" style="margin-top:12px"></div><div class="login-actions"><button class="btn" style="width:100%">Sign in securely</button></div></form><div class="login-divider"><span>Quick demo access</span></div><div class="demo-credentials"><div class="muted" style="font-size:12px;margin-bottom:10px">No copying or pasting. Choose a role and sign in instantly with a seeded account.</div><div class="quick-demo-grid">
${[['DEMO-STUDENT-001','Student','National learner account'],['DEMO-EMPLOYER-001','Employer','National employer account'],['DEMO-TRAINER-001','Training Provider','National training provider'],['DEMO-ADMIN-001','District Admin','National district administration']].map(([id,role,label])=>`<button type="button" class="quick-demo" onclick="submitDemoDirect('${id}')"><b>${esc(role)}</b><span>${esc(label)}</span><em>Sign in</em></button>`).join('')}
</div><div class="muted" style="font-size:11px;margin-top:10px">Demo accounts are real seeded accounts authenticated by the backend.</div></div></section></div></div>`;
  selectLoginRole('STUDENT');
}

async function submitDemoDirect(demoId){ const err=$('#loginError'); err.classList.add('hidden'); try{ const r=await fetch(API+'/api/auth/demo-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({demo_id:demoId})}); const j=await r.json(); if(!r.ok) throw new Error(j.detail||'Demo sign in failed'); sessionToken=j.token; currentUser=j.user; tenantId=j.user.tenant_id; localStorage.setItem('kp_session',sessionToken);localStorage.setItem('kp_user',JSON.stringify(currentUser));localStorage.setItem('kp_tenant',tenantId);localStorage.removeItem('kp_market_district');localStorage.removeItem('kp_market_state'); await startApplication(); }catch(e){ err.textContent=e.message; err.classList.remove('hidden'); }}

async function loadDemoIds(){
  try{ const rows=arr(await api('/api/auth/demo-accounts')); $('#demoIdList').innerHTML=rows.map(x=>`<option value="${esc(x.demo_id)}">${esc(x.label)}</option>`).join(''); }catch{}
}

async function submitDemoLogin(){
  const err=$('#demoError'); err.classList.add('hidden');
  const demoId=$('#demoId').value.trim();
  if(!demoId){err.textContent='Enter a Demo ID.';err.classList.remove('hidden');return;}
  try{ const r=await fetch(API+'/api/auth/demo-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({demo_id:demoId})}); const j=await r.json(); if(!r.ok) throw new Error(j.detail||'Demo sign in failed'); sessionToken=j.token; currentUser=j.user; tenantId=j.user.tenant_id; localStorage.setItem('kp_session',sessionToken);localStorage.setItem('kp_user',JSON.stringify(currentUser));localStorage.setItem('kp_tenant',tenantId);localStorage.setItem('kp_state',''); await startApplication(); }catch(e){err.textContent=e.message;err.classList.remove('hidden');}
}

function copyCredential(text, button, originalLabel='Copy'){
  const done=()=>{ const old=button.textContent; button.textContent='Copied'; setTimeout(()=>button.textContent=originalLabel,1200); };
  if(navigator.clipboard && window.isSecureContext){ navigator.clipboard.writeText(text).then(done).catch(()=>fallbackCopy(text,done)); }
  else fallbackCopy(text,done);
}
function fallbackCopy(text, done){
  const ta=document.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.left='-9999px'; document.body.appendChild(ta); ta.focus(); ta.select(); try{document.execCommand('copy');}catch{} document.body.removeChild(ta); done();
}

let loginRole='STUDENT';
function selectLoginRole(role){
  loginRole=role;
  document.querySelectorAll('.role-btn').forEach(b=>b.classList.toggle('active',b.dataset.role===role));
  const wrap=$('#identifierWrap'), input=$('#loginIdentifier'), label=$('#identifierLabel');
  const meta={STUDENT:['','No extra number is required for a student account.'],EMPLOYER:['Employment number','Enter your registered employment number.'],TRAINING_PROVIDER:['Training provider ID','Enter your registered training provider ID.'],DSC_ADMIN:['DSC officer ID','Enter your registered DSC officer ID.']}[role];
  $('#roleDesc').textContent=meta[1];
  label.textContent=meta[0]||'Identity number';
  input.placeholder=meta[0]||'Not required';
  wrap.classList.toggle('hidden',role==='STUDENT');
  input.required=role!=='STUDENT';
}

async function submitLogin(ev){
  ev.preventDefault(); const err=$('#loginError'); err.classList.add('hidden');
  try{ const body={role:loginRole,email:$('#loginEmail').value,password:$('#loginPassword').value,identifier:$('#loginIdentifier')?.value||null}; const r=await fetch(API+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); if(!r.ok) throw new Error(j.detail||'Sign in failed'); sessionToken=j.token; currentUser=j.user; tenantId=j.user.tenant_id; localStorage.setItem('kp_session',sessionToken);localStorage.setItem('kp_user',JSON.stringify(currentUser));localStorage.setItem('kp_tenant',tenantId);localStorage.setItem('kp_state',''); await startApplication(); }catch(e){ err.textContent=e.message; err.classList.remove('hidden'); }
}

async function logout(){ try{await fetch(API+'/api/auth/logout',{method:'POST',headers:{'X-Session-Token':sessionToken}})}catch{} sessionToken='';currentUser=null;tenantId='';stateId='';localStorage.removeItem('kp_session');localStorage.removeItem('kp_user');localStorage.removeItem('kp_tenant');localStorage.removeItem('kp_state');showLogin();setStatus('Signed out');}

function buildNav(){ const cfg=ROLE_NAV[currentUser?.role]||ROLE_NAV.STUDENT; $('#navMount').innerHTML=`<div class="nav-title">${cfg.title}</div><div class="nav">${cfg.items.map(([label,p])=>`<button data-page="${p}">${label}</button>`).join('')}</div>`; $('#signedUser').textContent=currentUser?.name||''; $('#signedRole').textContent=roleLabel(currentUser?.role||''); const marketName = marketDistrictId ? (nationalLocations.find(v=>`${String(v.stateCode||slug(v.state)).toLowerCase()}:${slug(v.district)}`===marketDistrictId)?.district || currentUser?.district_name) : currentUser?.district_name; $('#greeting').textContent=currentUser?.role==='STUDENT'?`Good Morning, ${currentUser?.name||'Student'}! 👋`:`Welcome, ${marketName||currentUser?.name||'User'} ${roleLabel(currentUser?.role||'').toLowerCase()}`; $('#subtitle').textContent=currentUser?.role==='STUDENT'?'Connect skills, training and local employer demand.':`Working market: ${marketName||currentUser?.district_name||'Not selected'}. Account permissions remain tied to your registered tenant.`; bindNav(); }

async function refreshEvidenceBar(){
  const el=$('#evidenceBar'); if(!el) return;
  try{ const x=obj(await api('/api/core/engine')); const prov=arr(x.provenance); el.innerHTML='<b>Evidence provenance</b> · '+(prov.map(v=>esc(v.label+' ('+v.type+')')).join(' · ')||'No provenance records returned')+' · Engine '+esc(x.engine_version||'unknown'); } catch(e){ el.textContent='Evidence provenance unavailable: '+e.message; }
}

async function startApplication(){
  $('#loginScreen').innerHTML=''; $('#appShell').classList.remove('hidden'); buildNav();
  try{
    const me=await api('/api/auth/me'); currentUser=me.user; localStorage.setItem('kp_user',JSON.stringify(currentUser)); tenantId=currentUser.tenant_id;
    $('#activeTenant').textContent='Registered account';
    setStatus('Signed in · '+roleLabel(currentUser.role));
    await loadNationalLocations();
    await syncMarketContext();
    await refreshEvidenceBar();
    await renderPage('home');
  }catch(e){console.error(e); logout();}
}

async function boot(){
  try{ const h=await fetch(API+'/health'); if(!h.ok) throw new Error('Backend health check failed'); const health=await h.json(); if(health.version!=='8.0.0') throw new Error('Wrong KaushalPulse backend version. Run run_backend.bat from this project folder.');
    if(sessionToken){ await startApplication(); } else { showLogin(); setStatus('Sign in required'); }
  }catch(e){ console.error(e); showLogin(); setStatus('Backend unavailable · '+e.message,false); }
}

async function loadNationalLocations(){
  if(locationReady && nationalLocations.length) return;
  const CACHE_KEY='kp_locations_cache_v10';
  const cached=localStorage.getItem(CACHE_KEY);
  const normalizeRows=(rows)=>arr(rows).map(x=>({state:x.state,stateCode:x.state_code||x.stateCode||'',district:x.district,districtCode:x.district_code||x.districtCode||'',fallbackId:x.district_id||x.id||''})).filter(x=>x.state&&x.district);
  try{
    // Local backend is primary: it can refresh the full national directory server-side.
    const r=await fetch(API+'/api/national/locations?ts='+Date.now(),{cache:'no-store'});
    if(r.ok){ const j=await r.json(); const rows=normalizeRows(j.locations); if(rows.length>=500){ nationalLocations=rows; localStorage.setItem(CACHE_KEY,JSON.stringify(rows)); } }
  }catch(e){ console.warn('National API unavailable',e); }
  if(nationalLocations.length<500 && cached){
    try{ const x=normalizeRows(JSON.parse(cached)); if(x.length>=500) nationalLocations=x; }catch{}
  }
  if(nationalLocations.length<740){
    // Browser-side fallback from the public national district reference.
    for(const url of [
      'https://raw.githubusercontent.com/iaseth/data-for-india/master/data/readable/districts.json',
      'https://raw.githubusercontent.com/KTBsomen/Indian-state-district-json/main/india-states-districts-latest.json'
    ]){
      try{
        const r=await fetch(url,{cache:'no-store'}); if(!r.ok) continue;
        const j=await r.json();
        const rows = Array.isArray(j) ? normalizeRows(j.flatMap(s=>arr(s.districts).map(d=>typeof d==='string'?{state:s.state,stateCode:s.stateCode||'',district:d}:({...d,state:s.state,stateCode:s.stateCode||d.stateCode||''})))) : normalizeRows(j.districts);
        if(rows.length>=740){ nationalLocations=rows; localStorage.setItem(CACHE_KEY,JSON.stringify(rows)); break; }
      }catch(e){ console.warn('Remote location fallback unavailable',e); }
    }
  }
  if(nationalLocations.length<100){
    try{
      const states=arr(await fetch(API+'/api/states').then(r=>r.json()));
      const all=[]; for(const st of states){ const ds=arr(await fetch(API+'/api/states/'+encodeURIComponent(st.id)+'/districts').then(r=>r.json())); ds.forEach(d=>all.push({state:st.name,stateCode:st.code,district:d.name,districtCode:d.lgd_code||'',fallbackId:d.id})); }
      nationalLocations=all;
    }catch(e){ console.warn('State endpoint fallback unavailable',e); }
  }
  // Canonicalize common naming variants so one logical state cannot appear twice.
  const stateAlias={
    'National Capital Territory of Delhi':'Delhi',
    'NCT of Delhi':'Delhi',
    'Pondicherry':'Puducherry',
    'Jammu & Kashmir':'Jammu and Kashmir',
    'Andaman & Nicobar Islands':'Andaman and Nicobar Islands'
  };
  const seen=new Set(), clean=[];
  for(const x of nationalLocations){
    const state=stateAlias[x.state]||x.state;
    const key=((x.stateCode||slug(state))+'::'+x.district.toLowerCase()).replace(/\s+/g,' ');
    if(!seen.has(key)){ seen.add(key); clean.push({...x,state}); }
  }
  nationalLocations=clean;
  locationReady=true;
}

function normalizedStateId(name, code){
  const exact=nationalLocations.find(x=>(x.stateCode||'')===code && x.state===name);
  if(exact && exact.stateCode) return String(exact.stateCode).toLowerCase();
  return slug(name);
}
function slug(v){ return String(v||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''); }
function marketOptions(){
  const map=new Map(); nationalLocations.forEach(x=>{ if(x.state) map.set((x.stateCode||slug(x.state)), {id:(x.stateCode||slug(x.state)).toString().toLowerCase(),name:x.state,code:x.stateCode||''}); });
  return [...map.values()].sort((a,b)=>a.name.localeCompare(b.name));
}
function districtsForState(id){
  const opts=marketOptions().find(x=>x.id===id); const code=opts?.code||id;
  return nationalLocations.filter(x=>(x.stateCode||slug(x.state)).toString().toLowerCase()===id || slug(x.state)===id).map(x=>({name:x.district,code:x.districtCode||'',state:x.state,stateCode:x.stateCode||code,id:`${id}:${slug(x.district)}`})).sort((a,b)=>a.name.localeCompare(b.name));
}
function renderMarketSelectors(){
  const states=marketOptions();
  const ss=$('#marketStateSelect'), ds=$('#marketDistrictSelect'); if(!ss||!ds) return;
  ss.innerHTML=states.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  if(!marketStateId || !states.some(x=>x.id===marketStateId)) marketStateId=states[0]?.id||'';
  ss.value=marketStateId;
  ss.onchange=()=>{ marketStateId=ss.value; localStorage.setItem('kp_market_state',marketStateId); marketDistrictId=''; localStorage.removeItem('kp_market_district'); renderMarketDistricts(); };
  renderMarketDistricts();
}
function renderMarketDistricts(){
  const ds=$('#marketDistrictSelect'); if(!ds) return; const list=districtsForState(marketStateId);
  ds.innerHTML=list.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  if(!marketDistrictId || !list.some(x=>x.id===marketDistrictId)) marketDistrictId=list[0]?.id||'';
  ds.value=marketDistrictId;
  localStorage.setItem('kp_market_district',marketDistrictId);
  ds.onchange=()=>selectMarketDistrict(ds.value);
  updateMarketLabel();
}
async function selectMarketDistrict(did){
  const st=districtsForState(marketStateId).find(x=>x.id===did); if(!st) return;
  marketDistrictId=did; localStorage.setItem('kp_market_district',did);
  try{
    await api('/api/locations/ensure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:st.state,state_code:st.stateCode,district:st.name,district_code:st.code})});
  }catch(e){ /* location may already exist; reads still work */ }
  updateMarketLabel(); buildNav(); await refreshEvidenceBar(); setStatus('Market: '+st.name+', '+st.state); await renderPage(page);
}
function isAssignedMarket(){ return !!tenantId && tenantId.replace(/^t:/,'')===marketDistrictId; }
function updateMarketLabel(){
  const txt=$('#marketLabel'); if(!txt) return;
  const x=nationalLocations.find(v=>`${String(v.stateCode||slug(v.state)).toLowerCase()}:${slug(v.district)}`===marketDistrictId);
  txt.textContent=x?`${x.district}, ${x.state}`:'Select a state and district';
}
async function syncMarketContext(){
  await loadNationalLocations();
  const assigned=nationalLocations.find(x=>x.state===currentUser?.state_name && x.district===currentUser?.district_name);
  if(!marketDistrictId && assigned) { marketStateId=String(assigned.stateCode||slug(assigned.state)).toLowerCase(); marketDistrictId=`${marketStateId}:${slug(assigned.district)}`; }
  renderMarketSelectors();
}

function bindNav(){ document.querySelectorAll('.nav button').forEach(b=>{ b.onclick=()=>renderPage(b.dataset.page); }); }

async function renderPage(p){
  page=p; bindNav(); document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===p));
  const allowed=(ROLE_NAV[currentUser?.role]||ROLE_NAV.STUDENT).items.map(x=>x[1]); if(!allowed.includes(p)) p='home';
  const wrap=$('#page'); wrap.classList.add('loading');
  try{
    if(p==='home') return currentUser?.role==='STUDENT' ? await renderHome(wrap) : await renderWorkspaceHome(wrap);
    if(p==='districtDashboard') return await renderDistrictDashboard(wrap);
    if(p==='districtJobs') return await renderDistrictJobs(wrap);
    if(p==='districtRecruiters') return await renderDistrictRecruiters(wrap);
    if(p==='districtCourseHealth') return await renderDistrictCourseHealth(wrap);
    if(p==='districtLibrary') return await renderDistrictLibrary(wrap);
    if(p==='districtGuarantees') return await renderDistrictGuarantees(wrap);
    if(p==='districtPlan') return await renderDistrictPlan(wrap);
    if(p==='districtFeedback') return await renderDistrictFeedback(wrap);
    if(p==='districtPlacements') return await renderDistrictPlacements(wrap);
    if(p==='alignmentHub') return await renderAlignmentHub(wrap);
    if(p==='profile') return await renderProfile(wrap);
    if(p==='assessment') return await renderAssessment(wrap);
    if(p==='gap') return await renderGap(wrap);
    if(p==='resume') return await renderResume(wrap);
    if(p==='path') return await renderPath(wrap);
    if(p==='jobs') return await renderJobs(wrap);
    if(p==='mentors') return await renderMentors(wrap);
    if(p==='alerts2') return await renderStudentAlerts(wrap);
    if(p==='commitments') return await renderCommitments(wrap);
    if(p==='companies') return await renderCompanies(wrap);
    if(p==='demand') return await renderDemand(wrap);
    if(p==='employerSkills') return await renderEmployerSkills(wrap);
    if(p==='candidates') return await renderCandidates(wrap);
    if(p==='trainingPartnership') return await renderTrainingPartnership(wrap);
    if(p==='outcomes') return await renderHiringOutcomes(wrap);
    if(p==='providerCentre') return await renderProviderCentre(wrap);
    if(p==='providerCourses') return await renderProviderCourses(wrap);
    if(p==='providerSkills') return await renderProviderSkills(wrap);
    if(p==='providerCapacity') return await renderProviderCapacity(wrap);
    if(p==='providerResources') return await renderProviderResources(wrap);
    if(p==='providerPlacements') return await renderProviderPlacements(wrap);
    if(p==='academy') return await renderAcademy(wrap);
    if(p==='alerts') return await renderCourseAlerts(wrap);
    if(p==='curriculum') return await renderCurriculum(wrap);
    if(p==='simulator') return await renderSimulator(wrap);
    if(p==='alignment') return await renderAlignment(wrap);
    if(p==='feedback') return await renderFeedback(wrap);
    if(p==='plan') return await renderPlan(wrap);
  }catch(e){ wrap.innerHTML=card(`<div class="notice danger"><b>Action failed</b><br>${esc(e.message)}</div>`); }
  finally{ wrap.classList.remove('loading'); }
}

async function renderWorkspaceHome(w){
  if(currentUser?.role==='STUDENT') return renderHome(w);
  const s=obj(await api('/api/market/summary'));
  if(currentUser?.role==='EMPLOYER'){
    const d=obj(await api('/api/employer/dashboard'));
    const alerts=arr(d.alerts).map(a=>`<div class="notice ${a.type==='critical'?'danger':''}" style="margin:8px 0"><b>${esc(a.title)}</b><br><span class="muted">${esc(a.detail)}</span><div style="margin-top:8px">${actionButton(a.cta,a.page?`renderPage('${a.page}')`:`renderPage('demand')`)}</div></div>`).join('')||'<div class="notice success">No critical hiring actions right now.</div>';
    w.innerHTML=card(`<div class="alignment-hero"><div class="hub-kicker">EMPLOYER CONTROL CENTRE</div><div class="hub-title">Turn real hiring demand into better candidates.</div><div class="hub-sub">Post jobs, define the skills you need, hire candidates, partner with training providers and feed outcomes back into district planning.</div></div>`)+card(`<h2>Hiring snapshot</h2><div class="grid">${card(metric('Open positions',d.open_positions),'sm')}${card(metric('Candidates matched',d.candidates_matched),'sm')}${card(metric('Invitations',d.invited),'sm')}${card(metric('People hired',d.hired),'sm')}${card(metric('Active commitments',d.commitments),'sm')}${card(metric('Feedback submitted',d.feedback_count),'sm')}</div>`)+card(`<h2>Recommended employer actions</h2>${alerts}`)+card(`<h2>Employer impact loop</h2><div class="hub-flow"><div class="flow-step active"><div class="flow-number">01</div><b>Define demand</b><span>Jobs + skills</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">02</div><b>Hire</b><span>Skill-based matching</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">03</div><b>Validate</b><span>Employer feedback</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">04</div><b>Improve training</b><span>Partnership requests</span></div></div>`);
  } else if(currentUser?.role==='TRAINING_PROVIDER'){

    w.innerHTML=card(explain('Training provider workspace','Your centre is registered under the assigned district. Course, capacity and placement data remain in that district tenant.')+`<h2>Training centre workspace</h2><div class="grid">${card(metric('Training providers',s.training_providers??0),'sm')}${card(metric('Training seats',s.training_capacity??0),'sm')}${card(metric('Open job openings',s.open_jobs??0),'sm')}${card(metric('Employers',s.companies??0),'sm')}</div><div style="margin-top:16px">${actionButton('Open course library',`renderPage('academy')`)} ${actionButton('Open course health',`renderPage('alignment')`)}</div>`)+card(`<h3>Account identity</h3><div class="row"><span class="pill">${esc(currentUser.email)}</span><span class="pill">${esc(currentUser.credential_id)}</span><span class="pill">${esc(currentUser.district_name)}</span></div>`);
  } else {
    w.innerHTML=card(explain('District administration workspace','The DSC account is scoped to one district. Planning decisions use employer demand, training supply, course alignment and outcomes from that tenant.')+`<h2>District control centre</h2><div class="grid">${card(metric('Employers',s.companies??0),'sm')}${card(metric('Open job openings',s.open_jobs??0),'sm')}${card(metric('Training providers',s.training_providers??0),'sm')}${card(metric('Training seats',s.training_capacity??0),'sm')}</div><div style="margin-top:16px">${actionButton('Open district plan',`renderPage('plan')`)} ${actionButton('Open course health',`renderPage('alignment')`)}</div>`)+card(`<h3>Officer identity</h3><div class="row"><span class="pill">${esc(currentUser.email)}</span><span class="pill">${esc(currentUser.credential_id)}</span><span class="pill">${esc(currentUser.district_name)}</span></div>`);
  }
}

async function renderHome(w){
  const [s,r,g,j0,res,pth0]=await Promise.all([api('/api/market/summary'),api('/api/student/readiness'),api('/api/student/gap'),api('/api/market/jobs?limit=8'),api('/api/student/resume-fitness'),api('/api/student/path-navigator')]);
  const j=arr(j0), pth=obj(pth0), rr=obj(r), gg=obj(g), ss=obj(s), rf=obj(res);
  w.innerHTML = explain('National market context','State and district selection is available on every page. Student profile data remains private to the account tenant, while market demand, employers, courses and job discovery follow the selected district.')+card(`<h2>District snapshot</h2><div class="grid">${card(metric('Employers',ss.companies??0),'sm')}${card(metric('Open job openings',ss.open_jobs??0),'sm')}${card(metric('Training providers',ss.training_providers??0),'sm')}${card(metric('Training seats',ss.training_capacity??0),'sm')}</div>`)+
  `<div class="grid" style="margin-top:16px">`+
  card(explain('Career readiness','Calculated from your stored skill levels against the target role requirements.')+`<div class="scorebox"><div class="bigscore">${rr.score??0}%</div><div><b>${esc(rr.label||'Needs Development')}</b><br><span class="muted">Target: ${esc(gg.role?.name||'Target role')}</span></div></div><div class="bar"><div style="width:${rr.score??0}%"></div></div><div style="margin-top:12px">${actionButton('View Skill Gap',`renderPage('gap')`)}</div>`,'md')+
  card(explain('Resume Fitness Score','Resume evidence is analysed separately and compared with current district job requirements.')+`<div class="metric">${rf.has_resume?rf.score+'%':'—'}</div><div class="muted">${rf.has_resume?'Latest resume fitness':'Upload a resume to calculate job fit'}</div><div style="margin-top:12px">${actionButton('Open Resume Fitness',`renderPage('resume')`)}</div>`,'md')+
  card(explain('AI Skill-Path Navigator','A persisted 12-week plan maps your target role gaps to local courses and practical projects.')+`<div class="metric">${pth.path_id?pth.progress_pct+'%':'Not created'}</div><div class="muted">${pth.path_id?'Current path progress':'Generate a target-role path'}</div><div style="margin-top:12px">${actionButton('Open Navigator',`renderPage('path')`)}</div>`,'md')+
  card(explain('Local job matching','Each opening is a separate employer posting, matched against your stored skills.')+`<div class="metric">${j.length}</div><div class="muted">Job postings returned</div><div style="margin-top:12px">${actionButton('View Jobs',`renderPage('jobs')`)}</div>`,'md')+
  `</div>`;
}

async function renderAlignmentHub(w){
  const d=obj(await api('/api/student/alignment-hub'));
  const market=d.market||{}, demand=arr(d.demand), gaps=arr(d.gaps), jobs=arr(d.jobs);
  const topGaps=gaps.slice(0,4);
  const demandSkillIds=new Set(demand.map(x=>x.skill_id));
  const gapCount=gaps.length;
  const topCourseCards=gaps.slice(0,3).map(g=>{
    const course=g.courses?.[0];
    return `<div class="hub-mini-card"><div class="hub-mini-top"><span class="hub-icon warn">↑</span><div><b>${esc(g.name)}</b><div class="muted">${g.current_label} → ${g.required_label}</div></div></div>${course?`<div class="hub-course"><b>${esc(course.name)}</b><span class="muted">${esc(course.provider_name)} · ${course.duration_weeks} weeks · ${course.seats} seats</span></div>`:`<div class="hub-course muted">No local course mapped yet</div>`}</div>`;
  }).join('');
  const demandCards=demand.slice(0,6).map((x,i)=>`<div class="demand-row"><div class="hub-rank">${i+1}</div><div class="demand-name"><b>${esc(x.name)}</b><span class="muted">${x.postings} postings</span></div><div class="demand-bar"><div style="width:${Math.min(100,Number(x.openings||0)*4)}%"></div></div><strong>${x.openings}</strong></div>`).join('');
  const gapCards=topGaps.map((g,i)=>`<div class="gap-row"><div class="gap-severity">${i===0?'HIGH':'GAP'}</div><div style="flex:1"><div class="row" style="justify-content:space-between"><b>${esc(g.name)}</b><span class="pill">${g.local_demand?.openings||0} local openings</span></div><div class="gap-track"><div style="width:${Math.min(100,g.gap_score)}%"></div></div><div class="muted" style="font-size:12px">You: ${esc(g.current_label)} · Role requires: ${esc(g.required_label)} · ${g.gap_score} score points to close</div></div></div>`).join('');
  const courseAction=gaps[0]?.courses?.[0] ? `Start ${esc(gaps[0].courses[0].name)}` : 'Open Skill Path';
  const jobCards=jobs.map((j,i)=>`<div class="job-row"><div class="job-match">${j.match}%<span>match</span></div><div class="job-main"><b>${esc(j.title)}</b><span>${esc(j.company_name)} · ${esc(j.location_text||market.district_name||'Local market')}</span><div class="muted">${j.openings} openings · ${j.salary_min?'₹'+Number(j.salary_min).toLocaleString('en-IN')+'–₹'+Number(j.salary_max||j.salary_min).toLocaleString('en-IN'):'Salary on application'}</div></div><button class="btn secondary" onclick="renderPage('jobs')">View</button></div>`).join('');
  w.innerHTML=`
  <div class="alignment-hero">
    <div class="hub-kicker">AI CAREER ALIGNMENT ENGINE</div>
    <div class="hub-title">Turn <span>industry demand</span> into your next job.</div>
    <div class="hub-sub">KaushalPulse connects what employers need, what you are missing, where you can learn it, and which jobs you can target next.</div>
    <div class="hub-flow">
      <div class="flow-step active"><div class="flow-number">01</div><b>Industry Demand</b><span>${market.openings||0} open positions</span></div><div class="flow-line"></div>
      <div class="flow-step"><div class="flow-number">02</div><b>Your Skill Gap</b><span>${gapCount} priority gaps</span></div><div class="flow-line"></div>
      <div class="flow-step"><div class="flow-number">03</div><b>Targeted Training</b><span>${topGaps.filter(g=>arr(g.courses).length).length} mapped options</span></div><div class="flow-line"></div>
      <div class="flow-step"><div class="flow-number">04</div><b>Job Match</b><span>${jobs[0]?.match||0}% top match</span></div>
    </div>
  </div>
  <div class="grid hub-metrics">
    ${card(`<div class="muted">Industry demand</div><div class="hub-big">${market.openings||0}</div><div class="muted">openings in ${esc(market.district_name||'your market')}</div>`,'sm')}
    ${card(`<div class="muted">Readiness</div><div class="hub-big">${d.readiness||0}%</div><div class="bar"><div style="width:${d.readiness||0}%"></div></div>`,'sm')}
    ${card(`<div class="muted">Priority gaps</div><div class="hub-big">${gapCount}</div><div class="muted">skills to close for ${esc(d.target_role?.name||'your target role')}</div>`,'sm')}
    ${card(`<div class="muted">Top job match</div><div class="hub-big">${jobs[0]?.match||0}%</div><div class="muted">${esc(jobs[0]?.title||'Keep building skills')}</div>`,'sm')}
  </div>
  <div class="hub-grid" style="margin-top:16px">
    ${card(`<div class="row" style="justify-content:space-between"><div><h2>1 · What industry needs</h2><p class="muted">Live demand signal from the selected district.</p></div><span class="hub-badge">Market intelligence</span></div><div class="demand-list">${demandCards||'<div class="notice">No active demand yet.</div>'}</div>`,'hub-panel')}
    ${card(`<div class="row" style="justify-content:space-between"><div><h2>What you need to build</h2><p class="muted">Your verified skills against ${esc(d.target_role?.name||'target role')} requirements.</p></div><span class="hub-badge danger">${gapCount} gaps</span></div><div>${gapCards||'<div class="notice success">You are aligned on all currently required skills.</div>'}</div>`,'hub-panel')}
  </div>
  <div class="hub-grid" style="margin-top:16px">
    ${card(`<div class="row" style="justify-content:space-between"><div><h2>3 · Where you can learn it</h2><p class="muted">Courses are mapped to your highest-priority gaps and filtered to the active market.</p></div><button class="btn secondary" onclick="renderPage('path')">Open full path</button></div><div class="hub-mini-grid">${topCourseCards||'<div class="notice">No mapped local training yet.</div>'}</div><div class="hub-cta"><div><b>Next best move</b><div class="muted">${courseAction.replace(/<[^>]*>/g,'')}</div></div><button class="btn" onclick="renderPage('path')">Build my 12-week path →</button></div>`,'hub-panel')}
    ${card(`<div class="row" style="justify-content:space-between"><div><h2>4 · Jobs you can target</h2><p class="muted">Role-level match based on your current verified skills.</p></div><button class="btn secondary" onclick="renderPage('jobs')">See all jobs</button></div><div class="job-list">${jobCards||'<div class="notice">No matched jobs found.</div>'}</div>`,'hub-panel')}
  </div>
  `;
}

async function renderProfile(w){
  const d=obj(await api('/api/student/profile'));
  w.innerHTML=explain('Profile','Your qualifications, target role and skills are the inputs to the assessment, job matching and learning pathway.')+card(`<h2>My Profile</h2><form id="profileForm"><div class="grid"><div style="grid-column:span 6"><label>Name</label><input id="pname" value="${esc(d.name)}"></div><div style="grid-column:span 6"><label>Qualification</label><input id="pqual" value="${esc(d.qualification)}"></div><div style="grid-column:span 6"><label>Target role</label><select id="prole" class="select" style="width:100%"></select></div><div style="grid-column:span 6"><label>Target company</label><input id="pcomp" value="${esc(d.target_company)}"></div></div><button class="btn" style="margin-top:15px">Save profile</button></form><div id="profileMsg" style="margin-top:12px"></div>`)+card(`<h3>Current verified skill levels</h3>${arr(d.skills).map(s=>`<div style="margin:11px 0"><div class="row"><b>${esc(s.name)}</b><span class="pill">${esc(lvl[s.level]||'Not assessed')}</span></div><div class="bar"><div style="width:${s.score}%"></div></div></div>`).join('')}`);
  const roles=arr(await api('/api/roles')); $('#prole').innerHTML=roles.map(r=>`<option value="${esc(r.name)}" ${r.name===d.target_role?'selected':''}>${esc(r.name)}</option>`).join('');
  $('#profileForm').onsubmit=saveProfile;
}
async function saveProfile(e){e.preventDefault(); const payload={name:$('#pname').value.trim(),qualification:$('#pqual').value.trim(),target_role:$('#prole').value,target_company:$('#pcomp').value.trim()}; const saved=obj(await api('/api/student/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})); currentUser={...(currentUser||{}),...saved,name:saved.name||payload.name}; localStorage.setItem('kp_user',JSON.stringify(currentUser)); buildNav(); $('#profileMsg').innerHTML='<div class="notice success">Profile saved. Your dashboard greeting now uses the updated name.</div>'; setStatus('Profile saved');}

async function renderAssessment(w){
  const [skills0,profile0]=await Promise.all([api('/api/skills'),api('/api/student/profile')]); const skills=arr(skills0), profile=obj(profile0);
  const current={}; profile.skills.forEach(s=>current[s.id]=s.level);
  w.innerHTML=explain('Skill Assessment','Pick a task-based level. Beginner means basic guided work; Intermediate means independent normal tasks; Advanced means complex real-world work and troubleshooting.')+card(`<h2>3-Level Skill Assessment</h2><div class="grid">${skills.map(s=>`<div class="md notice"><b>${esc(s.name)}</b><div class="muted" style="margin:6px 0">${esc(s.category)}</div><div class="level"><button data-skill="${esc(s.id)}" data-level="1" class="${current[s.id]===1?'selected':''}">Beginner</button><button data-skill="${esc(s.id)}" data-level="2" class="${current[s.id]===2?'selected':''}">Intermediate</button><button data-skill="${esc(s.id)}" data-level="3" class="${current[s.id]===3?'selected':''}">Advanced</button></div></div>`).join('')}</div><button class="btn" id="saveAssess" style="margin-top:15px">Save assessment</button><div id="assessMsg"></div>`);
  document.querySelectorAll('.level button').forEach(b=>b.onclick=()=>{ const group=b.parentElement; group.querySelectorAll('button').forEach(x=>x.classList.remove('selected')); b.classList.add('selected'); });
  $('#saveAssess').onclick=async()=>{ const selected=[...document.querySelectorAll('.level button.selected')]; for(const b of selected) await api('/api/student/assessment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:b.dataset.skill,level:Number(b.dataset.level),source:'task_assessment'})}); $('#assessMsg').innerHTML='<div class="notice success" style="margin-top:12px">Assessment stored. Your Skill Gap, Readiness and Job Recommendations have been recalculated from these values.</div>'; setStatus('Assessment saved'); };
}
async function renderGap(w){
  const g=obj(await api('/api/student/gap'));
  w.innerHTML=explain('Skill Gap','The gap is not a guessed percentage. It compares each assessed skill level with the required level for your target role.')+card(`<h2>Skill Gap Analysis</h2><p class="muted">Target role: <b>${esc(g.role?.name||'Target role')}</b> · Current readiness: <b>${g.readiness}%</b></p><table class="table"><tr><th>Skill</th><th>Current</th><th>Required</th><th>Gap</th></tr>${arr(g.rows).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.current_label)}</td><td>${esc(x.target_label)}</td><td>${x.gap_level?`<span class="pill">${x.gap_level} level${x.gap_level>1?'s':''}</span>`:'<span class="pill">Aligned</span>'}</td></tr>`).join('')}</table><div style="margin-top:14px">${actionButton('Build / update learning path',`renderPage('path')`)}</div>`);
}

async function renderResume(w){
  const [f0,ctx0,d0]=await Promise.all([api('/api/student/resume-fitness'),api('/api/tenant/context'),api('/api/market/demand')]); const f=obj(f0), ctx=obj(ctx0), d=obj(d0);
  const jobs=arr(f.job_matches), matched=arr(f.matched_skills), missing=arr(f.missing_skills), demandRoles=arr(d.roles), learned=arr(f.learned_skills), resumeSkills=arr(f.resume_skills), employerDemand=arr(f.skill_employer_demand);
  const learnedIds=new Set(learned.map(x=>x.id));
  const resumeOnly=resumeSkills.filter(x=>!learnedIds.has(x.id));
  const learnedName=(id)=>{const x=learned.find(s=>s.id===id);return x?`${esc(x.name)} · ${esc(lvl[x.level]||'Learned')}`:esc(id)};
  const sourceBadge=(id)=>learnedIds.has(id)?'<span class="pill">Learned / verified</span>':'<span class="pill">Resume detected</span>';
  const employerRows=employerDemand.flatMap(x=>arr(x.employers).map(e=>({skill_name:x.skill_name,...e})));
  w.innerHTML=explain('Resume-to-Opportunity Intelligence','Upload your resume and KaushalPulse separates what the resume proves, what you have already learned in the platform, and which local companies are currently hiring for those skills. Use the results to choose the next skill to learn and the employers to target.')+
  card(`<h2>Resume analysis</h2><form id="resumeForm" class="dropzone"><input id="resumeFile" type="file" accept=".pdf,.txt,.md,.csv" required><div class="muted" style="margin:8px 0">PDF, TXT, MD or CSV · text-based resumes work best</div><button class="btn">Upload & Analyse</button></form><div id="resumeMsg" style="margin-top:12px"></div>${f.has_resume?`<div style="margin-top:18px" class="scorebox"><div class="bigscore">${f.score}%</div><div><b>${esc(f.target_role)}</b><br><span class="muted">${esc(f.message)}</span></div></div><div class="bar"><div style="width:${f.score}%"></div></div><div class="grid" style="margin-top:12px">${card(metric('Resume fitness',f.score+'%'),'sm')}${card(metric('Learned skills',learned.length),'sm')}${card(metric('Resume skills',resumeSkills.length),'sm')}${card(metric('Local employer matches',employerRows.length),'sm')}</div>`:'<div class="notice" style="margin-top:15px">No resume analysed yet. Upload a resume to see your skills, learned skills and employers that need them.</div>'}`)+
  (f.has_resume?card(`<h3>1. Skills found in your resume</h3><p class="muted">These are skills the uploaded resume text contains. They are evidence from the document, not automatically treated as verified training.</p><div class="row">${resumeSkills.map(x=>`<span class="pill">${esc(x.name)}</span>`).join('')||'<span class="muted">No supported skills detected. Add clearer skill terms to your resume.</span>'}</div>${resumeOnly.length?`<div class="notice" style="margin-top:12px"><b>Resume-only skills:</b> ${resumeOnly.map(x=>esc(x.name)).join(' · ')}. Add these to your verified learning record through Skill Assessment or the learning path when you have actually learned them.</div>`:''}`):'')+
  (f.has_resume?card(`<h3>2. Skills you have learned / verified</h3><p class="muted">These come from your stored Skill Assessment / learning-path records, so the student can distinguish claimed resume skills from platform-verified learning progress.</p><table class="table"><tr><th>Skill</th><th>Level</th><th>Score</th><th>Source</th></tr>${learned.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(lvl[x.level]||'Not assessed')}</td><td>${x.score}</td><td>${esc(x.source||'Student record')}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No verified skills yet. Complete Skill Assessment to build your learned-skill profile.</td></tr>'}</table>`):'')+
  (f.has_resume?card(`<h3>3. Which companies need your skills?</h3><p class="muted">This is the direct bridge from your resume to real local demand. Companies below are hiring for skills detected in your resume.</p>${employerRows.length?`<table class="table"><tr><th>Your skill</th><th>Company</th><th>Job</th><th>Openings</th><th>Location</th></tr>${employerRows.map(x=>`<tr><td><b>${esc(x.skill_name)}</b><br>${sourceBadge(resumeSkills.find(s=>s.name===x.skill_name)?.id||'')}</td><td>${esc(x.company_name)}</td><td>${esc(x.job_title)}</td><td>${x.openings}</td><td>${esc(x.location_text||'')}</td></tr>`).join('')}</table>`:'<div class="notice">No current local employer openings matched the skills found in this resume. Check another district or use the Skill Gap / Path Navigator to identify what to learn next.</div>'}${employerDemand.filter(x=>arr(x.employers).length).map(x=>`<div class="notice" style="margin-top:8px"><b>${esc(x.skill_name)}</b> is currently needed by ${x.employers.length} employer/job combinations.</div>`).join('')}`):'')+
  (f.has_resume?card(`<h3>4. Where should you apply?</h3><table class="table"><tr><th>Role / Job</th><th>Employer</th><th>Openings</th><th>Skill match</th><th>Missing skills</th><th>Action</th></tr>${jobs.map(x=>`<tr><td>${esc(x.title)}</td><td>${esc(x.company_name)}</td><td>${x.openings}</td><td><span class="pill">${x.match}%</span></td><td>${arr(x.missing_skill_ids).length || 0}</td><td>${actionButton('View Jobs',`renderPage('jobs')`,'secondary')}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No current job matches.</td></tr>'}</table>`):'')+
  (f.has_resume?card(`<h3>5. What should you learn next?</h3><div class="grid">${matched.length?card(`<div class="muted">Already aligned with target role</div><div style="margin-top:6px">${matched.map(x=>`<span class="pill">${esc(x.name)}</span>`).join(' ')}</div>`,'sm'):''}${missing.length?card(`<div class="muted">Current gaps</div><div style="margin-top:6px">${missing.map(x=>`<span class="pill">${esc(x.name)}</span>`).join(' ')}</div><div style="margin-top:10px">${actionButton('Open Skill Gap',`renderPage('gap')`)}</div>`,'sm'):card('<div class="muted">Role skill coverage</div><b>All role skills detected</b>','sm')}${card(`<div class="muted">Highest-value next skill</div><div style="margin-top:6px"><b>${esc(f.next_skill||'Complete')}</b></div><div class="muted" style="margin-top:5px">Projected fitness: ${f.projected_after_next_skill}%</div><div style="margin-top:10px">${actionButton('Build learning path',`renderPage('path')`,'secondary')}</div>`,'sm')}</div>`):'');
  $('#resumeForm').onsubmit=uploadResume;
}
async function uploadResume(e){
  e.preventDefault();
  const file=$('#resumeFile')?.files?.[0];
  if(!file)return;
  try{
    const fd=new FormData(); fd.append('file',file);
    await api('/api/student/resume',{method:'POST',body:fd});
    setStatus('Resume analysed');
    $('#resumeMsg').innerHTML='<div class="notice success">Resume uploaded successfully. Skills, learned skills and employer demand have been refreshed.</div>';
    await renderPage('resume');
  }catch(err){
    $('#resumeMsg').innerHTML='<div class="notice danger">Resume analysis failed: '+esc(err.message)+'</div>';
    setStatus('Resume analysis failed',false);
  }
}
async function renderPath(w){
  const [roles0,p0]=await Promise.all([api('/api/roles'),api('/api/student/path-navigator')]); const roles=arr(roles0), p=obj(p0);
  w.innerHTML=explain('AI Skill-Path Navigator','The selected role determines the required skills. The backend stores a 12-week plan with local course suggestions and a practical project for each gap. Completing a step updates the verified student skill level.')+
  card(`<div class="row" style="justify-content:space-between"><div><h2>AI Skill-Path Navigator</h2><p class="muted">${esc(p.district)} · ${p.openings||0} relevant openings</p></div><div class="row"><select id="pathRole" class="select">${roles.map(r=>`<option value="${esc(r.id)}" ${r.id===p.role.id?'selected':''}>${esc(r.name)}</option>`).join('')}</select><button class="btn" id="generatePath">${p.path_id?'Regenerate 12-week path':'Generate 12-week path'}</button></div></div>${p.path_id?`<div class="notice" style="margin-top:14px"><b>Progress ${p.progress_pct}%</b><div class="bar" style="margin-top:8px"><div style="width:${p.progress_pct}%"></div></div></div>`:'<div class="notice" style="margin-top:14px">No saved path yet. Choose a role and generate it. This creates real rows in the learning-path tables.</div>'}<div id="pathSteps" style="margin-top:14px">${arr(p.steps).map(x=>pathStepHtml(x)).join('')||''}</div>`);
  $('#generatePath').onclick=async()=>{ await api('/api/student/path-navigator/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role_id:$('#pathRole').value,market_district_id:marketDistrictId})}); setStatus('12-week path generated and stored'); await renderPage('path'); };
}
function pathStepHtml(x){ return `<div class="notice" style="margin:8px 0"><div class="row"><b>Step ${x.step} · Weeks ${x.week_start}-${x.week_end}</b><span class="pill">${esc(x.skill)} · ${esc(x.target_level)}</span><span class="pill">${esc(x.status)}</span>${x.status!=='completed'?`<button class="btn secondary" onclick="completePathStep('${esc(x.id)}')">Mark project complete</button>`:''}</div><div class="muted" style="margin-top:7px">Course: ${esc(x.recommended_course)}</div><div style="margin-top:6px">Project: ${esc(x.project)}</div></div>`; }
async function completePathStep(id){ await api('/api/student/path-navigator/steps/'+encodeURIComponent(id)+'/complete',{method:'POST'}); setStatus('Milestone completed · skill profile updated'); await renderPage('path'); }

async function renderJobs(w){
  const [jobs0,ctx0]=await Promise.all([api('/api/student/market-jobs?limit=100'),api('/api/tenant/context')]); const jobs=arr(jobs0),ctx=obj(ctx0);
  w.innerHTML=explain('Job Recommendations','The market selector above controls the district used for local job discovery. Your profile and verified skills remain attached to your account; job listings come from the selected district.')+card(`<h2>District Job Board</h2><div class=\"muted\">${esc(ctx.district_name)} account · browsing ${esc($('#marketLabel')?.textContent||'selected market')}</div><div class=\"grid\" style=\"margin-top:14px\">${jobs.map(j=>`<div class=\"md notice\"><div class=\"row\" style=\"justify-content:space-between\"><b>${esc(j.title)}</b><span class=\"pill\">${j.openings} openings</span></div><div>${esc(j.company_name||'Employer')} · ${esc(j.role_name||'Role')}</div><div class=\"muted\" style=\"margin-top:6px\">${j.salary_min?'₹'+j.salary_min.toLocaleString('en-IN')+'–₹'+(j.salary_max||j.salary_min).toLocaleString('en-IN'):'Salary on application'}</div></div>`).join('')||`<div class=\"notice\">No verified job postings have been stored for this district yet.</div>`}</div>`);
}

async function renderMentors(w){
  const [m0,req0]=await Promise.all([api('/api/mentors'),api('/api/mentors/requests')]); const m=arr(m0), req=arr(req0);
  w.innerHTML=explain('AI-Powered Mentor Marketplace','Mentor fit is calculated from overlap between the mentor skill tags and your target role. A request is persisted in the database with your stated goal.')+
  card(`<h2>Available Mentors</h2><div class="grid">${m.map(x=>`<div class="md notice"><div class="row" style="justify-content:space-between"><b>${esc(x.name)}</b><span class="pill">${x.match}% fit</span></div><div>${esc(x.job_title)} · ${esc(x.company)}</div><div class="muted">${x.years_experience} years · ${x.available_slots} slots</div><div style="margin:7px 0">Skills: ${esc(x.skills)}</div><button class="btn" onclick="requestMentor('${esc(x.id)}')">Request mentor</button></div>`).join('')}</div>`)+
  card(`<h3>My mentorship requests</h3>${req.length?req.map(x=>`<div class="notice" style="margin:8px 0"><b>${esc(x.mentor_name)}</b> · ${esc(x.status)}<br><span class="muted">Goal: ${esc(x.goal||'')}</span></div>`).join(''):'<div class="notice">No requests yet.</div>'}`);
}
async function requestMentor(id){ const goal=window.prompt('What do you want the mentor to help you with?','Build a project, prepare for interviews and understand workplace expectations'); if(goal===null)return; await api('/api/mentors/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mentor_id:id,goal})}); setStatus('Mentor request saved'); await renderPage('mentors'); }

async function renderStudentAlerts(w){
  const [a0,actions0]=await Promise.all([api('/api/skill-alerts'),api('/api/skill-alerts/actions')]); const a=arr(a0), actions=arr(actions0);
  w.innerHTML=explain('Skill Obsolescence & Reskilling Engine','The engine compares a stored previous-quarter demand snapshot with the current district job database. The result is a transparent demand signal, not a claim that a skill is permanently obsolete.')+
  card(`<h2>Skill alerts</h2><table class="table"><tr><th>Skill</th><th>Previous openings</th><th>Current openings</th><th>Change</th><th>Status</th><th>Action</th></tr>${a.map(x=>`<tr><td>${esc(x.skill)}</td><td>${x.previous_openings}</td><td>${x.current_openings}</td><td>${x.change_pct>=0?'+':''}${x.change_pct}%</td><td><span class="pill">${esc(x.status)}</span></td><td>${actionButton('Create reskill action',`createReskill('${esc(x.skill_id)}')`)}</td></tr>`).join('')}</table>`)+
  card(`<h3>My reskilling actions</h3>${actions.length?actions.map(x=>`<div class="notice" style="margin:8px 0"><b>${esc(x.skill_name)}</b><br>${esc(x.action)} · <span class="pill">${esc(x.status)}</span></div>`).join(''):'<div class="notice">No reskilling actions created yet.</div>'}`);
}
async function createReskill(id){ await api('/api/skill-alerts/'+encodeURIComponent(id)+'/act',{method:'POST'}); setStatus('Reskilling action stored'); await renderPage('alerts2'); }

async function renderCompanies(w){
  const d=obj(await api('/api/employer/company'));
  w.innerHTML=explain('My Company','Manage your registered employer identity and see the health of the organisation workspace.')+
    card(`<div class="alignment-hero"><div class="hub-kicker">EMPLOYER IDENTITY</div><div class="hub-title">${esc(d.name)}</div><div class="hub-sub">${esc(d.sector)} · ${esc(d.size)} · ${esc(d.district)}, ${esc(d.state)}</div><div class="row" style="margin-top:12px"><span class="hub-badge">Verified employer workspace</span><span class="pill">${esc(d.status||'Active')}</span></div></div>`)+
    card(`<h2>Company performance</h2><div class="grid">${card(metric('Open positions',d.open_positions),'sm')}${card(metric('Openings',d.openings),'sm')}${card(metric('Active commitments',d.active_commitments),'sm')}${card(metric('Feedback submitted',d.feedback_count),'sm')}</div>`)+
    card(`<h2>Company profile</h2><form id="companyProfileForm"><div class="grid"><div style="grid-column:span 5"><label>Company name</label><input id="coName" value="${esc(d.name)}" required></div><div style="grid-column:span 4"><label>Industry / sector</label><input id="coSector" value="${esc(d.sector)}" required></div><div style="grid-column:span 3"><label>Company size</label><select id="coSize" class="select"><option ${d.size==='MSME'?'selected':''}>MSME</option><option ${d.size==='Large'?'selected':''}>Large</option><option ${d.size==='Startup'?'selected':''}>Startup</option></select></div><div style="grid-column:span 8"><label>Website</label><input id="coWebsite" value="${esc(d.website||'')}" placeholder="https://example.com"></div><div style="grid-column:span 4"><label>Registered district</label><input value="${esc(d.district)}" disabled></div></div><button class="btn" style="margin-top:12px">Save company profile</button></form><div id="companyMsg"></div>`);
  $('#companyProfileForm').onsubmit=async(e)=>{e.preventDefault();try{await api('/api/employer/company',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#coName').value.trim(),sector:$('#coSector').value.trim(),size:$('#coSize').value,website:$('#coWebsite').value.trim()})});setStatus('Company profile saved');await renderPage('companies');}catch(err){$('#companyMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}

async function renderDemand(w){ return renderEmployerJobs(w); }
async function renderEmployerJobs(w){
  const [d0,roles0]=await Promise.all([api('/api/employer/jobs'),api('/api/roles')]); const d=obj(d0),roles=arr(roles0),jobs=arr(d.jobs);
  const jobHtml=jobs.map(x=>{const pay=x.salary_min?('₹'+Number(x.salary_min).toLocaleString('en-IN')+' – ₹'+Number(x.salary_max||x.salary_min).toLocaleString('en-IN')):'Salary on application'; const act=(x.status==='open'?actionButton('Close job',`closeEmployerJob('${esc(x.id)}')`,'secondary'):actionButton('Reopen',`reopenEmployerJob('${esc(x.id)}')`,'secondary'))+' '+actionButton('Edit',`editEmployerJob('${esc(x.id)}')`,'secondary'); return `<div class="notice" style="margin:8px 0"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><b>${esc(x.title)}</b><div class="muted">${esc(x.role_name)} · ${x.openings} openings · ${esc(x.location_text||'Location not specified')}</div><div class="muted">${pay}</div><div style="margin-top:6px"><span class="pill">${esc(x.status)}</span></div></div>${act}</div></div>`;}).join('');
  const roleHtml=roles.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  w.innerHTML=explain('Jobs & Hiring','Create real vacancies. The selected occupation controls the normalized skills used by Candidate Pool and Skill Requirements.')+
    card(`<div class="grid">${card(metric('Open jobs',d.open_positions),'sm')}${card(metric('Openings',d.openings),'sm')}${card(metric('Closed jobs',d.closed_jobs),'sm')}${card(metric('Candidate matches',d.matches||0),'sm')}</div>`)+
    card(`<h2>My jobs</h2><p class="muted">Only vacancies owned by your company are shown.</p>${jobHtml||'<div class="notice">No jobs posted yet.</div>'}`)+
    card(`<h2>Post a new job</h2><form id="jobForm"><div class="grid"><div style="grid-column:span 4"><label>Occupation / role</label><select id="jobRole" class="select" required>${roleHtml}</select></div><div style="grid-column:span 4"><label>Job title</label><input id="jobTitle" placeholder="Industrial Automation Technician" required></div><div style="grid-column:span 2"><label>Vacancies</label><input id="jobOpenings" type="number" min="1" value="10" required></div><div style="grid-column:span 2"><label>Work location</label><input id="jobLocation" value="${esc(currentUser?.district_name||'Puducherry')}" required></div><div style="grid-column:span 3"><label>Minimum salary</label><input id="jobMin" type="number" min="0" value="20000"></div><div style="grid-column:span 3"><label>Maximum salary</label><input id="jobMax" type="number" min="0" value="35000"></div></div><div class="notice" style="margin-top:12px">Publishing converts this vacancy into a district employer-demand signal and drives your skill requirements.</div><button class="btn" style="margin-top:12px">Publish job</button></form><div id="jobMsg"></div>`);
  $('#jobForm').onsubmit=async(e)=>{e.preventDefault();try{const min=Number($('#jobMin').value||0),max=Number($('#jobMax').value||0),openings=Number($('#jobOpenings').value||0);if(openings<1)throw new Error('Vacancies must be at least 1.');if(max&&min>max)throw new Error('Maximum salary must be greater than or equal to minimum salary.');await api('/api/industry/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:d.company.id,role_id:$('#jobRole').value,title:$('#jobTitle').value.trim(),openings,salary_min:min,salary_max:max,location_text:$('#jobLocation').value.trim()})});setStatus('Job published');await renderPage('demand');}catch(err){$('#jobMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}
async function closeEmployerJob(id){try{await api('/api/employer/jobs/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'closed'})});setStatus('Job closed');await renderPage('demand');}catch(err){setStatus(err.message,false);}}
async function reopenEmployerJob(id){try{await api('/api/employer/jobs/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'open'})});setStatus('Job reopened');await renderPage('demand');}catch(err){setStatus(err.message,false);}}
async function editEmployerJob(id){
  try{
    const d=obj(await api('/api/employer/jobs')); const x=arr(d.jobs).find(v=>v.id===id); if(!x) throw new Error('Job not found');
    const title=window.prompt('Job title',x.title); if(title===null)return;
    const openingsRaw=window.prompt('Vacancies',String(x.openings)); if(openingsRaw===null)return;
    const location=window.prompt('Work location',x.location_text||''); if(location===null)return;
    const minRaw=window.prompt('Minimum salary',String(x.salary_min||0)); if(minRaw===null)return;
    const maxRaw=window.prompt('Maximum salary',String(x.salary_max||0)); if(maxRaw===null)return;
    const openings=Number(openingsRaw), salary_min=Number(minRaw||0), salary_max=Number(maxRaw||0);
    if(!title.trim()) throw new Error('Job title is required.');
    if(!Number.isInteger(openings)||openings<1) throw new Error('Vacancies must be at least 1.');
    if(salary_max && salary_min>salary_max) throw new Error('Maximum salary must be greater than or equal to minimum salary.');
    await api('/api/employer/jobs/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:title.trim(),openings,location_text:location.trim(),salary_min,salary_max})});
    setStatus('Job updated'); await renderPage('demand');
  }catch(err){setStatus(err.message,false);}
}

async function renderFeedback(w){
  const [f0,c0,r0]=await Promise.all([api('/api/employer/feedback'),api('/api/employer/company'),api('/api/roles')]); const f=arr(f0),c=obj(c0),roles=arr(r0);
  const history=f.map(x=>`<div class="notice" style="margin:8px 0"><b>${esc(x.role_name||'General')}</b> · ${x.rating}/5<div class="muted">${esc(x.created_at||'')}</div><div style="margin-top:5px">${esc(x.comment||'')}</div></div>`).join('');
  w.innerHTML=explain('Employer Feedback','Record what is working and what is missing in trained candidates. This evidence can be reviewed by district administrators and used to improve training.')+
    card(`<h2>Submit employer feedback</h2><span class="pill">${esc(c.name)}</span><form id="fb" style="margin-top:12px"><div class="grid"><div style="grid-column:span 4"><label>Role</label><select id="fbRole" class="select"><option value="">General</option>${roles.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></div><div style="grid-column:span 2"><label>Rating</label><select id="fbRating" class="select"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></div><div style="grid-column:span 6"><label>Missing skills</label><input id="fbMissing" placeholder="SCADA, IoT"></div><div style="grid-column:span 12"><label>Feedback</label><textarea id="fbComment" placeholder="What is working? What should training change?" required style="min-height:110px"></textarea></div></div><button class="btn" style="margin-top:12px">Submit feedback</button></form><div id="fbMsg"></div>`)+
    card(`<h2>Submitted feedback</h2>${history||'<div class="notice">No employer feedback yet.</div>'}`);
  $('#fb').onsubmit=async(e)=>{e.preventDefault();try{await api('/api/employer/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:c.id,role_id:$('#fbRole').value||null,rating:Number($('#fbRating').value),missing_skills:$('#fbMissing').value.split(',').map(x=>x.trim()).filter(Boolean),comment:$('#fbComment').value.trim()})});setStatus('Employer feedback stored');await renderPage('feedback');}catch(err){$('#fbMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}

async function renderEmployerSkills(w){
  const [d0,skills0]=await Promise.all([api('/api/employer/skill-requirements'),api('/api/skills')]);
  const d=obj(d0), skills=arr(d.skills); const levelName={1:'Beginner',2:'Intermediate',3:'Advanced'};
  const rows=skills.map(x=>`<div class="notice" style="margin:8px 0"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><b>${esc(x.name)}</b><div class="muted">${esc(x.category)} · ${x.jobs} active job(s) · ${x.openings} hiring need</div></div><span class="pill">${esc(x.importance)}</span></div><div class="grid" style="margin-top:10px"><div><div class="muted">Required proficiency</div><b>${esc(levelName[x.proficiency_level]||'Intermediate')}</b></div><div><div class="muted">Local training seats</div><b>${x.training_supply}</b></div><div><div class="muted">Coverage</div><b>${x.coverage}%</b></div><div><div class="muted">Action</div><b>${esc(x.action)}</b></div></div><form id="skill-${esc(x.skill_id)}" style="margin-top:10px"><div class="grid"><select class="select" id="imp-${esc(x.skill_id)}" style="grid-column:span 3"><option ${x.importance==='Critical'?'selected':''}>Critical</option><option ${x.importance==='High'?'selected':''}>High</option><option ${x.importance==='Important'?'selected':''}>Important</option><option ${x.importance==='Medium'?'selected':''}>Medium</option></select><select class="select" id="lvl-${esc(x.skill_id)}" style="grid-column:span 3"><option value="1" ${x.proficiency_level===1?'selected':''}>Beginner</option><option value="2" ${x.proficiency_level===2?'selected':''}>Intermediate</option><option value="3" ${x.proficiency_level===3?'selected':''}>Advanced</option></select><input id="note-${esc(x.skill_id)}" value="${esc(x.notes||'')}" placeholder="Business note / practical expectation" style="grid-column:span 6"><button class="btn secondary" style="grid-column:span 2;margin-top:8px">Save requirement</button></div></form></div>`).join('');
  const createSkills=arr(skills0).filter(s=>!skills.some(x=>x.skill_id===s.id)).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  w.innerHTML=explain('Skill Requirements','Define the exact competency level your company expects. Requirements from your active jobs are preloaded; your saved importance and proficiency become auditable employer evidence for training decisions.')+
    card(`<div class="grid">${card(metric('Open jobs',d.open_jobs),'sm')}${card(metric('Required skills',skills.length),'sm')}${card(metric('Critical skills',d.critical_count),'sm')}${card(metric('Openings',d.openings),'sm')}</div>`)+
    card(`<h2>Employer skill requirements</h2><p class="muted">Set importance, expected proficiency and a practical note for every skill your open jobs require.</p>${rows||'<div class="notice">Post an active job in Jobs & Hiring first. The system will derive the required skills here.</div>'}`)+
    card(`<h2>Add a custom requirement</h2><form id="customSkillForm"><div class="grid"><select id="customSkill" class="select" style="grid-column:span 4" required>${createSkills||'<option value="">All available skills are already represented by active jobs</option>'}</select><select id="customImportance" class="select" style="grid-column:span 2"><option>Critical</option><option selected>High</option><option>Important</option><option>Medium</option></select><select id="customLevel" class="select" style="grid-column:span 2"><option value="1">Beginner</option><option value="2" selected>Intermediate</option><option value="3">Advanced</option></select><input id="customNotes" placeholder="Why this skill matters" style="grid-column:span 4"><button class="btn" style="margin-top:10px">Save custom requirement</button></div></form><div id="skillMsg"></div>`);
  skills.forEach(x=>{ const f=$('#skill-'+x.skill_id); if(!f)return; f.onsubmit=async(e)=>{e.preventDefault();try{await api('/api/employer/skill-requirements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:x.skill_id,importance:$('#imp-'+x.skill_id).value,proficiency_level:Number($('#lvl-'+x.skill_id).value),notes:$('#note-'+x.skill_id).value.trim()})});setStatus('Skill requirement saved');await renderPage('employerSkills');}catch(err){setStatus(err.message,false);}}; });
  const cf=$('#customSkillForm'); if(cf) cf.onsubmit=async(e)=>{e.preventDefault(); if(!$('#customSkill').value){$('#skillMsg').innerHTML='<div class="notice danger">Choose a skill that is not already represented by an active job.</div>';return;} try{await api('/api/employer/skill-requirements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:$('#customSkill').value,importance:$('#customImportance').value,proficiency_level:Number($('#customLevel').value),notes:$('#customNotes').value.trim()})});setStatus('Custom skill requirement saved');await renderPage('employerSkills');}catch(err){$('#skillMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}
async function renderCandidates(w){
  const cands=arr(await api('/api/employment/candidates')); const assigned=cands.filter(x=>x.invite_status); const avg=cands.length?Math.round(cands.reduce((a,x)=>a+x.match,0)/cands.length):0;
  const list=cands.map(x=>{
    const matched=esc((x.matched_skills||[]).join(', ')||'None'), missing=esc((x.missing_skills||[]).join(', ')||'None');
    const action=x.invite_status&&x.invite_status!=='joined'?actionButton('Manage hiring',`renderPage('outcomes')`,'secondary'):actionButton('Invite to interview',`inviteCandidate('${esc(x.company_id)}','${esc(x.student_id)}','${esc(x.job_id)}')`,'secondary');
    return `<div class="notice candidate-card" style="margin:8px 0"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><b>${esc(x.student_name)}</b><div class="muted">${esc(x.job_title)} · ${esc(x.qualification||'Qualification not recorded')}</div><div class="muted">${esc(x.location_text||'')}${x.salary_min?' · ₹'+Number(x.salary_min).toLocaleString('en-IN')+' – ₹'+Number(x.salary_max||x.salary_min).toLocaleString('en-IN'):''}</div></div><div style="text-align:right"><div style="font-size:24px;font-weight:900">${x.match}%</div><div class="muted">skill match</div></div></div><div class="grid" style="margin-top:10px"><div style="grid-column:span 5"><div class="muted">Matched skills</div><b>${matched}</b></div><div style="grid-column:span 5"><div class="muted">Current gaps</div><b>${missing}</b></div><div style="grid-column:span 2"><div class="muted">Status</div><b>${esc(x.invite_status||'Not invited')}</b></div></div><div class="row" style="margin-top:10px;justify-content:space-between"><span class="muted">${esc(x.match_explanation||'')}</span>${action}</div></div>`;
  }).join('');
  w.innerHTML=explain('Candidate Pool','Candidates are ranked against your company’s open jobs using normalized role skills. Inspect the evidence, then move suitable candidates into the hiring pipeline.')+
    card(`<div class="grid">${card(metric('Candidate-job matches',cands.length),'sm')}${card(metric('Average match',avg+'%'),'sm')}${card(metric('75%+ strong matches',cands.filter(x=>x.match>=75).length),'sm')}${card(metric('Already invited',assigned.length),'sm')}</div>`)+
    card(`<div class="row" style="justify-content:space-between"><div><h2>Ranked candidate matches</h2><p class="muted">Higher match means more required skills meet the target proficiency.</p></div><span class="pill">${cands.length} results</span></div>${list||'<div class="notice">No candidates currently match your open jobs. Create or reopen a job to generate a candidate pool.</div>'}`);
}
async function inviteCandidate(companyId,studentId,jobId){try{const r=await api('/api/employment/invite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:companyId,student_id:studentId,job_id:jobId})});setStatus(r.existing?'Candidate already in pipeline':'Interview invitation stored');await renderPage('candidates');}catch(err){setStatus(err.message,false);}}

async function renderTrainingPartnership(w){
  const [d,courses0,skills0]=await Promise.all([api('/api/employer/training-partnership'),api('/api/district/skill-academy'),api('/api/skills')]); const courses=obj(courses0),skills=arr(skills0),reqs=arr(d.requests);
  const reqHtml=reqs.map(x=>`<div class="notice" style="margin:8px 0"><div class="row" style="justify-content:space-between"><div><b>${esc(x.title)}</b><div class="muted">${esc(x.request_type)}${x.skill_name?' · '+esc(x.skill_name):''} · ${esc(x.created_at||'')}</div><div style="margin-top:5px">${esc(x.details)}</div></div><span class="pill">${esc(x.status)}</span></div></div>`).join('');
  const courseHtml=arr(courses.courses).slice(0,12).map(x=>`<div class="md notice"><b>${esc(x.name)}</b><div class="muted">${esc(x.provider_name)} · ${x.seats} seats · ${x.duration_weeks} weeks</div><div class="muted" style="margin-top:5px">${esc(x.skills||'No mapped skills')}</div></div>`).join('');
  w.innerHTML=explain('Training Partnership','Turn employer capability gaps into structured requests for curriculum updates, practical exposure, internships, trainer upskilling or targeted training seats. Requests become evidence for training-provider and district planning.')+
    card(`<div class="grid">${card(metric('Requests',reqs.length),'sm')}${card(metric('Pending',d.pending),'sm')}${card(metric('Actioned',d.actioned),'sm')}${card(metric('Local providers',d.providers),'sm')}</div>`)+
    card(`<h2>Create a partnership request</h2><form id="tpForm"><div class="grid"><div style="grid-column:span 3"><label>Request type</label><select id="tpType" class="select"><option>Curriculum Update</option><option>Practical Training</option><option>Industry Visit</option><option>Internship / Apprenticeship</option><option>Guest Faculty</option><option>Trainer Upskilling</option><option>Equipment Exposure</option><option>Training Seats</option></select></div><div style="grid-column:span 3"><label>Related skill</label><select id="tpSkill" class="select"><option value="">Not skill-specific</option>${skills.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></div><div style="grid-column:span 6"><label>Request title</label><input id="tpTitle" placeholder="e.g. Add hands-on SCADA module" required></div><div style="grid-column:span 12"><label>Business need</label><textarea id="tpDetails" placeholder="Describe expected hiring, candidate gap, target volume and what should change." style="min-height:120px" required></textarea></div></div><button class="btn">Submit partnership request</button></form><div id="tpMsg"></div>`)+
    card(`<h2>My requests</h2>${reqHtml||'<div class="notice">No partnership requests yet.</div>'}`)+
    card(`<h2>Local training supply</h2><div class="grid">${courseHtml||'<div class="notice">No courses found in this market.</div>'}</div>`);
  $('#tpForm').onsubmit=async(e)=>{e.preventDefault();try{await api('/api/employer/training-partnership',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_type:$('#tpType').value,skill_id:$('#tpSkill').value||null,title:$('#tpTitle').value.trim(),details:$('#tpDetails').value.trim()})});setStatus('Training partnership request submitted');await renderPage('trainingPartnership');}catch(err){$('#tpMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}

async function renderHiringOutcomes(w){
  const d=obj(await api('/api/employer/hiring-outcomes')); const inv=arr(d.invitations);
  const conversion=d.invited?Math.round(d.joined/d.invited*100):0;
  w.innerHTML=explain('Hiring Outcomes','Track what happened after candidate matching: invitations, interviews, offers, hires and confirmed joins. This outcome evidence feeds employer accountability and district training decisions.')+
  card(`<div class="grid">${card(metric('Open positions',d.open_positions),'sm')}${card(metric('Invited',d.invited),'sm')}${card(metric('Interviewed',d.interviewed),'sm')}${card(metric('Offers made',d.offered),'sm')}${card(metric('Hired',d.hired),'sm')}${card(metric('Joined',d.joined),'sm')}</div>`)+
  card(`<div class="row" style="justify-content:space-between"><h2>Hiring funnel</h2><span class="pill">Join conversion ${conversion}%</span></div><div class="hub-flow"><div class="flow-step"><div class="flow-number">01</div><b>${d.invited}</b><span>Invited</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">02</div><b>${d.interviewed}</b><span>Interviewed</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">03</div><b>${d.offered}</b><span>Offers</span></div><div class="flow-line"></div><div class="flow-step"><div class="flow-number">04</div><b>${d.joined}</b><span>Joined</span></div></div>`)+
  card(`<h2>Candidate pipeline</h2><table class="table"><tr><th>Candidate</th><th>Job</th><th>Status</th><th>Action</th></tr>${inv.map(x=>`<tr><td>${esc(x.student_name)}</td><td>${esc(x.job_title||'Job')}</td><td><span class="pill">${esc(x.status)}</span></td><td>${x.status==='joined'?'<span class="muted">Complete</span>':`<button class="btn secondary" onclick="setInviteStatus('${esc(x.id)}','${x.status==='invited'?'interviewed':(x.status==='interviewed'?'offered':(x.status==='offered'?'hired':'joined'))}')">${x.status==='invited'?'Mark interviewed':x.status==='interviewed'?'Make offer':x.status==='offered'?'Mark hired':'Mark joined'}</button>`}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No hiring activity yet. Use Candidate Pool to invite a candidate.</td></tr>'}</table>`)+
  card(`<h2>Outcome evidence</h2><div class="grid"><div class="notice"><b>Commitment fulfilment</b><br><span class="metric">${d.commitment_fulfilment}%</span><div class="muted">${d.commitment_hired} of ${d.commitment_committed} committed positions recorded as hired.</div></div><div class="notice"><b>Production rollout note</b><br><span class="muted">${esc(d.retention_note||'Retention metrics require post-joining outcome capture.')}</span></div></div>`);
}
async function setInviteStatus(id,status){try{await api('/api/employment/invites/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});setStatus('Hiring stage updated');await renderPage('outcomes');}catch(err){setStatus(err.message,false);}}
async function renderCommitments(w){
  const [comm0,company,roles0]=await Promise.all([api('/api/employment/commitments'),api('/api/employer/company'),api('/api/roles')]); const comm=arr(comm0), roles=arr(roles0), c=obj(company);
  const commHtml=comm.map(x=>{const pct=x.committed_slots?Math.min(100,Math.round(x.hired_slots/x.committed_slots*100)):0;return `<div class="notice" style="margin:8px 0"><div class="row" style="justify-content:space-between"><div><b>${esc(x.role_name)}</b><div class="muted">${x.committed_slots} committed · ${x.hired_slots} hired · valid until ${esc(x.valid_until||'—')}</div></div><div class="row"><input type="number" min="0" max="${x.committed_slots}" value="${x.hired_slots}" id="hire-${esc(x.id)}" style="width:90px"><button class="btn secondary" onclick="updateHired('${esc(x.id)}',${x.committed_slots})">Update</button></div></div><div class="bar" style="margin-top:8px"><div style="width:${pct}%"></div></div></div>`;}).join('');
  const roleHtml=roles.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  const total=comm.reduce((a,x)=>a+Number(x.committed_slots||0),0), hired=comm.reduce((a,x)=>a+Number(x.hired_slots||0),0), remaining=comm.reduce((a,x)=>a+Math.max(0,Number(x.committed_slots||0)-Number(x.hired_slots||0)),0);
  w.innerHTML=explain('Employment Commitments','Commit future hiring needs so district planning can use employer intent, then update fulfilment as hiring progresses.')+card(`<div class="grid">${card(metric('Active commitments',comm.length),'sm')}${card(metric('Committed positions',total),'sm')}${card(metric('Hired',hired),'sm')}${card(metric('Remaining',remaining),'sm')}</div>`)+card(`<h2>My commitments</h2>${commHtml||'<div class="notice">No commitments yet.</div>'}`)+card(`<h2>Create hiring commitment</h2><p class="muted">Company: <b>${esc(c.name)}</b></p><form id="commitForm"><div class="grid"><div style="grid-column:span 5"><label>Occupation</label><select id="cr" class="select">${roleHtml}</select></div><div style="grid-column:span 2"><label>Positions</label><input id="slots" type="number" min="1" value="25"></div><div style="grid-column:span 3"><label>Valid until</label><input id="validUntil" type="date" value="2027-03-31"></div><div style="grid-column:span 12"><label>Notes</label><input id="commitNotes" placeholder="Expected hiring plan / capability need"></div></div><button class="btn" style="margin-top:12px">Save commitment</button></form><div id="commitMsg"></div>`);
  $('#commitForm').onsubmit=async(e)=>{e.preventDefault();try{const slots=Number($('#slots').value||0);if(slots<1)throw new Error('Positions must be at least 1.');await api('/api/employment/commitments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:c.id,role_id:$('#cr').value,committed_slots:slots,valid_until:$('#validUntil').value,notes:$('#commitNotes').value.trim()})});setStatus('Employment commitment saved');await renderPage('commitments');}catch(err){$('#commitMsg').innerHTML='<div class="notice danger">'+esc(err.message)+'</div>';}};
}
async function updateHired(id,max){const val=Number($('#hire-'+id).value);if(val<0||val>max){alert('Hired slots must be between 0 and the committed positions.');return;}try{await api('/api/employment/commitments/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({hired_slots:val})});setStatus('Hiring progress updated');await renderPage('commitments');}catch(err){setStatus(err.message,false);}}

function providerHeader(title,subtitle){ return `<div class="alignment-hero" style="margin-bottom:16px"><div class="hub-kicker">TRAINING PROVIDER CONTROL CENTRE</div><div class="hub-title">${esc(title)}</div><div class="hub-sub">${esc(subtitle)}</div></div>`; }
function providerWriteGuard(){ return isAssignedMarket() ? '' : '<div class="notice danger" style="margin-bottom:14px"><b>Read-only market view.</b> Switch the market selector back to your registered district before saving provider data.</div>'; }

async function renderProviderCentre(w){
  const d=obj(await api('/api/provider/overview'));
  w.innerHTML=providerHeader('My Centre','One place to manage centre identity, course supply, resources and outcomes while seeing how your capacity lines up with local employer demand.')+
    card(`<div class="row" style="justify-content:space-between"><div><h2>${esc(d.provider.name)}</h2><div class="muted">${esc(d.provider.provider_type)} · ${esc(d.district)}, ${esc(d.state)}</div></div><span class="hub-badge">Registered provider</span></div><div class="grid" style="margin-top:16px">${card(metric('Active courses',d.course_count),'sm')}${card(metric('Annual seats',d.training_capacity),'sm')}${card(metric('Local openings',d.market_openings),'sm')}${card(metric('Placed students',d.placed_students),'sm')}</div>`)+
    `<div class="grid" style="margin-top:16px">`+
    card(`<h3>Centre readiness</h3><div class="row"><span class="pill">${d.trainer_count} active trainers</span><span class="pill">${d.equipment_count} equipment records</span></div><p class="muted">Keep resource records current so course capacity recommendations are grounded in what the centre can actually deliver.</p>`,'md')+
    card(`<h3>Provider workflow</h3><div class="row"><button class="btn secondary" onclick="renderPage('providerCourses')">Manage courses</button><button class="btn secondary" onclick="renderPage('providerSkills')">Review skills</button><button class="btn secondary" onclick="renderPage('providerCapacity')">Check capacity</button></div>`,'md')+
    `</div>`;
}

async function renderProviderCourses(w){
  const [courses,skills]=await Promise.all([arr(await api('/api/provider/courses')),arr(await api('/api/skills'))]);
  const cards=courses.map(x=>`<div class="md notice"><div class="row" style="justify-content:space-between"><div><b>${esc(x.name)}</b><div class="muted">${x.duration_weeks} weeks · ${x.seats} seats</div></div><span class="pill">${esc(x.status)}</span></div><div style="margin-top:9px">${x.skills.map(s=>`<span class="pill">${esc(s.name)}</span>`).join('')||'<span class="muted">No skills mapped</span>'}</div><div style="margin-top:12px"><button class="btn secondary" onclick="prefillProviderCourse('${esc(x.id)}')">Edit</button></div></div>`).join('');
  w.innerHTML=providerHeader('Courses','Create and maintain the courses delivered by your centre. Each course is linked to a skill set so demand-to-supply analysis can explain why a course should scale or change.')+
    providerWriteGuard()+card(`<div class="row" style="justify-content:space-between"><h2>Course Library</h2><span class="muted">${courses.length} courses registered</span></div><div class="grid" style="margin-top:12px">${cards||'<div class="notice">No courses found for this provider.</div>'}</div>`)+
    card(`<h2 id="providerCourseFormTitle">Add course</h2><form id="providerCourseForm"><input type="hidden" id="pcId"><div class="grid"><div style="grid-column:span 5"><label>Course name</label><input id="pcName" placeholder="e.g. Industrial Automation Technician" required style="width:100%"></div><div style="grid-column:span 2"><label>Duration (weeks)</label><input id="pcWeeks" type="number" min="1" value="12" required style="width:100%"></div><div style="grid-column:span 2"><label>Seats</label><input id="pcSeats" type="number" min="1" value="60" required style="width:100%"></div><div style="grid-column:span 3"><label>Skills</label><select id="pcSkills" multiple class="select" style="width:100%;min-width:0;height:120px">${skills.map(s=>`<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}</select></div></div><div class="row" style="margin-top:14px"><button class="btn">Save course</button><button type="button" class="btn secondary" onclick="resetProviderCourseForm()">Clear</button></div><div id="pcMsg"></div></form>`);
  $('#providerCourseForm').onsubmit=async e=>{e.preventDefault();if(!isAssignedMarket()){return $('#pcMsg').innerHTML='<div class="notice danger">Switch back to your registered district to save.</div>';} const payload={name:$('#pcName').value.trim(),duration_weeks:Number($('#pcWeeks').value),seats:Number($('#pcSeats').value),skill_ids:[...$('#pcSkills').selectedOptions].map(x=>x.value)}; const id=$('#pcId').value; await api(id?'/api/provider/courses/'+encodeURIComponent(id):'/api/provider/courses',{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); setStatus(id?'Course updated':'Course created'); await renderPage('providerCourses');};
  window.__providerSkills=skills;
}
function resetProviderCourseForm(){ ['pcId','pcName'].forEach(id=>$('#'+id).value=''); $('#pcWeeks').value=12;$('#pcSeats').value=60; $('#pcSkills').selectedIndex=-1; $('#providerCourseFormTitle').textContent='Add course'; }
async function prefillProviderCourse(id){ const courses=arr(await api('/api/provider/courses')); const x=courses.find(v=>v.id===id); if(!x)return; $('#pcId').value=x.id;$('#pcName').value=x.name;$('#pcWeeks').value=x.duration_weeks;$('#pcSeats').value=x.seats; [...$('#pcSkills').options].forEach(o=>o.selected=x.skills.some(s=>s.id===o.value)); $('#providerCourseFormTitle').textContent='Edit course · '+x.name; window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'}); }

async function renderProviderSkills(w){
  const d=obj(await api('/api/provider/skills')); const rows=arr(d.skills);
  w.innerHTML=providerHeader('Skills Taught','See the skill coverage your centre currently supplies, how strong the local demand is, and where capacity is falling behind the market.')+
    card(`<div class="row" style="justify-content:space-between"><div><h2>Skill Coverage Matrix</h2><p class="muted">Demand is derived from the shared local market engine; training supply is the seats attached to your active courses.</p></div><span class="hub-badge">District: ${esc(d.district)}</span></div><div style="overflow:auto;margin-top:14px"><table class="table"><tr><th>Skill</th><th>Demand</th><th>Supply</th><th>Gap</th><th>12M trend</th><th>Priority</th><th>Action</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.name)}</b><br><span class="muted">${esc(x.category)}</span></td><td>${x.demand_openings}</td><td>${x.training_supply}</td><td><span class="pill">${x.gap}</span></td><td>${Number(x.growth_pct||0)>0?'↑ ':''}${x.growth_pct||0}%</td><td><span class="pill">${esc(x.priority)}</span></td><td>${esc(x.action)}</td></tr>`).join('')}</table></div>`);
}

async function renderProviderCapacity(w){
  const d=obj(await api('/api/provider/capacity')); const rows=arr(d.courses);
  w.innerHTML=providerHeader('Training Capacity','Measure capacity against market demand and see concrete actions for seats, utilization and course health.')+
    card(`<div class="grid">${card(metric('Centre capacity',d.total_capacity),'sm')}${card(metric('Market openings',d.market_openings),'sm')}${card(metric('Capacity gap',d.capacity_gap),'sm')}${card(metric('Active courses',rows.filter(x=>x.active).length),'sm')}</div>`)+
    card(`<h2>Capacity by Course</h2><table class="table"><tr><th>Course</th><th>Seats</th><th>Demand signal</th><th>Utilization</th><th>Health</th><th>Recommendation</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${x.seats}</td><td>${x.demand_openings}</td><td><div class="bar"><div style="width:${Math.min(100,x.utilization)}%"></div></div><span class="muted">${x.utilization}%</span></td><td>${x.health_score}/100</td><td><span class="pill">${esc(x.recommendation)}</span></td></tr>`).join('')}</table>`)+
    card(`<h2>Decision logic</h2><div class="grid"><div class="md notice"><b>Scale</b><br><span class="muted">Increase seats when local demand is higher than available training capacity.</span></div><div class="md notice"><b>Review</b><br><span class="muted">Reduce or rethink intake when supply materially exceeds demand.</span></div></div>`);
}

async function renderProviderResources(w){
  const d=obj(await api('/api/provider/resources')); const trainers=arr(d.trainers), equipment=arr(d.equipment);
  w.innerHTML=providerHeader('Trainers & Equipment','Track the human and physical resources behind each course. These records make capacity recommendations operational rather than theoretical.')+
    providerWriteGuard()+
    `<div class="grid">${card(`<div class="row" style="justify-content:space-between"><h2>Trainers</h2><span class="hub-badge">${trainers.length} records</span></div><table class="table" style="margin-top:12px"><tr><th>Name</th><th>Specialization</th><th>Skills</th><th>Experience</th><th>Availability</th></tr>${trainers.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.specialization)}</td><td>${esc(x.skills)}</td><td>${x.experience_years} yrs</td><td><span class="pill">${esc(x.availability)}</span></td></tr>`).join('')}</table>`,'md')+card(`<div class="row" style="justify-content:space-between"><h2>Equipment</h2><span class="hub-badge">${equipment.length} records</span></div><table class="table" style="margin-top:12px"><tr><th>Equipment</th><th>Required</th><th>Available</th><th>Utilization</th><th>Status</th></tr>${equipment.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${x.required_qty}</td><td>${x.available_qty}</td><td>${x.utilization_pct}%</td><td><span class="pill">${esc(x.status)}</span></td></tr>`).join('')}</table>`,'md')}</div>`+
    card(`<h2>Add Resource</h2><div class="grid"><form id="trainerForm" class="md notice"><h3>Trainer</h3><input id="trName" placeholder="Trainer name" required style="width:100%;margin:7px 0"><input id="trSpec" placeholder="Specialization" style="width:100%;margin:7px 0"><input id="trSkills" placeholder="Skills: PLC, SCADA" style="width:100%;margin:7px 0"><input id="trExp" type="number" min="0" value="2" placeholder="Years" style="width:100%;margin:7px 0"><button class="btn">Add trainer</button></form><form id="equipmentForm" class="md notice"><h3>Equipment</h3><input id="eqName" placeholder="Equipment name" required style="width:100%;margin:7px 0"><input id="eqReq" type="number" min="0" value="10" placeholder="Required" style="width:100%;margin:7px 0"><input id="eqAvail" type="number" min="0" value="7" placeholder="Available" style="width:100%;margin:7px 0"><input id="eqUtil" type="number" min="0" max="100" value="80" placeholder="Utilization %" style="width:100%;margin:7px 0"><button class="btn">Add equipment</button></form></div><div id="resourceMsg"></div>`);
  $('#trainerForm').onsubmit=async e=>{e.preventDefault();if(!isAssignedMarket())return $('#resourceMsg').innerHTML='<div class="notice danger">Switch back to your registered district to save.</div>';await api('/api/provider/trainers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#trName').value.trim(),specialization:$('#trSpec').value.trim(),skills:$('#trSkills').value.trim(),experience_years:Number($('#trExp').value),availability:'Available'})});setStatus('Trainer added');await renderPage('providerResources');};
  $('#equipmentForm').onsubmit=async e=>{e.preventDefault();if(!isAssignedMarket())return $('#resourceMsg').innerHTML='<div class="notice danger">Switch back to your registered district to save.</div>';await api('/api/provider/equipment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#eqName').value.trim(),required_qty:Number($('#eqReq').value),available_qty:Number($('#eqAvail').value),utilization_pct:Number($('#eqUtil').value)})});setStatus('Equipment added');await renderPage('providerResources');};
}

async function renderProviderPlacements(w){
  const [rows,courses0]=await Promise.all([arr(await api('/api/provider/placements')),arr(await api('/api/provider/courses'))]);
  const placed=rows.reduce((a,x)=>a+Number(x.students_placed||0),0), openings=rows.reduce((a,x)=>a+Number(x.openings||0),0), rate=openings?Math.round(placed/openings*100):0;
  w.innerHTML=providerHeader('Placements','Record verified placement outcomes by course and employer, then use those outcomes as a direct proof point for course effectiveness.')+
    providerWriteGuard()+card(`<div class="grid">${card(metric('Students placed',placed),'sm')}${card(metric('Employer openings',openings),'sm')}${card(metric('Placement fill',rate+'%'),'sm')}${card(metric('Verified records',rows.length),'sm')}</div>`)+
    card(`<h2>Placement Outcomes</h2><table class="table"><tr><th>Course</th><th>Employer</th><th>Placed</th><th>Openings</th><th>Date</th><th>Status</th></tr>${rows.map(x=>`<tr><td>${esc(x.course_name)}</td><td>${esc(x.employer_name)}</td><td>${x.students_placed}</td><td>${x.openings}</td><td>${esc(x.placement_date)}</td><td><span class="pill">${esc(x.status)}</span></td></tr>`).join('')||'<tr><td colspan=6 class="muted">No verified placement outcomes recorded yet.</td></tr>'}</table>`)+
    card(`<h2>Record placement</h2><form id="placementForm"><div class="grid"><select id="plCourse" class="select" style="grid-column:span 4" required>${courses0.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select><input id="plEmployer" placeholder="Employer" style="grid-column:span 3" required><input id="plPlaced" type="number" min="0" value="5" placeholder="Students placed" style="grid-column:span 2"><input id="plOpenings" type="number" min="0" value="8" placeholder="Openings" style="grid-column:span 2"><input id="plDate" type="date" value="2026-09-10" required style="grid-column:span 2"><input id="plNotes" placeholder="Notes" style="grid-column:span 4"></div><button class="btn" style="margin-top:14px">Save placement outcome</button><div id="plMsg"></div></form>`);
  $('#placementForm').onsubmit=async e=>{e.preventDefault();if(!isAssignedMarket())return $('#plMsg').innerHTML='<div class="notice danger">Switch back to your registered district to save.</div>';await api('/api/provider/placements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:$('#plCourse').value,employer_name:$('#plEmployer').value.trim(),students_placed:Number($('#plPlaced').value),openings:Number($('#plOpenings').value),placement_date:$('#plDate').value,status:'Verified',notes:$('#plNotes').value.trim()})});setStatus('Placement outcome saved');await renderPage('providerPlacements');};
}


function adminHeader(title,desc){ return card(`<div class="eyebrow">DISTRICT ADMINISTRATION</div><h1 style="margin:8px 0 6px">${esc(title)}</h1><div class="muted">${esc(desc)}</div><div class="row" style="margin-top:12px"><span class="pill">${esc(currentUser?.district_name||'Assigned district')}</span><span class="pill">Decision workspace</span></div>`); }
function healthBadge(score){ const n=Number(score||0); return `<span class="pill">${n}/100 · ${n>=70?'Healthy':n>=45?'Needs upgrade':'Review / phase down'}</span>`; }

async function renderDistrictDashboard(w){
  const d=obj(await api('/api/district/admin-dashboard')), m=obj(d.metrics);
  const alerts=[];
  (d.top_skills||[]).filter(x=>Number(x.gap||0)>0).slice(0,3).forEach(x=>alerts.push(`Skill gap: ${x.name} · ${x.gap} seats short`));
  (d.course_health||[]).filter(x=>Number(x.health_score||0)<45).slice(0,2).forEach(x=>alerts.push(`Course risk: ${x.course} · ${x.action}`));
  w.innerHTML=adminHeader('District Command Centre','Monitor local labour demand, training supply, employer commitments and outcomes from one district-level control surface.')+
  card(`<h2>District snapshot</h2><div class="grid">${card(metric('Employers',m.companies),'sm')}${card(metric('Open job openings',m.openings),'sm')}${card(metric('Training providers',m.providers),'sm')}${card(metric('Training capacity',m.training_capacity),'sm')}${card(metric('Active trainers',m.active_trainers),'sm')}${card(metric('Equipment gap',m.equipment_gap_units+' units'),'sm')}${card(metric('Committed slots',m.committed_slots),'sm')}${card(metric('Placed students',m.placed_students),'sm')}</div>`)+
  card(`<div class="row" style="justify-content:space-between"><h2>Priority alerts</h2><span class="pill">${alerts.length} signals</span></div>${alerts.map(a=>`<div class="notice danger" style="margin:8px 0">${esc(a)}</div>`).join('')||'<div class="notice success">No critical gaps detected in seeded data.</div>'}`)+
  card(`<h2>Top skills by local demand gap</h2><table class="table"><tr><th>Skill</th><th>Openings</th><th>Training seats</th><th>Gap</th><th>Trend</th><th>Demand score</th></tr>${arr(d.top_skills).map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${x.openings}</td><td>${x.training_seats}</td><td>${x.gap}</td><td>${x.growth_pct>0?'↑ ':'↓ '}${Math.abs(x.growth_pct)}%</td><td>${x.demand_score}/100</td></tr>`).join('')||'<tr><td colspan=6 class="muted">No local demand records.</td></tr>'}</table>`)+
  card(`<h2>Recommended interventions</h2>${arr(d.recommendations).map(x=>`<div class="notice" style="margin:8px 0"><b>${esc(x.skill)}</b><br>${esc(x.action)}<br><span class="muted">${esc(x.reason)}</span></div>`).join('')||'<div class="notice">No intervention recommendations generated.</div>'}`);
}

async function renderDistrictJobs(w){
  const rows=arr(await api('/api/market/jobs?limit=100'));
  w.innerHTML=adminHeader('District Job Board','Demand intelligence from active employer postings. Filter openings and inspect the skills attached to each role.')+
  card(`<div class="row"><input id="djSearch" placeholder="Search job, employer or title" style="flex:1;min-width:260px"><select id="djSort" class="select"><option value="openings">Most openings</option><option value="salary">Highest salary</option><option value="recent">Recent</option></select></div><div id="djTable" style="margin-top:14px"></div>`);
  const draw=()=>{ const q=$('#djSearch').value.toLowerCase(); const mode=$('#djSort').value; let r=rows.filter(x=>`${x.title} ${x.company_name} ${x.role_name}`.toLowerCase().includes(q)); r.sort((a,b)=>mode==='salary'?Number(b.salary_max||0)-Number(a.salary_max||0):mode==='recent'?String(b.id).localeCompare(String(a.id)):Number(b.openings||0)-Number(a.openings||0)); $('#djTable').innerHTML=`<table class="table"><tr><th>Job</th><th>Employer</th><th>Role</th><th>Openings</th><th>Salary</th><th>Action</th></tr>${r.map((x,i)=>`<tr><td><b>${esc(x.title)}</b></td><td>${esc(x.company_name)}</td><td>${esc(x.role_name)}</td><td>${x.openings}</td><td>${x.salary_min?'₹'+Number(x.salary_min).toLocaleString('en-IN')+'–₹'+Number(x.salary_max||x.salary_min).toLocaleString('en-IN'):'On request'}</td><td><button class="btn secondary" onclick="showDistrictJobDetail(${i})">View</button></td></tr>`).join('')||'<tr><td colspan=6 class="muted">No jobs match this filter.</td></tr>'}</table><div id="djDetail" style="margin-top:12px"></div>`; window.__districtJobs=r;};
  $('#djSearch').oninput=draw; $('#djSort').onchange=draw; draw();
}
function showDistrictJobDetail(i){ const x=(window.__districtJobs||[])[i]; if(!x)return; $('#djDetail').innerHTML=card(`<div class="row" style="justify-content:space-between"><div><h3>${esc(x.title)}</h3><div class="muted">${esc(x.company_name)} · ${esc(x.role_name)}</div></div><span class="pill">${x.openings} openings</span></div><div class="grid" style="margin-top:12px">${card(metric('Salary max',x.salary_max?'₹'+Number(x.salary_max).toLocaleString('en-IN'):'—'),'sm')}${card(metric('Salary min',x.salary_min?'₹'+Number(x.salary_min).toLocaleString('en-IN'):'—'),'sm')}${card(metric('Location',x.location_text||'District'),'sm')}</div>`,'md'); }

async function renderDistrictRecruiters(w){
 const rows=arr(await api('/api/district/recruiters')); w.innerHTML=adminHeader('Active Recruiters','Employer relationships and current hiring intensity across the district.')+card(`<table class="table"><tr><th>Recruiter</th><th>Sector</th><th>Size</th><th>Open postings</th><th>Openings</th><th>Status</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.sector)}</td><td>${esc(x.size)}</td><td>${x.open_postings}</td><td>${x.openings}</td><td><span class="pill">${x.openings?'Actively hiring':'No open jobs'}</span></td></tr>`).join('')||'<tr><td colspan=6 class="muted">No active recruiters.</td></tr>'}</table>`)+card(`<h2>Recruiter action</h2><div class="notice">Use employer feedback and hiring outcomes to decide which recruiters should be engaged for new commitments, curriculum validation and placement drives.</div>`);
}

async function renderDistrictCourseHealth(w){
 const [health,lib]=await Promise.all([arr(await api('/api/market/course-alerts')),arr(await api('/api/district/course-library'))]);
 const byId=new Map(lib.map(x=>[x.id,x])); w.innerHTML=adminHeader('Course Health Score','Evaluate whether local training supply is aligned to employer demand, then identify courses that need scale, upgrade or phase-down.')+
 card(`<div class="grid">${card(metric('Healthy',health.filter(x=>Number(x.health_score)>=70).length),'sm')}${card(metric('Needs upgrade',health.filter(x=>Number(x.health_score)>=45&&Number(x.health_score)<70).length),'sm')}${card(metric('At risk',health.filter(x=>Number(x.health_score)<45).length),'sm')}${card(metric('Courses assessed',health.length),'sm')}</div>`)+
 card(`<table class="table"><tr><th>Course</th><th>Seats</th><th>Health</th><th>Missing demand skills</th><th>Action</th><th></th></tr>${health.map(x=>`<tr><td><b>${esc(x.course)}</b></td><td>${x.seats}</td><td>${healthBadge(x.health_score)}</td><td>${arr(x.missing_skills).map(s=>`<span class="pill">${esc(s)}</span>`).join('')||'—'}</td><td>${esc(x.action)}</td><td><button class="btn secondary" onclick="showDistrictCourse('${esc(x.course_id)}')">Evidence</button></td></tr>`).join('')||'<tr><td colspan=6 class="muted">No courses are currently assessed.</td></tr>'}</table><div id="dchDetail" style="margin-top:12px"></div>`);
  window.__districtCourseMap=byId;
}
function showDistrictCourse(id){ const x=(window.__districtCourseMap||{})[id]||{}; $('#dchDetail').innerHTML=card(`<h3>${esc(x.name||'Course')}</h3><div class="row"><span class="pill">${esc(x.provider_name||'')}</span><span class="pill">${x.seats||0} seats</span><span class="pill">${x.placed_students||0} placed students</span></div><p class="muted">Skills taught</p><div>${arr(x.skills).map(s=>`<span class="pill">${esc(s.name)} · L${s.taught_level}</span>`).join('')||'No mapped skills'}</div>`,'md'); }

async function renderDistrictLibrary(w){
 const rows=arr(await api('/api/district/course-library')); w.innerHTML=adminHeader('Curated Course Library','The district catalogue of active and inactive courses, their providers, capacity, skills and placement evidence.')+
 card(`<div class="row"><input id="dlSearch" placeholder="Search course, provider or skill" style="flex:1;min-width:260px"><select id="dlStatus" class="select"><option value="all">All statuses</option><option value="Active">Active</option><option value="Inactive">Inactive</option></select></div><div id="dlTable" style="margin-top:14px"></div>`);
 const draw=()=>{const q=$('#dlSearch').value.toLowerCase(),st=$('#dlStatus').value;r=rows.filter(x=>(st==='all'||x.status===st)&&`${x.name} ${x.provider_name} ${x.skills.map(s=>s.name).join(' ')}`.toLowerCase().includes(q));$('#dlTable').innerHTML=`<table class="table"><tr><th>Course</th><th>Provider</th><th>Duration</th><th>Seats</th><th>Skills</th><th>Placements</th><th>Status</th></tr>${r.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.provider_name)}</td><td>${x.duration_weeks} weeks</td><td>${x.seats}</td><td>${x.skills.map(s=>`<span class="pill">${esc(s.name)}</span>`).join('')}</td><td>${x.placed_students}</td><td><span class="pill">${esc(x.status)}</span></td></tr>`).join('')||'<tr><td colspan=7 class="muted">No courses match the filter.</td></tr>'}</table>`};$('#dlSearch').oninput=draw;$('#dlStatus').onchange=draw;let r=[];draw();
}

async function renderDistrictGuarantees(w){
 const rows=arr(await api('/api/district/guarantees')); const committed=rows.reduce((a,x)=>a+Number(x.committed_slots||0),0), hired=rows.reduce((a,x)=>a+Number(x.hired_slots||0),0); w.innerHTML=adminHeader('Employment Guarantee Board','Track employer hiring commitments, fulfilment and exceptions so promised pathways turn into real placements.')+
 card(`<div class="grid">${card(metric('Active commitments',rows.filter(x=>x.status==='active').length),'sm')}${card(metric('Committed slots',committed),'sm')}${card(metric('Hired slots',hired),'sm')}${card(metric('Fulfilment',committed?Math.round(hired/committed*100)+'%':'0%'),'sm')}</div>`)+
 card(`<table class="table"><tr><th>Employer</th><th>Role</th><th>Committed</th><th>Hired</th><th>Fulfilment</th><th>Valid until</th><th>Status</th><th></th></tr>${rows.map(x=>`<tr><td>${esc(x.company_name)}</td><td>${esc(x.role_name)}</td><td>${x.committed_slots}</td><td><input id="hire_${esc(x.id)}" type="number" min="0" max="${x.committed_slots}" value="${x.hired_slots}" style="min-width:90px;width:90px"></td><td>${x.fulfilment_pct}%</td><td>${esc(x.valid_until||'—')}</td><td><span class="pill">${esc(x.status)}</span></td><td><button class="btn secondary" onclick="reviewGuarantee('${esc(x.id)}',${x.committed_slots})">Save</button></td></tr>`).join('')||'<tr><td colspan=8 class="muted">No employer commitments.</td></tr>'}</table><div id="dgMsg" style="margin-top:12px"></div>`);
}
async function reviewGuarantee(id,max){ const n=Number($(`#hire_${id}`).value); if(!Number.isInteger(n)||n<0||n>max){$('#dgMsg').innerHTML='<div class="notice danger">Hired slots must be between 0 and the committed slots.</div>';return;} await api('/api/district/guarantees/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({hired_slots:n})});setStatus('Employment commitment updated');await renderPage('districtGuarantees');}

async function renderDistrictPlan(w){
 const d=obj(await api('/api/district/plan?target_year=2027')); w.innerHTML=adminHeader('District Training Plan','Convert demand, course health and capacity evidence into accountable interventions for the district skill committee.')+
 card(`<div class="row" style="justify-content:space-between"><div><h2>${esc(d.district)} · ${d.target_year}</h2><div class="muted">Status: ${esc(d.status)}</div></div><button class="btn" ${isAssignedMarket()?'':'disabled'} onclick="saveDistrictAdminPlan()">Save Plan</button></div><div class="grid" style="margin-top:14px">${card(metric('Training capacity',d.current_training_capacity),'sm')}${card(metric('Current openings',d.current_openings),'sm')}${card(metric('Capacity gap',d.capacity_gap),'sm')}${card(metric('Engine',d.engine_version),'sm')}</div>`)+
 card(`<h2>Recommended district actions</h2><table class="table"><tr><th>Role</th><th>Demand</th><th>Course health</th><th>Recommended action</th></tr>${arr(d.actions).map(x=>`<tr><td>${esc(x.role)}</td><td>${x.demand_openings}</td><td>${x.alignment}/100</td><td>${esc(x.recommended_action)}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">No plan actions.</td></tr>'}</table>`)+
 card(`<h2>System recommendations</h2>${arr(d.recommendations).map(x=>`<div class="notice" style="margin:8px 0"><b>${esc(x.skill)}</b><br>${esc(x.action)}<br><span class="muted">${esc(x.reason)}</span></div>`).join('')||'<div class="notice">No additional recommendations.</div>'}<div id="dapMsg"></div>`);
}
async function saveDistrictAdminPlan(){ const d=obj(await api('/api/district/plan?target_year=2027')); await api('/api/district/plan/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});setStatus('District training plan saved');await renderDistrictPlan($('#page'));$('#dapMsg')?.insertAdjacentHTML('beforeend','<div class="notice success">Plan persisted to the database.</div>'); }

async function renderDistrictFeedback(w){
 const rows=arr(await api('/api/district/feedback')); w.innerHTML=adminHeader('Employer Feedback','Review employer evidence, classify the feedback and record what the district has decided to do with it.')+
 card(`<div class="grid">${card(metric('Feedback records',rows.length),'sm')}${card(metric('New',rows.filter(x=>x.review_status==='new').length),'sm')}${card(metric('Actioned',rows.filter(x=>x.review_status==='actioned').length),'sm')}${card(metric('Avg rating',rows.length?(rows.reduce((a,x)=>a+Number(x.rating||0),0)/rows.length).toFixed(1)+'/5':'—'),'sm')}</div>`)+
 card(`<table class="table"><tr><th>Employer</th><th>Role</th><th>Rating</th><th>Feedback</th><th>Status</th><th>Admin note</th><th></th></tr>${rows.map(x=>`<tr><td>${esc(x.company_name)}</td><td>${esc(x.role_name||'—')}</td><td>${x.rating}/5</td><td>${esc(x.comment||'')}</td><td><span class="pill">${esc(x.review_status)}</span></td><td><input id="note_${x.id}" value="${esc(x.admin_note||'')}" placeholder="Decision note" style="min-width:180px"></td><td><select id="status_${x.id}" class="select" style="min-width:130px"><option ${x.review_status==='new'?'selected':''}>new</option><option ${x.review_status==='reviewed'?'selected':''}>reviewed</option><option ${x.review_status==='actioned'?'selected':''}>actioned</option><option ${x.review_status==='dismissed'?'selected':''}>dismissed</option></select><button class="btn secondary" style="margin-left:6px" onclick="reviewDistrictFeedback(${x.id})">Save</button></td></tr>`).join('')||'<tr><td colspan=7 class="muted">No employer feedback has been submitted for this district.</td></tr>'}</table><div id="dfMsg" style="margin-top:12px"></div>`);
}
async function reviewDistrictFeedback(id){await api('/api/district/feedback/'+encodeURIComponent(id)+'/review',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:$(`#status_${id}`).value,admin_note:$(`#note_${id}`).value.trim()})});setStatus('Employer feedback reviewed');await renderDistrictFeedback($('#page'));}

async function renderDistrictPlacements(w){
 const d=obj(await api('/api/district/placements')), s=obj(d.summary); w.innerHTML=adminHeader('Placement Outcomes','Measure whether district training converted into verified employer outcomes, by provider, course and hiring opportunity.')+
 card(`<div class="grid">${card(metric('Students placed',s.placed),'sm')}${card(metric('Employer openings',s.openings),'sm')}${card(metric('Placement records',s.records),'sm')}${card(metric('Fill rate',s.openings?Math.round(Number(s.placed)/Number(s.openings)*100)+'%':'0%'),'sm')}</div>`)+
 card(`<table class="table"><tr><th>Course</th><th>Provider</th><th>Employer</th><th>Placed</th><th>Openings</th><th>Fill rate</th><th>Date</th><th>Status</th></tr>${arr(d.items).map(x=>`<tr><td>${esc(x.course_name)}</td><td>${esc(x.provider_name)}</td><td>${esc(x.employer_name)}</td><td>${x.students_placed}</td><td>${x.openings}</td><td>${x.openings?Math.round(x.students_placed/x.openings*100):0}%</td><td>${esc(x.placement_date)}</td><td><span class="pill">${esc(x.status)}</span></td></tr>`).join('')||'<tr><td colspan=8 class="muted">No placement records.</td></tr>'}</table>`)+
 card(`<h2>What the district should learn from outcomes</h2><div class="notice">High-demand + high placement → scale capacity. High-demand + low placement → inspect curriculum/trainer readiness. Low-demand + high capacity → phase down or redirect intake. Placement evidence should feed the next training plan.</div>`);
}

async function renderAcademy(w){ const d=obj(await api('/api/market/academy')); w.innerHTML=explain('Curated Course Library','Shows the training supply actually stored for this district: provider, duration, seats and skills taught. Students can use this supply when building a learning path.')+card(`<h2>Curated Course Library</h2><div class="grid">${arr(d.courses).map(x=>`<div class="md notice"><b>${esc(x.name)}</b><br><span class="muted">${esc(x.provider_name)}</span><div class="row" style="margin-top:7px"><span class="pill">${x.seats} seats</span><span class="pill">${x.duration_weeks} weeks</span></div><div class="muted" style="margin-top:7px">Skills: ${esc(x.skills||'—')}</div></div>`).join('')||'<div class="notice">No courses stored for this district yet.</div>'}</div>`); }

async function renderCourseAlerts(w){ const d=arr(await api('/api/market/course-alerts')); w.innerHTML=explain('Course Alerts','The health check compares the skills taught by local courses against the skills present in current local job requirements, then flags missing coverage.')+card(`<h2>Course Alerts</h2><table class="table"><tr><th>Course</th><th>Alignment</th><th>Action</th><th>Missing skill IDs</th></tr>${d.map(x=>`<tr><td>${esc(x.name)}</td><td>${x.alignment}%</td><td>${esc(x.action)}</td><td>${arr(x.missing_skill_ids).length}</td></tr>`).join('')}</table>`); }

async function renderCurriculum(w){ const d=obj(await api('/api/market/academy')); w.innerHTML=explain('AI Curriculum Generator','Select a district course. The backend compares the course skill coverage with active local employer demand and returns recommended additions plus practical-hour changes. The proposal is data-derived and remains editable.')+card(`<h2>AI Curriculum Generator</h2><div class="grid">${arr(d.courses).map(x=>`<div class="md notice"><div class="row" style="justify-content:space-between"><b>${esc(x.name)}</b><button class="btn secondary" ${isAssignedMarket()?'':'disabled'} onclick="generateCurriculum('${esc(x.id)}')">Generate recommendation</button></div><div class="muted">${esc(x.provider_name)} · ${x.seats} seats</div></div>`).join('')}</div><div id="curriculumResult"></div>`); }
async function generateCurriculum(id){ const d=await api('/api/curriculum/'+encodeURIComponent(id)); $('#curriculumResult').innerHTML=card(`<h3>${esc(d.course.name)} · Recommended changes</h3><div class="grid"><div class="md notice"><b>Current modules / skills</b><br>${arr(d.current_modules).map(x=>`<span class="pill">${esc(x.name)}</span>`).join('')||'—'}</div><div class="md notice"><b>Add</b><br>${arr(d.recommended_additions).map(x=>`<span class="pill">${esc(x.name)}</span>`).join('')||'No missing demand skills'}</div></div><div class="notice" style="margin-top:12px">Practical training change: <b>+${d.recommended_practical_hours_increase} hours</b></div>`,'md'); }

async function renderSimulator(w){ const c=await api('/api/market/academy'); w.innerHTML=explain('Placement Impact Simulator','This is a scenario tool. It recalculates a readiness uplift from the skills a selected course teaches; it does not promise a job or a guaranteed placement outcome.')+card(`<h2>Placement Impact Simulator</h2><select id="simCourse" class="select">${arr(c.courses).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select><button class="btn" style="margin-left:8px" ${isAssignedMarket()?'':'disabled'} onclick="runSim()">Run simulation</button><div id="simResult" style="margin-top:15px"></div>`); }
async function runSim(){ const d=await api('/api/simulator',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:$('#simCourse').value})}); $('#simResult').innerHTML=`<div class="grid">${card(metric('Current readiness',d.before_score+'%'),'sm')}${card(metric('Projected',d.projected_score+'%'),'sm')}${card(metric('Change','+'+d.improvement+'%'),'sm')}</div><div class="notice">${esc(d.disclaimer)}</div>`; }

async function renderAlignment(w){ const d=arr(await api('/api/market/alignment')); w.innerHTML=explain('Course Health Score','Measures how well the current district course supply covers skills appearing in local employer demand. The score is generated from stored job requirements and course skill coverage.')+card(`<h2>Course Health Score</h2><table class="table"><tr><th>Role</th><th>Openings</th><th>Health</th><th>Action</th></tr>${d.map(x=>`<tr><td>${esc(x.role)}</td><td>${x.openings}</td><td><span class="pill">${x.alignment_score}/100</span></td><td>${esc(x.action)}</td></tr>`).join('')}</table>`); }

async function renderPlan(w){ const d=obj(await api('/api/district/plan?target_year=2027')); w.innerHTML=explain('District Plan','The plan combines local employer demand and current training capacity, then turns the evidence into actions the district skill committee can review.')+card(`<div class="row" style="justify-content:space-between"><div><h2>District Training Plan · ${esc(d.district)}</h2><p class="muted">Target year ${d.target_year}</p></div><button class="btn" ${isAssignedMarket()?'':'disabled'} onclick="savePlan()">Save plan</button></div><div class="grid">${card(metric('Training capacity',d.current_training_capacity),'sm')}${card(metric('Current openings',d.current_openings),'sm')}${card(metric('Capacity gap',d.capacity_gap),'sm')}${card(metric('Planning status',d.status),'sm')}</div><table class="table"><tr><th>Role</th><th>Demand</th><th>Course health</th><th>Recommended action</th></tr>${arr(d.actions).map(x=>`<tr><td>${esc(x.role)}</td><td>${x.demand_openings}</td><td>${x.alignment}/100</td><td>${esc(x.recommended_action)}</td></tr>`).join('')}</table><div id="planMsg"></div>`); }
async function savePlan(){ const d=obj(await api('/api/district/plan?target_year=2027')); await api('/api/district/plan/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); setStatus('District plan saved'); await renderPage('plan'); document.querySelector('#planMsg')?.insertAdjacentHTML('beforeend','<div class="notice success" style="margin-top:12px">Plan persisted to the database.</div>'); }

function refreshAll(){ renderPage(page); }
function renderOffline(msg){ $('#activeTenant').textContent='Backend unavailable'; $('#page').innerHTML=card(`<h2>Backend connection problem</h2><div class="notice danger"><b>${esc(msg)}</b><br><br>Start <b>run_backend.bat</b> from this project folder, then refresh the page.</div>`); }

bindNav();
window.refreshAll=refreshAll; window.renderPage=renderPage; window.completePathStep=completePathStep; window.requestMentor=requestMentor; window.createReskill=createReskill; window.updateHired=updateHired; window.inviteCandidate=inviteCandidate; window.generateCurriculum=generateCurriculum; window.runSim=runSim; window.submitDemoDirect=submitDemoDirect;
boot();
