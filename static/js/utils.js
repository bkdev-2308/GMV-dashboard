/* ============================================
   UTILITY FUNCTIONS - BeyondK Dashboard
   Shared helper functions
   ============================================ */

/**
 * Format number to currency with đ suffix
 * @param {number} value 
 * @returns {string}
 */
function formatCurrency(value) {
    if (!value || value === 0) return '0đ';
    if (value >= 1000000000) return (value / 1000000000).toFixed(1) + 'B đ';
    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M đ';
    if (value >= 1000) return (value / 1000).toFixed(0) + 'K đ';
    return value.toLocaleString() + ' đ';
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/**
 * Show toast notification
 * @param {string} message 
 * @param {number} duration - Duration in ms
 */
function showToast(message, duration = 2000) {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMessage');
    if (toast && toastMsg) {
        toastMsg.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), duration);
    }
}

/**
 * Debounce function
 * @param {Function} func 
 * @param {number} wait 
 * @returns {Function}
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Toggle sidebar expand/collapse
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    if (sidebar) sidebar.classList.toggle('expanded');
    if (mainContent) mainContent.classList.toggle('expanded');
}

/**
 * Copy Modal Functions (for iOS compatibility)
 */
function showCopyModal(content) {
    const modal = document.getElementById('copyModal');
    const input = document.getElementById('copyModalInput');
    if (modal && input) {
        input.value = content;
        modal.classList.add('show');
        input.focus();
        input.select();
    }
}

function closeCopyModal(event) {
    if (!event || event.target.id === 'copyModal') {
        const modal = document.getElementById('copyModal');
        if (modal) modal.classList.remove('show');
    }
}

function tryCopyFromModal() {
    const input = document.getElementById('copyModalInput');
    if (input) {
        input.select();
        input.setSelectionRange(0, 99999);

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(input.value)
                .then(() => {
                    showToast('Đã copy!');
                    closeCopyModal();
                })
                .catch(() => {
                    document.execCommand('copy');
                    showToast('Đã copy!');
                    closeCopyModal();
                });
        } else {
            document.execCommand('copy');
            showToast('Đã copy!');
            closeCopyModal();
        }
    }
}

/**
 * Copy single link
 * @param {string} link 
 */
async function copyLink(link) {
    if (!link) {
        showToast('Không có link!');
        return;
    }

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);

    if (isIOS) {
        showCopyModal(link);
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(link);
            showToast('Đã copy link!');
        } catch {
            showCopyModal(link);
        }
    } else {
        showCopyModal(link);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { formatCurrency, escapeHtml, showToast, debounce, toggleSidebar, copyLink };
}
