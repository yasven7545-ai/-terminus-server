// ══════════════════════════════════════════════
// EPMS DOCUMENT MANAGEMENT MODULE
// Compatible with Flask backend routes in server.py
// ══════════════════════════════════════════════

// ── DATA SOURCES ───────────────────────────────
const AUDIT_SHEETS = {
  "PM_Technical_Audit_Checklist": [],
  "HSE Compliance Audit Checklist": [],
  "Utility_Energy_Performance_Au": [],
  "Soft Services Operational Audit": [],
  "Vendor Management Audit": [],
  "Security_Operational_Audit_Chec": [],
  "Fire_Life_Safety_Audit_Checklis": [],
  "Customer_Occupant_Satisfaction_": [],
  "Financial_Controls_Audit_Checkl": [],
  "Annual_Compliance_Documentation": [],
  "Lease_Space_Management_Audit_Ch": [],
  "Sustainability_ESG_Audit_Checkl": []
};

const OM_DATA = [
  {"no":"1","area":"Resource Management","criteria":[
    {"sub":"1.1","desc":"Actual man days deployment >95%","score":-1},
    {"sub":"1.2","desc":"Short deployment has been fullfilled in 2 hrs","score":-1},
    {"sub":"1.3","desc":"Trained and expereinced resources are deployed","score":-1},
    {"sub":"1.4","desc":"Proper uniforms and Accessaories has been provided","score":-1},
    {"sub":"1.5","desc":"Employees are groomed and well mannered","score":-1}
  ]},
  // ... (full 10 sections as per your data)
];

let momRows = [];
let sheetData = [];
let omData = JSON.parse(JSON.stringify(OM_DATA));
let currentSheetKey = '';

// ── CONFIG: EPMS MODULES ───────────────────────
const EPMS_MODULES = [
  {key:'PM_Technical_Audit_Checklist', icon:'⚙️', title:'Preventive Maintenance (PM) Systems', desc:'PM schedules, work orders, equipment logbooks, spare parts & records', color:'rgba(0,200,255,.1)'},
  {key:'HSE Compliance Audit Checklist', icon:'🦺', title:'Health, Safety & Environment (HSE)', desc:'Fire safety, emergency preparedness, PPE compliance, first aid & incidents', color:'rgba(255,107,53,.1)'},
  {key:'Utility_Energy_Performance_Au', icon:'⚡', title:'Utility & Energy Management', desc:'Energy consumption, water management, DG fuel & sustainability KPIs', color:'rgba(255,196,0,.1)'},
  {key:'Soft Services Operational Audit', icon:'🧹', title:'Soft Services (Housekeeping & Waste)', desc:'Cleaning standards, pest control, waste segregation & team grooming', color:'rgba(164,114,255,.1)'},
  {key:'Vendor Management Audit', icon:'🤝', title:'Vendor Management & SLAs', desc:'Contracts, SLA adherence, vendor performance, invoice management', color:'rgba(52,211,153,.1)'},
  {key:'Security_Operational_Audit_Chec', icon:'🔒', title:'Security Operations', desc:'Guard deployment, access control, CCTV, patrols and incidents', color:'rgba(56,189,248,.1)'},
  {key:'Fire_Life_Safety_Audit_Checklis', icon:'🔥', title:'Fire & Life Safety Systems', desc:'Fire alarms, suppression systems, extinguishers, drills & compliance', color:'rgba(251,113,133,.1)'},
  {key:'Customer_Occupant_Satisfaction_', icon:'😊', title:'Customer / Occupant Satisfaction', desc:'Helpdesk management, complaint resolution, SLA and feedback scores', color:'rgba(251,191,36,.1)'},
  {key:'Financial_Controls_Audit_Checkl', icon:'💰', title:'Financial Controls', desc:'Budget control, purchase orders, expense tracking, reporting', color:'rgba(34,211,153,.1)'},
  {key:'Annual_Compliance_Documentation', icon:'📜', title:'Annual Compliance & Documentation', desc:'Statutory compliance, licensing, record management & certifications', color:'rgba(99,102,241,.1)'},
  {key:'Lease_Space_Management_Audit_Ch', icon:'🏢', title:'Lease & Space Management', desc:'Lease documentation, occupancy tracking, rent collection & handover', color:'rgba(16,185,129,.1)'},
  {key:'Sustainability_ESG_Audit_Checkl', icon:'🌱', title:'Sustainability & ESG Initiatives', desc:'Carbon management, green certifications, water recycling & ESG KPIs', color:'rgba(5,150,105,.1)'}
];

// ── INITIALIZATION ─────────────────────────────
function initAll() {
  fetchMOM();
  initEPMSGrid();
  initOM();
  lucide.createIcons();
}

async function fetchMOM() {
  try {
    const res = await fetch('/api/documents/mom');
    if (res.ok) {
      const data = await res.json();
      momRows = (data.items || []).map((it, i) => ({
        sno: String(i + 1),
        site: it.site?.trim() || '',
        topic: it.topic?.trim() || '',
        desc: it.desc?.trim() || '',
        remarks: it.rem?.trim() || ''
      }));
      renderMOM();
    }
  } catch (e) {
    console.warn('Local MOM fallback');
    momRows = [];
    renderMOM();
  }
}

// ── PANEL NAVIGATION ───────────────────────────
function go(id, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.nav').forEach(b => b.classList.remove('on'));
  document.getElementById(`panel-${id}`)?.classList.add('on');
  btn?.classList.add('on');
  closeSidebar();
  if (id === 'epms') backToGrid();
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('open');
}

function closeSidebar() {
  if (window.innerWidth <= 768) {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('overlay').classList.remove('open');
  }
}

// ── MOM FUNCTIONS ──────────────────────────────
function renderMOM() {
  const tbody = document.getElementById('momBody');
  if (!tbody) return;
  tbody.innerHTML = momRows.map((r, i) => `
    <tr>
      <td style="text-align:center;color:var(--txt3);font-weight:600">${i+1}</td>
      <td contenteditable="true" onblur="updateMOMField(${i}, 'site', this.textContent)">${esc(r.site)}</td>
      <td contenteditable="true" onblur="updateMOMField(${i}, 'topic', this.textContent)">${esc(r.topic)}</td>
      <td contenteditable="true" onblur="updateMOMField(${i}, 'desc', this.textContent)" style="line-height:1.5">${esc(r.desc)}</td>
      <td contenteditable="true" onblur="updateMOMField(${i}, 'remarks', this.textContent)" style="line-height:1.5">${esc(r.remarks)}</td>
      <td><button class="del-btn" onclick="delMOMRow(${i})"><i data-lucide="trash-2"></i></button></td>
    </tr>
  `).join('');
  lucide.createIcons();
}

function updateMOMField(i, field, value) {
  momRows[i][field] = value.trim();
}

function addMOMRow() {
  momRows.push({sno: String(momRows.length + 1), site: '', topic: '', desc: '', remarks: ''});
  renderMOM();
  toast('✅ Row added');
}

function delMOMRow(i) {
  momRows.splice(i, 1);
  renderMOM();
  toast('🗑 Row deleted');
}

async function saveMOM() {
  const data = {
    refNo: document.getElementById('momRefNo')?.textContent.trim() || '',
    attendees: document.getElementById('momAttendees')?.textContent.trim() || '',
    items: momRows.map(r => ({ site: r.site, topic: r.topic, desc: r.desc, rem: r.remarks }))
  };
  try {
    const res = await fetch('/api/documents/mom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.ok) {
      toast('✅ MOM saved to server');
    } else throw new Error();
  } catch (e) {
    localStorage.setItem('emerzhent_mom', JSON.stringify(data));
    toast('💾 Saved locally');
  }
}

// ── EPMS MODULE GRID ───────────────────────────
function initEPMSGrid() {
  const grid = document.getElementById('moduleGrid');
  if (!grid) return;
  grid.innerHTML = EPMS_MODULES.map((m, idx) => `
    <div class="mcard" data-midx="${idx}">
      <div class="mcard-ico" style="background:${m.color}">${m.icon}</div>
      <div class="mcard-title">${m.title}</div>
      <div class="mcard-desc">${m.desc}</div>
      <div class="mcard-arr"><i data-lucide="chevron-right"></i></div>
    </div>
  `).join('');
  grid.querySelectorAll('.mcard').forEach(card => {
    card.addEventListener('click', () => {
      const idx = parseInt(card.dataset.midx);
      openSheet(EPMS_MODULES[idx].key, EPMS_MODULES[idx].title, EPMS_MODULES[idx].icon);
    });
  });
  lucide.createIcons();
}

// ── AUDIT SHEET ────────────────────────────────
function openSheet(key, title, icon) {
  currentSheetKey = key;
  document.getElementById('sheetTitle').textContent = icon + ' ' + title;
  document.getElementById('sheetBcName').textContent = title;
  document.getElementById('epmsGrid').style.display = 'none';
  document.getElementById('epmsSheet').style.display = 'block';

  const saved = localStorage.getItem(`emerzhent_audit_${key}`);
  if (saved) {
    sheetData = JSON.parse(saved);
  } else {
    sheetData = Array.from({ length: 32 }, (_, i) => ({
      sno: String(i + 1),
      section: '',
      subsystem: '',
      item: '',
      method: '',
      compliance: '',
      observation: '',
      risk: '',
      evidence: '',
      responsible: '',
      closure: '',
      status: 'Open'
    }));
  }
  renderAuditSheet();
}

function renderAuditSheet() {
  const tbody = document.getElementById('auditBody');
  if (!tbody) return;
  tbody.innerHTML = sheetData.map((r, i) => `
    <tr>
      <td style="text-align:center;color:var(--txt3);font-weight:600">${r.sno}</td>
      <td style="color:var(--txt2);font-size:.8rem">${esc(r.section)}</td>
      <td style="color:var(--txt3);font-size:.78rem">${esc(r.subsystem)}</td>
      <td contenteditable="true" onblur="sheetData[${i}].item=this.textContent" style="line-height:1.55">${esc(r.item)}</td>
      <td style="color:var(--txt3);font-size:.78rem">${esc(r.method)}</td>
      <td style="text-align:center">
        <span class="badge ${compBadge(r.compliance)}" onclick="cycleCompliance(${i},this)">${r.compliance||'—'}</span>
      </td>
      <td contenteditable="true" onblur="sheetData[${i}].observation=this.textContent;calcAuditScore()" style="font-size:.78rem;color:var(--txt3)">${esc(r.observation)}</td>
      <td><span class="risk-${riskClass(r.risk)}" onclick="cycleRisk(${i},this)">${r.risk||'—'}</span></td>
      <td contenteditable="true" onblur="sheetData[${i}].evidence=this.textContent" style="font-size:.78rem;color:var(--txt3)">${esc(r.evidence)}</td>
      <td contenteditable="true" onblur="sheetData[${i}].responsible=this.textContent" style="font-size:.78rem">${esc(r.responsible)}</td>
      <td contenteditable="true" onblur="sheetData[${i}].closure=this.textContent" style="font-size:.78rem">${esc(r.closure)}</td>
      <td>
        <select class="insel" onchange="sheetData[${i}].status=this.value">
          <option ${r.status==='Open'||!r.status?'selected':''}>Open</option>
          <option ${r.status==='Closed'?'selected':''}>Closed</option>
          <option ${r.status==='In Progress'?'selected':''}>In Progress</option>
        </select>
      </td>
    </tr>
  `).join('');
  calcAuditScore();
  lucide.createIcons();
}

function compBadge(v) {
  if (!v) return 'badge-na';
  v = v.toLowerCase();
  if (v === 'yes') return 'badge-yes';
  if (v === 'no') return 'badge-no';
  return 'badge-na';
}

function cycleCompliance(i, el) {
  const vals = ['Yes', 'No', 'NA', ''];
  const cur = sheetData[i].compliance;
  const ni = (vals.indexOf(cur) + 1) % vals.length;
  sheetData[i].compliance = vals[ni];
  el.textContent = vals[ni] || '—';
  el.className = 'badge ' + compBadge(vals[ni]);
  calcAuditScore();
}

function riskClass(r) {
  if (!r) return 'med';
  r = r.toLowerCase();
  if (r.includes('low')) return 'low';
  if (r.includes('high')) return 'high';
  return 'med';
}

const RISKS = ['Low', 'Medium', 'High', ''];
function cycleRisk(i, el) {
  const cur = sheetData[i].risk;
  const ni = (RISKS.indexOf(cur) + 1) % RISKS.length;
  sheetData[i].risk = RISKS[ni];
  el.textContent = RISKS[ni] || '—';
  el.className = 'risk-' + riskClass(RISKS[ni]);
}

function calcAuditScore() {
  let yes = 0, no = 0, na = 0;
  sheetData.forEach(r => {
    if (r.compliance === 'Yes') yes++;
    else if (r.compliance === 'No') no++;
    else if (r.compliance === 'NA') na++;
  });
  const applicable = yes + no;
  const pct = applicable > 0 ? Math.round((yes / applicable) * 100) : 0;
  document.getElementById('scTotal').textContent = yes;
  document.getElementById('scNC').textContent = no;
  document.getElementById('scNA').textContent = na;
  document.getElementById('scPct').textContent = pct + '%';
  document.getElementById('scPct').style.color = pct >= 80 ? '#00ff99' : pct >= 50 ? '#ffc400' : '#ff6b35';
}

async function saveSheet() {
  localStorage.setItem(`emerzhent_audit_${currentSheetKey}`, JSON.stringify(sheetData));
  try {
    await fetch('/api/documents/audit-save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sheet: currentSheetKey,
        month: document.getElementById('auditMonth')?.value || '2026-02',
        data: sheetData
      })
    });
  } catch (e) {}
  toast('✅ Sheet saved');
}

function exportSheetCSV() {
  const hdr = ['#','Section','Sub-System','Checklist Item','Method','Compliance','Observation','Risk','Evidence','Responsible','Closure','Status'];
  const rows = sheetData.map(r => [r.sno,r.section,r.subsystem,r.item,r.method,r.compliance,r.observation,r.risk,r.evidence,r.responsible,r.closure,r.status]);
  downloadCSV([hdr, ...rows], 'EPMS_Audit_' + currentSheetKey);
}

function backToGrid() {
  document.getElementById('epmsGrid').style.display = 'block';
  document.getElementById('epmsSheet').style.display = 'none';
}

// ── O&M SCORE CARD ─────────────────────────────
function initOM() {
  const saved = localStorage.getItem('emerzhent_om');
  if (saved) omData = JSON.parse(saved);
  renderOM();
}

function renderOM() {
  const cont = document.getElementById('omSections');
  if (!cont) return;
  cont.innerHTML = omData.map((sec, si) => `
    <div class="om-sec">
      <div class="om-sec-hdr">
        <h3>${sec.no}. ${sec.area}</h3>
        <div style="display:flex;align-items:center;gap:10px">
          <div style="font-size:.7rem;color:var(--txt3)">Section Score:</div>
          <div class="om-score-disp" id="omSec${si}">0/${sec.criteria.length * 2}</div>
        </div>
      </div>
      ${sec.criteria.map((c, ci) => `
        <div class="om-row">
          <div class="om-sub">${c.sub}</div>
          <div class="om-desc">${c.desc}</div>
          <div class="om-inp">
            ${[0,1,2].map(v => `<button class="star-btn ${c.score===v?'on':''}" onclick="setOMScore(${si},${ci},${v})">
              ${v===0?'⭕':v===1?'⭐':'⭐⭐'}</button>`).join('')}
            <button class="star-btn ${c.score===-1?'on':''}" onclick="setOMScore(${si},${ci},-1)" title="N/A" style="font-size:.75rem">NA</button>
          </div>
          <div style="font-size:.82rem;font-weight:600;color:${scoreColor(c.score)}" id="omCrit${si}_${ci}">
            ${c.score < 0 ? 'N/A' : c.score + '/2'}
          </div>
        </div>
      `).join('')}
    </div>
  `).join('');
  updateOMTotals();
}

function setOMScore(si, ci, val) {
  omData[si].criteria[ci].score = val;
  renderOM();
}

function scoreColor(v) {
  if (v < 0) return 'var(--txt3)';
  if (v === 2) return '#00ff99';
  if (v === 1) return '#ffc400';
  return '#ff6b35';
}

function updateOMTotals() {
  let total = 0, maxTotal = 0;
  omData.forEach((sec, si) => {
    let secTotal = 0, secMax = 0;
    sec.criteria.forEach(c => {
      if (c.score >= 0) { total += c.score; maxTotal += 2; secTotal += c.score; secMax += 2; }
    });
    const el = document.getElementById(`omSec${si}`);
    if (el) el.textContent = `${secTotal}/${secMax}`;
  });
  const pct = maxTotal > 0 ? Math.round((total / maxTotal) * 100) : 0;
  document.getElementById('omTotal').textContent = total;
  document.getElementById('omMax').textContent = maxTotal;
  document.getElementById('omPct').textContent = pct + '%';
  document.getElementById('omPct').style.color = pct >= 80 ? '#00ff99' : pct >= 50 ? '#ffc400' : '#ff6b35';
  const status = pct > 90 ? '✅ Good' : pct > 80 ? '🟡 Satisfactory' : pct > 70 ? '⚠️ Average' : '🔴 Needs Improvement';
  document.getElementById('omStatus').textContent = status;
}

async function saveOM() {
  localStorage.setItem('emerzhent_om', JSON.stringify(omData));
  try {
    await fetch('/api/documents/om-save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        month: document.getElementById('omMonth')?.value || '2026-02',
        vendor: document.getElementById('omVendor')?.value || 'Default',
        site: document.getElementById('omSite')?.value || 'SLN Terminus',
        data: omData
      })
    });
  } catch (e) {}
  toast('✅ Score card saved');
}

function resetOM() {
  omData = JSON.parse(JSON.stringify(OM_DATA));
  renderOM();
  toast('🔄 Score card reset');
}

function exportOMCSV() {
  const hdr = ['Section No','Area','Sub-No','Criteria','Score (0-2)','Max'];
  const rows = [];
  omData.forEach(sec => {
    sec.criteria.forEach(c => {
      rows.push([sec.no, sec.area, c.sub, c.desc, c.score < 0 ? 'NA' : c.score, 2]);
    });
  });
  downloadCSV([hdr, ...rows], 'OM_Performance_ScoreCard');
}

// ── UTILITIES ──────────────────────────────────
function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function downloadCSV(rows, filename) {
  const csv = rows.map(r => r.map(v => `"${String(v||'').replace(/"/g,'""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${filename}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  toast('📥 CSV exported');
}

function toast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('on');
  setTimeout(() => t.classList.remove('on'), 3000);
}

// ── START ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', initAll);