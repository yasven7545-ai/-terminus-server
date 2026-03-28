
/* sln_terminus_full.js
   Full dashboard JS (extracted from inline HTML).
   Place this file at: static/js/sln_terminus.js
   Then include: <script src="/static/js/sln_terminus.js"></script> just before </body>
   KEEP: no logic, design, or process changes — this simply consolidates existing inline JS.
*/

(function(){
  // -------- utilities --------
  function showSection(id){
     document.querySelectorAll('section').forEach(s=>s.classList.remove('active'));
     const section = document.getElementById(id);
     if(!section) return;
     section.classList.add('active');
     section.scrollIntoView({ behavior: 'smooth', block: 'center' });
     section.style.boxShadow = '0 0 20px 4px rgba(59,130,246,0.5)';
     setTimeout(()=>section.style.boxShadow='none', 1500);
  }

  function showUploadMessage(msg, type='success'){
    const box=document.getElementById('uploadMsg');
    if(!box) return;
    box.innerText=msg;
    box.style.background = type==='success' ? 'linear-gradient(90deg,#16a34a,#22c55e)' : 'linear-gradient(90deg,#ef4444,#dc2626)';
    box.style.color='#fff'; box.style.padding='10px 14px'; box.style.borderRadius='8px';
    box.style.opacity='1';
    setTimeout(()=>box.style.opacity='0',3000);
  }

  // -------- charts init (global) --------
  function initCharts(){
    // guard: ensure canvases exist
    const spaceCanvas = document.getElementById('spaceChart');
    if (spaceCanvas && spaceCanvas.getContext) {
      const sctx = spaceCanvas.getContext('2d');
      window.spaceChart = new Chart(sctx,{ type:'bar', data:{ labels:['Total','Occupied','Vacant','Fit Out'], datasets:[{ label:'Area (SQFT)', data:[593209,555886,29124,8199], backgroundColor:'#f97316'}]}, options:{ indexAxis:'y', plugins:{legend:{display:false}} } });
    }

    const electricCanvas = document.getElementById('electricChart');
    if (electricCanvas && electricCanvas.getContext) {
      const ectx = electricCanvas.getContext('2d');
      window.electricChart = new Chart(ectx,{ type:'line', data:{ labels:['Built-up','Occupied','Leasable','Common'], datasets:[{label:'KWH/SFT', data:[0.88,0.86,0.82,0.75], borderColor:'#3b82f6', fill:true}]}, options:{} });
    }

    const benchmarkCanvas = document.getElementById('benchmarkChart');
    if (benchmarkCanvas && benchmarkCanvas.getContext) {
      const bctx = benchmarkCanvas.getContext('2d');
      window.benchmarkChart = new Chart(bctx,{ type:'line', data:{ labels:[], datasets:[{label:'HT Bill Units', data:[], borderColor:'#38bdf8', fill:true},{label:'Benchmark',data:[], borderColor:'#22c55e', borderDash:[5,5], fill:false}]}, options:{} });
    }

    const deployCanvas = document.getElementById('deployChart');
    if (deployCanvas && deployCanvas.getContext) {
      const dctx = deployCanvas.getContext('2d');
      window.deployChart = new Chart(dctx,{ type:'bar', data:{ labels:[], datasets:[{label:'Budgeted', data:[], backgroundColor:'#60a5fa'},{label:'Actual', data:[], backgroundColor:'#34d399'}]}, options:{responsive:true}});
    }

    const complaintsCanvas = document.getElementById('complaintsChart');
    if (complaintsCanvas && complaintsCanvas.getContext) {
      const cctx = complaintsCanvas.getContext('2d');
      window.complaintsChart = new Chart(cctx,{ type:'line', data:{ labels:[], datasets:[{label:'Complaints', data:[], borderColor:'#fb7185', fill:false}]}, options:{}});
    }

    const efacCanvas = document.getElementById('efacChart');
    if (efacCanvas && efacCanvas.getContext) {
      const fctx = efacCanvas.getContext('2d');
      window.efacChart = new Chart(fctx,{ type:'doughnut', data:{ labels:['Active','Pending/Other'], datasets:[{data:[0,0], backgroundColor:['#34d399','#f97316']}]}, options:{}});
    }

    const trainingCanvas = document.getElementById('trainingChart');
    if (trainingCanvas && trainingCanvas.getContext) {
      const tctx = trainingCanvas.getContext('2d');
      window.trainingChart = new Chart(tctx,{ type:'bar', data:{ labels:[], datasets:[{label:'Trainings', data:[], backgroundColor:'#f59e0b'}]}, options:{}});
    }

    // DG charts
    const dgComboCanvas = document.getElementById('dgComboChart');
    if (dgComboCanvas && dgComboCanvas.getContext) {
      const dgComboCtx = dgComboCanvas.getContext('2d');
      window.dgComboChart = new Chart(dgComboCtx, {
        type: 'bar',
        data: { labels: [], datasets: [
          { type: 'bar', label: 'KWH Units', data: [], backgroundColor: '#60a5fa', yAxisID: 'y' },
          { type: 'line', label: 'Diesel (Ltrs)', data: [], borderColor: '#f97316', backgroundColor: '#f97316', yAxisID: 'y1', tension: 0.2, fill:false }
        ] },
        options: {
          responsive:true,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { type: 'linear', position: 'left', title:{display:true,text:'KWH Units'} },
            y1: { type: 'linear', position: 'right', grid:{drawOnChartArea:false}, title:{display:true,text:'Diesel (Ltrs)'} }
          }
        }
      });
    }

    const dgKwhCanvas = document.getElementById('dgKwhChart');
    if (dgKwhCanvas && dgKwhCanvas.getContext) {
      const dgKwhCtx = dgKwhCanvas.getContext('2d');
      window.dgKwhChart = new Chart(dgKwhCtx,{ type:'bar', data:{ labels:[], datasets:[{label:'KWH Units', data:[], backgroundColor:'#60a5fa'}]}, options:{responsive:true}});
    }

    const dgDieselCanvas = document.getElementById('dgDieselChart');
    if (dgDieselCanvas && dgDieselCanvas.getContext) {
      const dgDieselCtx = dgDieselCanvas.getContext('2d');
      window.dgDieselChart = new Chart(dgDieselCtx,{ type:'line', data:{ labels:[], datasets:[{label:'Diesel (Ltrs)', data:[], borderColor:'#f97316', fill:false}]}, options:{responsive:true}});
    }

  }

  // ---- FIX EXCEL SERIAL DATE → TEXT ----
  function fixExcelDate(v) {
    if (typeof v === "number" && v > 40000 && v < 60000) {
      const jsDate = XLSX.SSF.parse_date_code(v);
      return `${jsDate.m}-${jsDate.y}`;
    }
    return String(v);
  }

  /* -------- read + map workbook -> DOM + charts -------- */
  function handleWorkbook(arrayBuffer){
    try{
      const wb = XLSX.read(arrayBuffer);

      const w = document.getElementById('welcomeIdle'); if(w) w.style.display='none';

      // Space_Occupancy
      if(wb.SheetNames.includes('Space_Occupancy')){
        const sheet = wb.Sheets['Space_Occupancy'];
        const rows = XLSX.utils.sheet_to_json(sheet, {header:1});
        if(rows.length>1){
          const table = document.getElementById('spaceTable'); if(table) table.innerHTML='';
          const vals=[];
          rows.slice(1).forEach(r=>{
            const tr=document.createElement('tr'); tr.innerHTML=`<th>${r[0]||''}</th><td>${r[1]||''}</td>`; if(table) table.appendChild(tr);
            vals.push(parseFloat(String(r[1]||'0').replace(/,/g,''))||0);
          });
          while(vals.length<4) vals.push(0);
          if (window.spaceChart && window.spaceChart.data) {
            window.spaceChart.data.datasets[0].data = vals.slice(0,4);
            window.spaceChart.update();
          }
        }
      }

      // Electricity_Consumption
      if(wb.SheetNames.includes('Electricity_Consumption')){
        const sheet = wb.Sheets['Electricity_Consumption'];
        const rows = XLSX.utils.sheet_to_json(sheet, {header:1});
        if(rows.length>1){
          const table = document.getElementById('electricTable'); if(table) table.innerHTML='';
          const map = {};
          rows.slice(1).forEach(r=>{
            const tr=document.createElement('tr'); tr.innerHTML=`<th>${r[0]||''}</th><td>${r[1]||''}</td>`; if(table) table.appendChild(tr);
            if(r[0]) map[r[0].toString().toLowerCase()] = r[1];
          });
          const built = parseFloat(String(map['built-up area consumption (kwh/sft)']||map['built-up area consumption']||map['built-up']||0).replace(/,/g,''))||0;
          const occ = parseFloat(String(map['occupied area (sft)']||map['occupied']||0).replace(/,/g,''))||0;
          const leas = parseFloat(String(map['leasable area energy consumption (units)']||map['leasable']||0).replace(/,/g,''))||0;
          const common = parseFloat(String(map['common area consumption (kwh/sft)']||map['common']||0).replace(/,/g,''))||0;
          const chartVals = [built||window.electricChart?.data?.datasets?.[0]?.data?.[0], occ||window.electricChart?.data?.datasets?.[0]?.data?.[1], leas||window.electricChart?.data?.datasets?.[0]?.data?.[2], common||window.electricChart?.data?.datasets?.[0]?.data?.[3]];
          if (window.electricChart && window.electricChart.data) {
            window.electricChart.data.datasets[0].data = chartVals;
            window.electricChart.update();
          }
        }
      }

      // Energy_Benchmark
      if(wb.SheetNames.includes('Energy_Benchmark')){
        const sheet = wb.Sheets['Energy_Benchmark'];
        const rows = XLSX.utils.sheet_to_json(sheet,{header:1});
        if(rows.length>1){
          const body = document.getElementById('benchmarkBody'); if(body) body.innerHTML='';
          const months=[]; const units=[];
          rows.slice(1).forEach(r=>{
            const tr=document.createElement('tr');
            tr.innerHTML = `<td>${r[0]||''}</td><td style="text-align:left">${r[1]||''}</td><td style="text-align:right">${r[2]||''}</td>`;
            if(body) body.appendChild(tr);
            months.push(r[1]||''); units.push(parseFloat(String(r[2]||'0').replace(/,/g,''))||0);
          });
          if(months.length && window.benchmarkChart) window.benchmarkChart.data.labels = months;
          if(units.length && window.benchmarkChart) window.benchmarkChart.data.datasets[0].data = units;
          if(window.benchmarkChart) window.benchmarkChart.update();
        }
      }

      // CAPEX_Works
      if(wb.SheetNames.includes('CAPEX_Works')){
        const sheet = wb.Sheets['CAPEX_Works']; const rows=XLSX.utils.sheet_to_json(sheet,{header:1});
        if(rows.length>1){
          const body=document.getElementById('capexBody'); if(body) body.innerHTML='';
          rows.slice(1).forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td style="text-align:center">${r[0]||''}</td><td style="text-align:left">${r[1]||''}</td><td style="text-align:left">${r[2]||''}</td>`; if(body) body.appendChild(tr); });
        }
      }

# trimmed for brevity - file is long
