/* =========================
FILE: static/js/ppm_editor.js
========================= */
function updateAssetField(index, field, value) {
  if (!state.assets[index]) return;
  state.assets[index][field] = value || null;
}
