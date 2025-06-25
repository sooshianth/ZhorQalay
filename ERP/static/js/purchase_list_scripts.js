/**
 * اسکریپت‌های صفحه لیست خریدها
 * شامل مدیریت پیجینیشن، فیلترها، انتخاب سطرها و دیگر عملکردها
 */

// ذخیره tableFilter به صورت global برای استفاده در drag_and_drop_columns.js

// تابع برای اضافه کردن واحدها به هدرهای جدول
function addUnitsToHeaders() {
    const unitsMap = {
        'weight': 'کیلوگرم',
        'total_weight': 'کیلوگرم', 
        'delivered_weight': 'کیلوگرم',
        'extelaf_weight': 'کیلوگرم',
        'company_price': 'ریال',
        'customer_price': 'ریال',
        'amount_paid': 'ریال',
        'extelaf_amount': 'ریال'
    };
    
    Object.keys(unitsMap).forEach(columnId => {
        const headers = document.querySelectorAll(`.column-${columnId}`);
        headers.forEach(header => {
            const currentText = header.textContent.trim();
            const unit = unitsMap[columnId];
            
            // اگر واحد قبلاً اضافه نشده باشد
            if (!header.querySelector('.header-unit')) {
                header.innerHTML = `
                    <span class="header-text">${currentText}</span>
                    <span class="header-unit">(${unit})</span>
                `;
            }
        });
    });
}

// تابع مشاهده تاریخچه تغییرات کلی
function viewEditHistory() {
    // باز کردن مدال تاریخچه تغییرات
    const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
    historyModal.show();
    
    // پاک کردن فیلتر شناسه آبجکت اگر تنظیم شده باشد
    if (typeof editHistoryManager !== 'undefined') {
        editHistoryManager.filters.object_id = '';
        editHistoryManager.loadHistoryData();
        
        // تغییر عنوان مدال
        document.querySelector('#historyModal .modal-title').innerHTML = 
            '<i class="fas fa-history me-2"></i>تاریخچه تغییرات';
    }
}

// تابع نمایش تاریخچه تغییرات یک خرید خاص
function showPurchaseHistory(purchaseId) {
    // باز کردن مدال تاریخچه
    const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
    historyModal.show();
    
    // تنظیم فیلترها
    if (typeof editHistoryManager !== 'undefined') {
        // تنظیم فیلترها برای نمایش تاریخچه خرید خاص
        editHistoryManager.filters.object_id = purchaseId;
        
        // بارگیری داده‌ها
        editHistoryManager.loadHistoryData();
        
        // تغییر عنوان مدال
        document.querySelector('#historyModal .modal-title').innerHTML = 
            '<i class="fas fa-history me-2"></i>تاریخچه تغییرات خرید شماره ' + purchaseId;
    }
}

// تابع بروزرسانی آمار اجماعی
function updateAggregatedStats() {
    // همگام‌سازی با آمار اجماعی خریدها فقط برای نقش‌های مجاز
    const hideSensitiveInfo = window.PurchaseListConfig?.hideSensitiveInfo || false;
    if (!hideSensitiveInfo && window.purchaseAggregatedStats) {
        window.purchaseAggregatedStats.syncWithBulkEditManager();
    }
}

// تابع ساده برای تغییر رنگ سطر انتخاب شده
function toggleRowSelection(checkbox) {
    console.log('toggleRowSelection called:', checkbox.checked);
    
    const row = checkbox.closest('tr');
    if (row) {
        if (checkbox.checked) {
            row.classList.add('selected-row');
            row.style.backgroundColor = '#e3f2fd';
            row.style.borderLeft = '4px solid #2196f3';
            console.log('Row selected - added class and style');
        } else {
            row.classList.remove('selected-row');
            row.style.backgroundColor = '';
            row.style.borderLeft = '';
            console.log('Row deselected - removed class and style');
        }
    }
}

// توابع کمکی
function showSearchLoading(show) {
    const searchInput = document.getElementById('globalSearch');
    if (!searchInput) return;
    
    if (show) {
        searchInput.style.backgroundImage = 'url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iOCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjNjY2IiBzdHJva2Utd2lkdGg9IjIiLz4KPHBhdGggZD0iTTEwIDJhOCA4IDAgMCAxIDggOCIgc3Ryb2tlPSIjMDA3YmZmIiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiPgogIDxhbmltYXRlVHJhbnNmb3JtIGF0dHJpYnV0ZU5hbWU9InRyYW5zZm9ybSIgdHlwZT0icm90YXRlIiBkdXI9IjFzIiByZXBlYXRDb3VudD0iaW5kZWZpbml0ZSIgdmFsdWVzPSIwIDEwIDEwOzM2MCAxMCAxMCIvPgo8L3BhdGg+Cjwvc3ZnPg==")';
        searchInput.style.backgroundRepeat = 'no-repeat';
        searchInput.style.backgroundPosition = 'left 10px center';
        searchInput.style.paddingLeft = '40px';
    } else {
        searchInput.style.backgroundImage = '';
        searchInput.style.paddingLeft = '';
    }
}

function performQuickSearch(searchTerm) {
    const tables = document.querySelectorAll('.enable-filter');
    
    tables.forEach(table => {
        const rows = table.querySelectorAll('tbody tr');
        let visibleCount = 0;
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            let found = false;
            
            cells.forEach(cell => {
                if (cell.textContent.toLowerCase().includes(searchTerm)) {
                    found = true;
                }
            });
            
            if (found) {
                row.style.display = '';
                visibleCount++;
                // هایلایت کردن متن یافت شده
                highlightSearchTerm(row, searchTerm);
            } else {
                row.style.display = 'none';
            }
        });
        
        // نمایش تعداد نتایج
        showSearchResults(visibleCount, searchTerm);
    });
}

function highlightSearchTerm(row, searchTerm) {
    const cells = row.querySelectorAll('td');
    
    cells.forEach(cell => {
        const text = cell.textContent;
        if (text.toLowerCase().includes(searchTerm)) {
            const regex = new RegExp(`(${searchTerm})`, 'gi');
            const highlightedText = text.replace(regex, '<mark>$1</mark>');
            
            // فقط اگر سلول شامل HTML ساده باشد
            if (!cell.querySelector('input, button, a')) {
                cell.innerHTML = highlightedText;
            }
        }
    });
}

function clearQuickSearch() {
    // حذف هایلایت‌ها
    document.querySelectorAll('mark').forEach(mark => {
        mark.outerHTML = mark.textContent;
    });
    
    // نمایش همه ردیف‌ها
    document.querySelectorAll('.enable-filter tbody tr').forEach(row => {
        row.style.display = '';
    });
    
    // مخفی کردن نتایج جستجو
    const resultsDiv = document.getElementById('searchResults');
    if (resultsDiv) {
        resultsDiv.remove();
    }
}

function showSearchResults(count, searchTerm) {
    let resultsDiv = document.getElementById('searchResults');
    
    if (!resultsDiv) {
        resultsDiv = document.createElement('div');
        resultsDiv.id = 'searchResults';
        resultsDiv.style.cssText = `
            background: #e3f2fd;
            border: 1px solid #2196f3;
            border-radius: 4px;
            padding: 8px 12px;
            margin-top: 10px;
            font-size: 0.9rem;
            color: #1976d2;
        `;
        
        const searchPanel = document.querySelector('.search-panel');
        if (searchPanel) {
            searchPanel.appendChild(resultsDiv);
        }
    }
    
    resultsDiv.innerHTML = `
        <i class="fas fa-search me-2"></i>
        یافت شد: <strong>${count}</strong> نتیجه برای "<strong>${searchTerm}</strong>"
        ${count === 0 ? '<span style="color: #f44336;">- هیچ نتیجه‌ای یافت نشد</span>' : ''}
    `;
}

// تابع کمکی برای دریافت CSRF token از کوکی
function getCsrfTokenFromCookie() {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith('csrftoken=')) {
            return cookie.substring('csrftoken='.length, cookie.length);
        }
    }
    return '';
}

// تابع تغییر تعداد رکورد در هر صفحه (حالا توسط pagination مدیریت می‌شود)
function updatePerPage() {
    // این تابع دیگر نیازی ندارد چون pagination جاوااسکریپتی خودش تعداد نمایش را مدیریت می‌کند
    console.log('updatePerPage called - now handled by JavaScript pagination');
}

// تابع مدیریت pagination links (دیگر نیازی ندارد)
function handlePaginationClick(event) {
    // این تابع دیگر استفاده نمی‌شود چون pagination جاوااسکریپتی خودش کلیک‌ها را مدیریت می‌کند
    console.log('handlePaginationClick called - now handled by JavaScript pagination');
}

// راه‌اندازی pagination
function initializePagination() {
    if (!window.PurchaseListConfig) {
        console.error('PurchaseListConfig not found. Make sure pagination configuration is loaded.');
        return;
    }
    
    const config = window.PurchaseListConfig;
    
    // راه‌اندازی pagination برای جدول خریدهای فعال
    window.activePurchasesPagination = new TablePagination({
        tableSelector: '#activePurchasesTable',
        perPage: config.perPage,
        perPageOptions: config.perPageOptions,
        perPageSelector: '#perPageSelect'
    });
    
    // راه‌اندازی pagination برای جدول آرشیو شده
    window.archivedPurchasesPagination = new TablePagination({
        tableSelector: '#archivedPurchasesTable',
        perPage: config.perPage,
        perPageOptions: config.perPageOptions,
        perPageSelector: null  // از همان select box استفاده نمی‌کند
    });
    
    console.log('JavaScript pagination initialized for both tables');
}

// مدیریت ستون‌ها
function initializeColumnManagement() {
    const saveColumnsBtn = document.getElementById('saveColumnsBtn');
    if (saveColumnsBtn) {
        saveColumnsBtn.addEventListener('click', function() {
            const form = document.getElementById('columnsForm');
            const checkboxes = form.querySelectorAll('input[name="columns[]"]:checked');
            
            if (checkboxes.length === 0) {
                alert('لطفاً حداقل یک ستون را انتخاب کنید');
                return;
            }
            
            const selectedColumns = Array.from(checkboxes).map(checkbox => checkbox.value);
            console.log('ستون‌های انتخاب شده:', selectedColumns);
            
            // نمایش پیام در حال پردازش
            const originalText = saveColumnsBtn.innerHTML;
            saveColumnsBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>در حال ذخیره...';
            saveColumnsBtn.disabled = true;
            
            // ساخت FormData برای ارسال به سرور
            const formData = new FormData();
            selectedColumns.forEach(column => {
                formData.append('columns[]', column);
            });
            
            // دریافت CSRF token
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                             document.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
                             getCookie('csrftoken');
            
            console.log('CSRF Token:', csrfToken);
            
            // ارسال داده‌ها به سرور
            const updateUrl = window.PurchaseListConfig?.updateColumnsUrl || '/erp/purchases/update-columns/';
            
            fetch(updateUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            })
            .then(response => {
                console.log('وضعیت پاسخ سرور:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('داده پاسخ سرور:', data);
                if (data.status === 'success') {
                    // بستن مدال
                    const modal = bootstrap.Modal.getInstance(document.getElementById('columnsModal'));
                    if (modal) {
                        modal.hide();
                    }
                    
                    // نمایش پیام موفقیت
                    if (typeof showSuccessToast === 'function') {
                        showSuccessToast('ستون‌ها با موفقیت به‌روزرسانی شدند');
                    }
                    
                    // بارگذاری مجدد صفحه برای اعمال تغییرات
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.message || 'خطای نامشخص در سرور');
                }
            })
            .catch(error => {
                console.error('خطا در ذخیره ستون‌ها:', error);
                alert('خطا در ذخیره ستون‌ها: ' + error.message);
            })
            .finally(() => {
                // بازگردانی حالت دکمه
                saveColumnsBtn.innerHTML = originalText;
                saveColumnsBtn.disabled = false;
            });
        });
    }
    
    // انتخاب همه ستون‌ها
    const selectAllColumnsBtn = document.getElementById('selectAllColumns');
    if (selectAllColumnsBtn) {
        selectAllColumnsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const checkboxes = document.querySelectorAll('input[name="columns[]"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    }
    
    // لغو انتخاب همه ستون‌ها
    const deselectAllColumnsBtn = document.getElementById('deselectAllColumns');
    if (deselectAllColumnsBtn) {
        deselectAllColumnsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const checkboxes = document.querySelectorAll('input[name="columns[]"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    }
    
    // بازنشانی ستون‌ها به حالت پیش‌فرض
    const resetColumnsBtn = document.getElementById('resetColumnsBtn');
    if (resetColumnsBtn) {
        resetColumnsBtn.addEventListener('click', function() {
            // انتخاب ستون‌های پیش‌فرض
            const defaultColumns = ['purchase_number', 'date', 'customer', 'invoice_id', 'sales_agent', 'weight', 'cargo', 'status', 'actions'];
            
            // بازنشانی همه چک‌باکس‌ها
            const checkboxes = document.querySelectorAll('input[name="columns[]"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = defaultColumns.includes(checkbox.value);
            });
            
            // ذخیره تغییرات
            saveColumnsBtn.click();
        });
    }
}

// تابع کمکی برای دریافت cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// تابع نمایش پیام موفقیت (اگر موجود نباشد)
function showSuccessToast(message) {
    // ایجاد toast ساده اگر Bootstrap toast موجود نباشد
    const toast = document.createElement('div');
    toast.className = 'alert alert-success position-fixed';
    toast.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    toast.innerHTML = `<i class="fas fa-check-circle me-2"></i>${message}`;
    document.body.appendChild(toast);
    
    // نمایش toast
    setTimeout(() => {
        toast.style.opacity = '1';
    }, 100);
    
    // حذف toast بعد از 3 ثانیه
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// راه‌اندازی جستجوی سریع
function initializeQuickSearch() {
    const globalSearchInput = document.getElementById('globalSearch');
    if (globalSearchInput) {
        let searchTimeout;
        
        globalSearchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            
            // جلوگیری از جستجوی زیاد
            searchTimeout = setTimeout(() => {
                const searchTerm = this.value.toLowerCase().trim();
                
                if (searchTerm.length >= 2) {
                    // نمایش loading indicator
                    showSearchLoading(true);
                    
                    // شبیه‌سازی جستجوی زنده
                    setTimeout(() => {
                        performQuickSearch(searchTerm);
                        showSearchLoading(false);
                    }, 300);
                } else if (searchTerm.length === 0) {
                    // پاک کردن نتایج جستجو
                    clearQuickSearch();
                }
            }, 500);
        });
    }
}

// راه‌اندازی دکمه خروجی اکسل
function initializeExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
        // مدیریت فعال/غیرفعال بودن دکمه بر اساس انتخاب‌ها
        const updateExportButton = function() {
            const selectedRows = document.querySelectorAll('.row-checkbox:checked');
            exportBtn.disabled = selectedRows.length === 0;
            
            if (selectedRows.length > 0) {
                exportBtn.innerHTML = `<i class="fas fa-file-excel me-2"></i>خروجی اکسل (${selectedRows.length} مورد)`;
            } else {
                exportBtn.innerHTML = '<i class="fas fa-file-excel me-2"></i>خروجی اکسل';
            }
        };
        
        // بروزرسانی اولیه
        updateExportButton();
        
        // Listener برای تغییرات انتخاب
        document.addEventListener('change', function(e) {
            if (e.target.classList.contains('row-checkbox') || 
                e.target.classList.contains('select-all-checkbox') ||
                e.target.classList.contains('select-all-checkbox-archived')) {
                updateExportButton();
            }
        });
    }
}

// مدیریت toggle آرشیو
function initializeArchiveToggle() {
    const archiveToggle = document.getElementById('toggleArchived');
    const archivedContent = document.getElementById('archivedContent');
    const archiveIcon = document.getElementById('archiveIcon');
    
    if (archiveToggle && archivedContent && archiveIcon) {
        archiveToggle.addEventListener('click', function() {
            if (archivedContent.style.display === 'none') {
                archivedContent.style.display = 'block';
                archiveIcon.classList.remove('fa-chevron-down');
                archiveIcon.classList.add('fa-chevron-up');
            } else {
                archivedContent.style.display = 'none';
                archiveIcon.classList.remove('fa-chevron-up');
                archiveIcon.classList.add('fa-chevron-down');
            }
        });
    }
}

// راه‌اندازی تاریخچه تغییرات
function initializeEditHistory() {
    // اضافه کردن event listener برای دکمه‌های تاریخچه
    document.querySelectorAll('.item-history-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const purchaseId = this.getAttribute('data-id');
            showPurchaseHistory(purchaseId);
        });
    });
}

// بهبود UX برای فیلترها
function initializeFilterEnhancements() {
    const filterButtons = document.querySelectorAll('.filter-dropdown-btn');
    filterButtons.forEach(button => {
        // اضافه کردن tooltip
        button.title = 'کلیک کنید تا فیلتر این ستون را باز کنید';
        
        // بهبود نمایش visual feedback
        button.addEventListener('mouseenter', function() {
            if (!this.classList.contains('has-filters')) {
                this.style.backgroundColor = '#e3f2fd';
                this.style.color = '#1976d2';
            }
        });
        
        button.addEventListener('mouseleave', function() {
            if (!this.classList.contains('has-filters')) {
                this.style.backgroundColor = '';
                this.style.color = '';
            }
        });
    });
}

// ذخیره و بارگیری حالت فیلترها
function initializeFilterState() {
    // اضافه کردن قابلیت ذخیره حالت فیلترها در localStorage
    const saveFiltersState = function() {
        if (window.tableFilter && window.tableFilter.activeFilters) {
            localStorage.setItem('purchase_filters', JSON.stringify({
                filters: window.tableFilter.activeFilters,
                sorts: window.tableFilter.sortState,
                timestamp: Date.now()
            }));
        }
    };
    
    const loadFiltersState = function() {
        const saved = localStorage.getItem('purchase_filters');
        if (saved) {
            try {
                const data = JSON.parse(saved);
                // فقط اگر کمتر از 1 ساعت پیش ذخیره شده باشد
                if (Date.now() - data.timestamp < 3600000) {
                    // بازگردانی فیلترها (اختیاری)
                    console.log('فیلترهای ذخیره شده یافت شد:', data);
                }
            } catch (e) {
                console.log('خطا در بارگیری فیلترهای ذخیره شده:', e);
            }
        }
    };
    
    // ذخیره حالت هنگام اعمال فیلتر
    document.addEventListener('tableFilterApplied', saveFiltersState);
    document.addEventListener('tableFilterCleared', saveFiltersState);
    
    // بارگیری حالت ذخیره شده (اختیاری)
    // loadFiltersState();
}

// Event listeners برای رویدادهای فیلتر
function initializeFilterEventListeners() {
    // مدیریت رویدادهای فیلتر
    document.addEventListener('tableFilterApplied', function(e) {
        console.log('فیلتر اعمال شد:', e.detail);
        
        // بروزرسانی آمار انتخاب‌ها
        if (window.bulkEditManager) {
            window.bulkEditManager.updateSelectionAfterFilter();
        }
        
        // بروزرسانی آمار جمع‌آوری شده
        updateAggregatedStats();
    });
    
    document.addEventListener('tableFilterCleared', function(e) {
        console.log('فیلتر پاک شد:', e.detail);
        
        // بروزرسانی آمار انتخاب‌ها
        if (window.bulkEditManager) {
            window.bulkEditManager.updateSelectionAfterFilter();
        }
        
        // بروزرسانی آمار جمع‌آوری شده
        updateAggregatedStats();
    });
    
    document.addEventListener('tableFiltersCleared', function(e) {
        console.log('همه فیلترها پاک شدند:', e.detail);
        
        // بروزرسانی آمار انتخاب‌ها
        if (window.bulkEditManager) {
            window.bulkEditManager.clearSelection();
        }
        
        // مخفی کردن آمار جمع‌آوری شده
        const hideSensitiveInfo = window.PurchaseListConfig?.hideSensitiveInfo || false;
        if (!hideSensitiveInfo) {
            const aggregatedStats = document.getElementById('aggregatedStats');
            if (aggregatedStats) {
                aggregatedStats.style.display = 'none';
            }
        }
    });
}

// Event listener برای چک‌باکس‌ها
function initializeRowSelection() {
    // Event listener مستقیم برای چک‌باکس‌ها
    document.addEventListener('change', function(e) {
        if (e.target && e.target.classList.contains('row-checkbox')) {
            console.log('Direct event listener triggered');
            
            const checkbox = e.target;
            const row = checkbox.closest('tr');
            
            if (row) {
                if (checkbox.checked) {
                    row.classList.add('selected-row');
                    row.style.backgroundColor = '#e3f2fd !important';
                    row.style.borderLeft = '4px solid #2196f3';
                    console.log('Row selected via direct listener');
                } else {
                    row.classList.remove('selected-row');
                    row.style.backgroundColor = '';
                    row.style.borderLeft = '';
                    console.log('Row deselected via direct listener');
                }
            }
        }
    });
}

// تابع اصلی راه‌اندازی
function initializePurchaseListPage() {
    console.log('Initializing Purchase List Page...');
    
    // اضافه کردن واحدها به هدرهای جدول
    addUnitsToHeaders();
    
    // انتظار کوتاه برای اطمینان از بارگیری table filter
    setTimeout(() => {
        if (typeof window.tableFilter === 'undefined' && typeof TableFilter !== 'undefined') {
            window.tableFilter = new TableFilter({
                tableSelector: 'table',
                enableToast: true,
                enableIndicators: true,
                enableSummary: true,
                enableClearAll: true
            });
        }
    }, 100);
    
    console.log('Purchase List Page initialization completed');
}

// راه‌اندازی هنگام بارگیری DOM
document.addEventListener('DOMContentLoaded', function() {
    initializePurchaseListPage();
}); 