(function () {
  if (window.__PPM_APP__) return;
  window.__PPM_APP__ = true;

  /* ================= GLOBAL STATE ================= */
  window.state = {
    assets: [],
    schedules: [],
    currentDate: new Date()
  };

  /* ================= CHARTS (HARD SAFE) ================= */
  function destroyChart(id) {
    if (!window.Chart) return;
    const c = Chart.getChart(id);
    if (c) c.destroy();
  }

  function initCharts() {
    if (!window.Chart) return;

    destroyChart("statusChart");
    destroyChart("growthChart");

    const sc = document.getElementById("statusChart");
    const gc = document.getElementById("growthChart");

    if (sc) {
      new Chart(sc, {
        type: "doughnut",
        data: {
          labels: ["Pending", "Open", "Closed"],
          datasets: [{
            data: [
              state.schedules.filter(s => s.status === "Pending").length,
              state.schedules.filter(s => s.status === "Open").length,
              state.schedules.filter(s => s.status === "Closed").length
            ],
            backgroundColor: ["#eab308", "#3b82f6", "#22c55e"]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    if (gc) {
      new Chart(gc, {
        type: "line",
        data: {
          labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
          datasets: [{
            label: "Tasks",
            data: [5, 12, 8, 15, 10, 20],
            borderColor: "#3b82f6",
            fill: true,
            tension: 0.4
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }
  }

  /* ================= HELPERS ================= */
  function parseExcelDate(v) {
    if (!v) return null;
    if (typeof v === "number") {
      return new Date((v - 25569) * 86400 * 1000).toISOString().split("T")[0];
    }
    const d = new Date(v);
    return isNaN(d) ? null : d.toISOString().split("T")[0];
  }

  function addMonths(d, m) {
    const x = new Date(d);
    x.setMonth(x.getMonth() + m);
    return x.toISOString().split("T")[0];
  }

  function freqColor(f) {
    return {
      Monthly: "bg-green-500",
      Quarterly: "bg-yellow-500",
      "Half Yearly": "bg-blue-500",
      Yearly: "bg-red-500"
    }[f] || "bg-gray-400";
  }

  /* ================= DASHBOARD ================= */
  function updateDashboardStats() {
    const closed = state.schedules.filter(s => s.status === "Closed").length;

    const totalEl = document.getElementById("total-assets-count");
    const pendingEl = document.getElementById("pending-ppm-count");
    const completedEl = document.getElementById("completed-ppm-count");
    const complianceEl = document.getElementById("compliance-rate");

    if (totalEl) totalEl.innerText = state.assets.length;
    if (pendingEl) pendingEl.innerText = state.schedules.filter(s => s.status !== "Closed").length;
    if (completedEl) completedEl.innerText = closed;

    if (complianceEl) {
      complianceEl.innerText =
        state.schedules.length > 0
          ? Math.round((closed / state.schedules.length) * 100) + "%"
          : "0%";
    }
  }

  /* ================= ASSETS ================= */
  function renderAssetsTable() {
    const body = document.getElementById("assets-table-body");
    if (!body) return;

    body.innerHTML = state.assets.map(a => `
      <tr>
        <td class="p-3">${a.id}</td>
        <td class="p-3">${a.name}</td>
        <td class="p-3">${a.category}</td>
        <td class="p-3">${a.location}</td>
        <td class="p-3">${a.lastService || "-"}</td>
        <td class="p-3">${a.nextDueDate || "-"}</td>
        <td class="p-3">
          <span class="w-3 h-3 inline-block rounded-full ${freqColor(a.frequency)}"></span>
        </td>
      </tr>
    `).join("");
  }

  /* ================= CALENDAR ================= */
  function renderCalendar() {
    const grid = document.getElementById("calendar-body");
    const title = document.getElementById("current-month-display");
    if (!grid || !title) return;

    const y = state.currentDate.getFullYear();
    const m = state.currentDate.getMonth();

    title.innerText = state.currentDate.toLocaleString("default", {
      month: "long",
      year: "numeric"
    });

    grid.innerHTML = "";

    const first = new Date(y, m, 1).getDay();
    const days = new Date(y, m + 1, 0).getDate();

    for (let i = 0; i < first; i++) grid.appendChild(document.createElement("div"));

    for (let d = 1; d <= days; d++) {
      const date = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const items = state.schedules.filter(s => s.date === date);

      const cell = document.createElement("div");
      cell.className = "calendar-day p-2";
      cell.innerHTML = `
        <div class="text-xs">${d}</div>
        <div class="flex gap-1 flex-wrap mt-1">
          ${items.map(i => `<span class="w-2 h-2 rounded-full ${freqColor(i.frequency)}"></span>`).join("")}
        </div>
      `;
      grid.appendChild(cell);
    }
  }

  /* ================= EXCEL ================= */
  function handleWorkbook(buffer) {
    const wb = XLSX.read(buffer, { type: "array" });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: "" });

    state.assets = [];
    state.schedules = [];

    rows.forEach((r, i) => {
      const id = String(r["Asset ID"] || r["ID"] || `AST-${i + 1}`);
      const freq = r["Frequency"] || "Yearly";
      const next = parseExcelDate(r["NEXT DUE"]);
      const step = freq === "Monthly" ? 1 : freq === "Quarterly" ? 3 : freq === "Half Yearly" ? 6 : 12;

      state.assets.push({
        id,
        name: r["Asset Name"] || "Unnamed",
        category: r["Category"] || "General",
        location: r["Location"] || "HT Room",
        lastService: parseExcelDate(r["LAST SERVICE"]),
        nextDueDate: next,
        frequency: freq
      });

      if (next) {
        let d = next;
        for (let k = 0; k < 12; k++) {
          state.schedules.push({
            assetId: id,
            date: d,
            frequency: freq,
            status: "Pending"
          });
          d = addMonths(d, step);
        }
      }
    });

    localStorage.setItem("ppm_data", JSON.stringify(state));
    renderAssetsTable();
    renderCalendar();
    updateDashboardStats();
    initCharts();
  }

  function loadExcelFromInput() {
    const fi = document.getElementById("assets-file-input");
    if (!fi || !fi.files[0]) return;
    fi.files[0].arrayBuffer().then(handleWorkbook);
  }

  /* ================= INIT ================= */
  document.addEventListener("DOMContentLoaded", () => {
    const saved = JSON.parse(localStorage.getItem("ppm_data") || "{}");
    if (saved.assets) {
      state.assets = saved.assets;
      state.schedules = saved.schedules || [];
    }
    state.currentDate = new Date();

    renderAssetsTable();
    renderCalendar();
    updateDashboardStats();
    initCharts();
  });

  window.handleWorkbook = handleWorkbook;
  window.loadExcelFromInput = loadExcelFromInput;
})();
