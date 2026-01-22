// Admin Panel JavaScript

$(document).ready(function() {
    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Initialize popovers
    $('[data-bs-toggle="popover"]').popover();
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);
    
    // Table row click for mobile
    $('tr[data-href]').on('click', function() {
        window.location = $(this).data('href');
    });
    
    // Form validation
    $('form').on('submit', function(e) {
        const requiredFields = $(this).find('[required]');
        let valid = true;
        
        requiredFields.each(function() {
            if (!$(this).val().trim()) {
                valid = false;
                $(this).addClass('is-invalid');
                $(this).after('<div class="invalid-feedback">This field is required</div>');
            } else {
                $(this).removeClass('is-invalid');
                $(this).next('.invalid-feedback').remove();
            }
        });
        
        if (!valid) {
            e.preventDefault();
            showToast('warning', 'Please fill all required fields');
        }
    });
    
    // Real-time clock in navbar
    function updateClock() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
        $('.navbar-clock').text(timeString);
    }
    
    // Update clock every minute
    updateClock();
    setInterval(updateClock, 60000);
    
    // Search functionality for tables
    $('#searchInput').on('keyup', function() {
        const value = $(this).val().toLowerCase();
        $('table tbody tr').filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
    });
    
    // Export buttons
    $('.export-btn').on('click', function() {
        const format = $(this).data('format');
        const tableId = $(this).data('table');
        exportTable(format, tableId);
    });
    
    // Status badge click to filter
    $('.status-badge').on('click', function() {
        const status = $(this).data('status');
        window.location.href = `/admin/orders?filter=${status}`;
    });
});

// Export table data
function exportTable(format, tableId) {
    const table = document.getElementById(tableId);
    let data = [];
    
    // Get headers
    const headers = [];
    $(table).find('thead th').each(function() {
        headers.push($(this).text().trim());
    });
    
    // Get rows
    $(table).find('tbody tr').each(function() {
        const row = [];
        $(this).find('td').each(function() {
            // Remove buttons and icons from export
            const clone = $(this).clone();
            clone.find('button, .btn, .badge').remove();
            row.push(clone.text().trim());
        });
        data.push(row);
    });
    
    if (format === 'csv') {
        exportToCSV(headers, data, 'orders.csv');
    } else if (format === 'excel') {
        exportToExcel(headers, data, 'orders.xlsx');
    }
}

function exportToCSV(headers, rows, filename) {
    let csvContent = "data:text/csv;charset=utf-8,";
    
    // Add headers
    csvContent += headers.join(",") + "\r\n";
    
    // Add rows
    rows.forEach(row => {
        csvContent += row.join(",") + "\r\n";
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('success', 'CSV exported successfully');
}

function exportToExcel(headers, rows, filename) {
    // For simplicity, we'll create CSV and rename as Excel
    // In production, use a proper Excel library like SheetJS
    exportToCSV(headers, rows, filename);
}

// Show toast notification
function showToast(type, message) {
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${getToastIcon(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    const toastContainer = $('#toastContainer');
    if (toastContainer.length === 0) {
        $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3"></div>');
    }
    
    $('#toastContainer').append(toastHtml);
    const toastElement = $('#toastContainer .toast').last();
    const toast = new bootstrap.Toast(toastElement[0]);
    toast.show();
    
    toastElement.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

function getToastIcon(type) {
    const icons = {
        'success': 'bi-check-circle',
        'warning': 'bi-exclamation-triangle',
        'danger': 'bi-x-circle',
        'info': 'bi-info-circle'
    };
    return icons[type] || 'bi-info-circle';
}

// Confirm before action
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Format currency
function formatCurrency(amount) {
    return '₹' + parseFloat(amount).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

// Format date to IST
function formatISTDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('success', 'Copied to clipboard');
    }).catch(function(err) {
        showToast('danger', 'Failed to copy');
    });
}

// Print order
function printOrder(orderId) {
    window.open(`/admin/order/${orderId}/print`, '_blank');
}

// Refresh data
function refreshData() {
    showToast('info', 'Refreshing data...');
    setTimeout(() => {
        location.reload();
    }, 1000);
}

// Keyboard shortcuts
$(document).on('keydown', function(e) {
    // Ctrl + R to refresh
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        refreshData();
    }
    
    // Ctrl + F to focus search
    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        $('#searchInput').focus();
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        $('.modal').modal('hide');
    }
});

// Auto-refresh every 5 minutes for real-time updates
setTimeout(refreshData, 5 * 60 * 1000);

// Initialize data tables
function initDataTable(tableId) {
    if ($.fn.DataTable) {
        $(tableId).DataTable({
            pageLength: 25,
            order: [[0, 'desc']],
            language: {
                search: "Search:",
                lengthMenu: "Show _MENU_ entries",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "Showing 0 to 0 of 0 entries",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            }
        });
    }
}

// Initialize on page load
$(document).ready(function() {
    initDataTable('#ordersTable');
});
