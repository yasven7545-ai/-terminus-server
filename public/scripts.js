const btn = document.getElementById("vacantGraphBtn");
const popup = document.getElementById("popup");
const closeBtn = document.querySelector(".close");
const table = document.getElementById("data-table");

btn.addEventListener("click", async () => {
  const res = await fetch("/api/vacant-data");
  const data = await res.json();
  
  table.innerHTML = "";
  if (data.length > 0) {
    const headers = Object.keys(data[0]);
    const headerRow = `<tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr>`;
    const rows = data.map(row => `<tr>${headers.map(h => `<td>${row[h]}</td>`).join("")}</tr>`).join("");
    table.innerHTML = headerRow + rows;
  } else {
    table.innerHTML = "<tr><td>No data available</td></tr>";
  }
  popup.style.display = "flex";
});

closeBtn.addEventListener("click", () => {
  popup.style.display = "none";
});

window.onclick = function(event) {
  if (event.target == popup) {
    popup.style.display = "none";
  }
};
