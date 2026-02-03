/* ============================================
   MULTI-SESSION FUNCTIONS - BeyondK Dashboard
   Session filter and history data loading
   ============================================ */

// Session state
let currentSessionId = '';
let currentArchivedAt = '';

/**
 * Load available sessions from API
 */
async function loadSessions() {
    try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();

        if (data.success && data.sessions) {
            const select = document.getElementById('sessionFilter');
            if (!select) return;

            select.innerHTML = '';  // Bỏ option "Tất cả phiên"

            data.sessions.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.session_id;
                opt.textContent = s.session_title || `Session ${s.session_id}`;
                select.appendChild(opt);
            });

            console.log('[Sessions] Loaded ' + data.sessions.length + ' sessions');

            // 🆕 Attach preload listeners sau khi load xong
            attachPreloadListeners();
        }
    } catch (e) {
        console.error('[Sessions] Load error:', e);
    }
}

/**
 * Handle session filter change
 */
async function onSessionChange() {
    const sessionId = document.getElementById('sessionFilter').value;
    currentSessionId = sessionId;
    currentArchivedAt = '';

    const historySelect = document.getElementById('historySlotFilter');
    const badge = document.getElementById('sessionInfoBadge');

    // 🆕 THÊM LOADING INDICATOR
    const tableWrapper = document.getElementById('tableWrapper');
    if (tableWrapper) {
        tableWrapper.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    }


    // Enable history filter và load timeslots
    if (historySelect) {
        historySelect.disabled = false;
        historySelect.innerHTML = '<option value="">🟢 Live hiện tại</option><option disabled>Đang tải...</option>';
    }

    try {
        const resp = await fetch('/api/history/timeslots?session_id=' + sessionId);
        const data = await resp.json();

        if (historySelect) {
            historySelect.innerHTML = '<option value="">🟢 Live hiện tại</option>';

            if (data.success && data.timeslots) {
                data.timeslots.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.archived_at;
                    const date = new Date(t.archived_at);
                    opt.textContent = '📁 ' + date.toLocaleString('vi-VN') + ' (' + t.item_count + ' SP)';
                    historySelect.appendChild(opt);
                });
            }
        }
    } catch (e) {
        console.error('[History] Load timeslots error:', e);
    }

    // Update badge
    if (badge) {
        badge.style.display = 'block';
        const titleEl = document.getElementById('currentSessionTitle');
        if (titleEl) {
            const select = document.getElementById('sessionFilter');
            titleEl.textContent = select.selectedOptions[0].text;
        }
    }

    // 🆕 Reset data state và reload
    if (typeof loadData === 'function') {
        dataLoaded = false;
        fullData = [];
        await loadData(false);
    }
}
/**
 * Handle history slot filter change
 */
async function onHistorySlotChange() {
    const archivedAt = document.getElementById('historySlotFilter').value;
    currentArchivedAt = archivedAt;

    if (!archivedAt) {
        // Chọn "Live hiện tại" - load live data
        if (typeof loadData === 'function') loadData(true);
        return;
    }

    // Load history data
    try {
        const resp = await fetch('/api/history/data?session_id=' + currentSessionId + '&archived_at=' + archivedAt);
        const data = await resp.json();

        if (data.success) {
            // Update global data (these should be defined in dashboard.js)
            if (typeof fullData !== 'undefined') fullData = data.data;
            if (typeof dataLoaded !== 'undefined') dataLoaded = true;

            // Update stats
            if (data.stats) {
                const totalRev = document.getElementById('totalRevenue');
                const totalConf = document.getElementById('totalConfirmedRevenue');
                const gap = document.getElementById('gapRevenue');

                if (totalRev && typeof formatCurrency === 'function')
                    totalRev.textContent = formatCurrency(data.stats.total_gmv);
                if (totalConf && typeof formatCurrency === 'function')
                    totalConf.textContent = formatCurrency(data.stats.total_nmv);
                if (gap && typeof formatCurrency === 'function')
                    gap.textContent = formatCurrency(data.stats.gap);
            }

            const countEl = document.getElementById('currentProductCount');
            if (countEl) countEl.textContent = data.count + ' SP';

            if (typeof applyFiltersAndSort === 'function') applyFiltersAndSort();
            console.log('[History] Loaded ' + data.count + ' products from archive');
        }
    } catch (e) {
        console.error('[History] Load data error:', e);
    }
}
// ============== PRELOAD ON HOVER ==============
let preloadTimeout = null;
let preloadedSessions = new Set();

/**
 * Preload session data khi hover
 */
function preloadSessionData(sessionId) {
    if (!sessionId || preloadedSessions.has(sessionId)) return;

    // Debounce 300ms - chỉ fetch nếu hover đủ lâu
    clearTimeout(preloadTimeout);
    preloadTimeout = setTimeout(async () => {
        console.log('[Preload] Prefetching session:', sessionId);
        try {
            const resp = await fetch(`/api/all-data?session_id=${encodeURIComponent(sessionId)}`);
            const data = await resp.json();
            if (data.success) {
                // Cache vào localStorage
                const cacheKey = `gmv_dashboard_data_${sessionId}`;
                localStorage.setItem(cacheKey, JSON.stringify({
                    version: 4,  // Phải khớp với CACHE_VERSION trong index.html
                    data: data.data,
                    shopIds: data.shop_ids,
                    stats: data.stats,
                    lastSync: data.last_sync,
                    timestamp: Date.now()
                }));
                preloadedSessions.add(sessionId);
                console.log('[Preload] Cached session:', sessionId, '(' + data.data.length + ' products)');
            }
        } catch (e) {
            console.error('[Preload] Error:', e);
        }
    }, 300);
}

/**
 * Attach hover listener cho session dropdown
 */
function attachPreloadListeners() {
    const select = document.getElementById('sessionFilter');
    if (!select) return;

    // Hover event trên dropdown
    select.addEventListener('mouseenter', () => {
        // Preload tất cả sessions khi mở dropdown
        const options = select.querySelectorAll('option[value]');
        options.forEach((opt, index) => {
            if (opt.value && index < 3) {  // Chỉ preload 3 sessions đầu
                setTimeout(() => preloadSessionData(opt.value), index * 500);
            }
        });
    });

    console.log('[Preload] Listeners attached');
}