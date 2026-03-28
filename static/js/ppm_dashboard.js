/**
 * SLN TERMINUS | NEURAL MMS ENGINE
 * Purpose: Handles real-time UI updates, Asset Ticker logic, and API communication.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initializers
    lucide.createIcons();
    initializeClock();
    
    // 2. Load Core Data
    fetchDashboardStats();
    fetchWorkOrders();
    fetchAssetTicker();

    // 3. Setup File Upload Listener
    const fileInput = document.getElementById('fileUpload');
    if (fileInput) {
        fileInput.addEventListener('change', handleExcelUpload);
    }
});

/**
 * Syncs the UI with the Server-side stats
 */
async function fetchDashboardStats() {
    try {
        const response = await fetch('/api/ppm_stats'); // Pointing to your ppm_routes.py
        const data = await response.json();
        
        // Update the 3 main counters in the center panel
        updateCounter('active-pm-count', data.pending_ppm || 0);
        updateCounter('breakdown-count', data.breakdowns || 0);
        updateCounter('overdue-count', data.ppm_overdue || 0);
    } catch (error) {
        console.error("Neural Sync Error [Stats]:", error);
    }
}

/**
 * Populates the Right Panel (Asset Ticker) with Color Logic
 * Green: Monthly | Yellow: Quarterly | Red: Yearly
 */
async function fetchAssetTicker() {
    try {
        const response = await fetch('/api/assets_summary');
        const assets = await response.json();
        const tickerContainer = document.querySelector('.custom-scroll.space-y-4');
        
        tickerContainer.innerHTML = ''; // Clear skeleton

        assets.forEach(asset => {
            const freq = asset.frequency.toLowerCase();
            let colorClass = 'border-green-500';
            let labelColor = 'text-green-500';

            if (freq.includes('quarter')) {
                colorClass = 'border-yellow-500';
                labelColor = 'text-yellow-500';
            } else if (freq.includes('year')) {
                colorClass = 'border-red-500';
                labelColor = 'text-red-500';
            }

            const tickerItem = `
                <div class="flex items-center justify-between border-l-2 ${colorClass} pl-3 py-1 hover:bg-white/5 transition-all cursor-pointer">
                    <div>
                        <p class="text-xs text-white font-medium">${asset.name}</p>
                        <p class="text-[9px] text-slate-500 uppercase tracking-tighter">Due: ${asset.nextDueDate}</p>
                    </div>
                    <span class="text-[9px] ${labelColor} font-bold uppercase">${asset.frequency}</span>
                </div>
            `;
            tickerContainer.innerHTML += tickerItem;
        });
    } catch (error) {
        console.warn("Ticker failed to sync. Using local buffer.");
    }
}

/**
 * Handles Work Order Feed with Status Indicators
 */
async function fetchWorkOrders() {
    const feedContainer = document.querySelector('.overflow-y-auto.custom-scroll.space-y-3');
    
    try {
        const response = await fetch('/api/work_orders');
        const data = await response.json();
        const wos = data.work_orders;

        feedContainer.innerHTML = ''; 

        wos.forEach(wo => {
            const isClosed = wo.status === 'closed';
            const statusColor = isClosed ? 'text-slate-500' : 'text-cyan-400';
            const icon = isClosed ? 'check' : 'zap';

            const woCard = `
                <div class="p-4 rounded-xl border border-white/5 bg-gradient-to-r ${isClosed ? 'from-transparent' : 'from-cyan-500/5'} to-transparent flex justify-between items-center group hover:border-cyan-500/30 transition-all">
                    <div class="flex gap-4">
                        <div class="w-10 h-10 rounded-lg ${isClosed ? 'bg-slate-800' : 'bg-cyan-500/20'} flex items-center justify-center border border-white/5 text-cyan-400 group-hover:scale-110 transition-transform">
                            <i data-lucide="${icon}" class="w-5 h-5"></i>
                        </div>
                        <div>
                            <p class="text-white text-sm font-bold">${wo.work_order_id}</p>
                            <p class="text-[10px] text-slate-500 uppercase">${wo.task}</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="text-xs ${statusColor} font-bold tracking-tighter uppercase">${wo.status}</p>
                        <p class="text-[10px] text-slate-400">ID: ${wo.asset_id || 'N/A'}</p>
                    </div>
                </div>
            `;
            feedContainer.innerHTML += woCard;
        });
        lucide.createIcons(); // Refresh icons for new elements
    } catch (e) {
        console.error("Feed interrupt:", e);
    }
}

/**
 * Satellite Sync Clock Logic
 */
function initializeClock() {
    const clockElement = document.getElementById('clock');
    setInterval(() => {
        const now = new Date();
        clockElement.innerText = now.toLocaleTimeString('en-GB', { hour12: false });
    }, 1000);
}

/**
 * Handles Excel Upload to Server
 */
async function handleExcelUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    // Show visual feedback
    const label = document.querySelector('label[for="fileUpload"]');
    const originalText = label.innerHTML;
    label.innerHTML = `<i class="w-3 h-3 animate-spin" data-lucide="refresh-cw"></i> Processing...`;
    lucide.createIcons();

    try {
        const response = await fetch('/api/upload_assets', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            alert("Asset Matrix Updated Successfully");
            location.reload(); // Refresh to show new data
        } else {
            alert("Upload Protocol Failed");
            label.innerHTML = originalText;
        }
    } catch (err) {
        console.error("Upload Error:", err);
        label.innerHTML = originalText;
    }
}

/**
 * Utility: Animated Counter
 */
function updateCounter(id, targetValue) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText = targetValue; // Simple update, or add lerp logic for "Thinking Different"
}
// CRITICAL FIX: Proper async function declaration
document.getElementById('mobileMenuToggle')?.addEventListener('click', async (e) => {
    document.querySelector('.sidebar').classList.toggle('active');
});

// CORRECTED: Proper async function for work order creation
document.getElementById('exportWOBtn')?.addEventListener('click', async (e) => {
    window.location.href = '/api/ppm/workorders/export';
});