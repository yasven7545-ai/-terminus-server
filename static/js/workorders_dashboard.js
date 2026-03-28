// static/js/workorders_dashboard.js

console.log("Work Orders Dashboard JS Loaded");

const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

let workOrders = [];

// ==========================================
// LOAD DATA
// ==========================================
async function loadWorkOrders() {
    try {
        // Fetch ALL work orders initially
        const res = await fetch(`${API}/load`);
        const data = await res.json();
        workOrders = data || [];
        
        console.log(`Loaded ${workOrders.length} work orders.`);
        
        // After loading, render the current month
        renderWorkOrders(window.CURRENT_YEAR, window.CURRENT_MONTH);
        
    } catch (e) {
        console.error("Error loading work orders:", e);
        id("wo-list").innerHTML = "<li style='color:red;'>Failed to load work orders from the server.</li>";
    }
}

// ==========================================
// RENDERING
// ==========================================
function renderWorkOrders(year, monthIndex) {
    const list = id("wo-list");
    const monthName = MONTHS[monthIndex];
    
    id("monthTitle").textContent = `${monthName} ${year}`;
    list.innerHTML = ""; // Clear previous list

    // Month in string format for filtering (e.g., "2025-12")
    const monthFilter = `${year}-${(monthIndex + 1).toString().padStart(2, '0')}`;
    
    const filteredWOs = workOrders.filter(wo => {
        // Assuming work order date is in ISO format like "2025-12-15"
        return wo.date && wo.date.startsWith(monthFilter);
    });

    if (filteredWOs.length === 0) {
        list.innerHTML = "<li style='color:rgba(255,255,255,0.7);'>No work orders found for this month.</li>";
        return;
    }

    // Sort by date (oldest first)
    filteredWOs.sort((a, b) => new Date(a.date) - new Date(b.date));

    filteredWOs.forEach(wo => {
        const item = document.createElement("li");
        item.className = "wo-item";
        
        // Simple display of key properties
        item.innerHTML = `
            <span><strong>ID:</strong> ${wo.id}</span>
            <span><strong>Date:</strong> ${wo.date}</span>
            <span><strong>Asset:</strong> ${wo.asset}</span>
            <span><strong>Team:</strong> ${wo.asset_type}</span>
            <span><strong>Status:</strong> ${wo.status}</span>
        `;
        list.appendChild(item);
    });
}

// ==========================================
// NAVIGATION
// ==========================================
function prevMonth() {
    window.CURRENT_MONTH--;
    if (window.CURRENT_MONTH < 0) {
        window.CURRENT_MONTH = 11;
        window.CURRENT_YEAR--;
    }
    renderWorkOrders(window.CURRENT_YEAR, window.CURRENT_MONTH);
}

function nextMonth() {
    window.CURRENT_MONTH++;
    if (window.CURRENT_MONTH > 11) {
        window.CURRENT_MONTH = 0;
        window.CURRENT_YEAR++;
    }
    renderWorkOrders(window.CURRENT_YEAR, window.CURRENT_MONTH);
}

// ==========================================
// EXPORT PDF
// ==========================================
function exportPDF() {
    const year = window.CURRENT_YEAR;
    const month = (window.CURRENT_MONTH + 1).toString().padStart(2, '0');
    
    // The server handles the file download via this API route
    window.location.href = `${API}/report/${year}/${month}`;
}


// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    // Bind UI buttons
    id("btnPrevMonth")?.addEventListener("click", prevMonth);
    id("btnNextMonth")?.addEventListener("click", nextMonth);
    id("btnExportPDF")?.addEventListener("click", exportPDF);
    
    // Load initial data
    loadWorkOrders();
});