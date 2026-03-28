/* =========================
FILE: static/js/ppm_work.js
========================= */
function openWorkOrder(assetId, date) {
  const s = state.schedules.find(x => x.assetId === assetId && x.date === date);
  if (!s || s.status !== "Pending") return;
  s.status = "Open";
}

function closeWorkOrder(assetId, date) {
  const s = state.schedules.find(x => x.assetId === assetId && x.date === date);
  if (!s || s.status !== "Open") return;
  s.status = "Closed";
}
