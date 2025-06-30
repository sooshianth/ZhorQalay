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
function showPurchaseHistory(purchaseId, customerId = null, customerName = '') {
    // باز کردن مدال تاریخچه
    const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
    historyModal.show();
    
    // تنظیم فیلترها
    if (typeof editHistoryManager !== 'undefined') {
        // ریست کامل فیلترها قبل از تنظیم فیلتر جدید
        editHistoryManager.filters = {
            app_name: 'core',
            model_name: 'Purchase',
            user: '',
            action_type: '',  
            field_name: '',
            date: '',
            object_id: purchaseId,
            customer: customerId || ''
        };
        
        // بارگیری داده‌ها
        editHistoryManager.loadHistoryData();
        
        // تغییر عنوان مدال
        let title = '<i class="fas fa-history me-2"></i>تاریخچه تغییرات خرید شماره ' + purchaseId;
        if (customerName) {
            title += ' - مشتری: ' + customerName;
        }
        
        document.querySelector('#historyModal .modal-title').innerHTML = title;
        
        // مخفی کردن فیلترها در حالت نمایش تاریخچه یک خرید خاص
        const filterSection = document.querySelector('#historyModal .filter-section');
        if (filterSection) {
            filterSection.style.display = 'none';
        }
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

// تابع بروزرسانی وضعیت دکمه خروجی اکسل (global)
function updateExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn) return;
    
    const selectedRows = document.querySelectorAll('.row-checkbox:checked');
    const selectedCount = selectedRows.length;
    
    console.log(`📊 تعداد خریدهای انتخاب شده: ${selectedCount}`);
    
    // تنظیم وضعیت دکمه
    exportBtn.disabled = selectedCount === 0;
    
    // تغییر متن دکمه
    if (selectedCount > 0) {
        exportBtn.innerHTML = `<i class="fas fa-file-excel me-2"></i>خروجی اکسل (${selectedCount} مورد)`;
        exportBtn.classList.remove('btn-secondary');
        exportBtn.classList.add('btn-success');
    } else {
        exportBtn.innerHTML = '<i class="fas fa-file-excel me-2"></i>خروجی اکسل';
        exportBtn.classList.remove('btn-success');
        exportBtn.classList.add('btn-secondary');
    }
    
    console.log(`🔘 وضعیت دکمه - disabled: ${exportBtn.disabled}, text: ${exportBtn.textContent}`);
}

// راه‌اندازی دکمه خروجی اکسل
function initializeExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn) {
        console.log('❌ دکمه خروجی اکسل یافت نشد!');
        return;
    }
    
    console.log('✅ شروع راه‌اندازی دکمه خروجی اکسل');
    
    // اضافه کردن event listener برای کلیک روی دکمه
    exportBtn.addEventListener('click', function() {
        console.log('🖱️ کلیک روی دکمه خروجی اکسل');
        
        const selectedRows = document.querySelectorAll('.row-checkbox:checked');
        
        if (selectedRows.length === 0) {
            alert('هیچ خریدی انتخاب نشده است!');
            return;
        }
        
        // جمع‌آوری آیدی‌های خریدهای انتخاب شده
        const selectedIds = Array.from(selectedRows).map(checkbox => checkbox.getAttribute('data-id'));
        
        // دریافت ستون‌های انتخاب شده
        const selectedColumns = [];
        document.querySelectorAll('input[name="columns[]"]:checked').forEach(checkbox => {
            selectedColumns.push(checkbox.value);
        });
        
        // اگر ستونی انتخاب نشده، از کوکی استفاده کن
        let columnsParam = '';
        if (selectedColumns.length > 0) {
            columnsParam = selectedColumns.join(',');
        } else {
            // استفاده از کوکی selected_columns
            const cookieColumns = getCookie('selected_columns');
            if (cookieColumns) {
                columnsParam = cookieColumns;
            } else {
                // ستون‌های پیش‌فرض
                columnsParam = 'date,customer,invoice_id,sales_agent,purchase_number,weight,cargo,status';
            }
        }
        
        console.log('Exporting purchases:', selectedIds);
        console.log('With columns:', columnsParam);
        
        // ایجاد URL برای خروجی اکسل
        const exportUrl = window.PurchaseListConfig?.exportPurchasesUrl || '/erp/purchases/export/';
        const params = new URLSearchParams();
        params.append('ids', selectedIds.join(','));
        params.append('columns', columnsParam);
        
        // باز کردن URL در پنجره جدید یا دانلود مستقیم
        const fullUrl = `${exportUrl}?${params.toString()}`;
        
        // نمایش پیام بارگیری
        const originalText = exportBtn.innerHTML;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>در حال ایجاد فایل...';
        exportBtn.disabled = true;
        
        // ایجاد لینک مخفی برای دانلود
        const downloadLink = document.createElement('a');
        downloadLink.href = fullUrl;
        downloadLink.style.display = 'none';
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        
        // بازگردانی وضعیت دکمه بعد از 3 ثانیه
        setTimeout(() => {
            exportBtn.innerHTML = originalText;
            exportBtn.disabled = false;
            updateExportButton(); // بروزرسانی دکمه براساس انتخاب‌ها
        }, 3000);
    });
    
    // بروزرسانی اولیه
    updateExportButton();
    
    // اضافه کردن visual feedback برای دکمه
    exportBtn.addEventListener('mouseenter', function() {
        if (!this.disabled) {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
        }
    });
    
    exportBtn.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '';
    });
    
    console.log('✅ راه‌اندازی دکمه خروجی اکسل کامل شد');
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
            const customerId = this.getAttribute('data-customer-id');
            const customerName = this.getAttribute('data-customer-name');
            
            console.log(`نمایش تاریخچه خرید ${purchaseId} - مشتری: ${customerName} (${customerId})`);
            showPurchaseHistory(purchaseId, customerId, customerName);
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
            console.log('🔄 Row checkbox changed');
            
            const checkbox = e.target;
            const row = checkbox.closest('tr');
            
            if (row) {
                if (checkbox.checked) {
                    row.classList.add('selected-row');
                    row.style.backgroundColor = '#e3f2fd !important';
                    row.style.borderLeft = '4px solid #2196f3';
                    console.log('✅ Row selected');
                } else {
                    row.classList.remove('selected-row');
                    row.style.backgroundColor = '';
                    row.style.borderLeft = '';
                    console.log('❌ Row deselected');
                }
            }
            
            // بروزرسانی دکمه خروجی اکسل
            console.log('📤 Calling updateExportButton...');
            try {
                if (typeof updateExportButton === 'function') {
                    updateExportButton();
                } else {
                    console.error('❌ updateExportButton is not a function!');
                }
            } catch (error) {
                console.error('❌ Error calling updateExportButton:', error);
            }
        }
        
        // بروزرسانی دکمه خروجی اکسل برای چک‌باکس‌های انتخاب همه
        if (e.target && (e.target.classList.contains('select-all-checkbox') ||
                        e.target.classList.contains('select-all-checkbox-pending') ||
                        e.target.classList.contains('select-all-checkbox-archived'))) {
            console.log('🔄 Select-all checkbox changed - updating export button');
            setTimeout(() => {
                try {
                    if (typeof updateExportButton === 'function') {
                        updateExportButton();
                    } else {
                        console.error('❌ updateExportButton is not a function!');
                    }
                } catch (error) {
                    console.error('❌ Error calling updateExportButton:', error);
                }
            }, 100);
        }
    });
}

// تابع مدیریت چک‌باکس‌های انتخاب همه
function initializeSelectAllCheckboxes() {
    // مدیریت چک‌باکس انتخاب همه برای خریدهای فعال
    const selectAllActive = document.querySelector('.select-all-checkbox');
    if (selectAllActive) {
        selectAllActive.addEventListener('change', function() {
            const activeTable = document.getElementById('activePurchasesTable');
            if (activeTable) {
                const rowCheckboxes = activeTable.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    // فراخوانی event change برای هر checkbox
                    checkbox.dispatchEvent(new Event('change'));
                });
            }
        });
    }

    // مدیریت چک‌باکس انتخاب همه برای خریدهای در انتظار پرداخت
    const selectAllPending = document.querySelector('.select-all-checkbox-pending');
    if (selectAllPending) {
        selectAllPending.addEventListener('change', function() {
            const pendingTable = document.getElementById('pendingPurchasesTable');
            if (pendingTable) {
                const rowCheckboxes = pendingTable.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    // فراخوانی event change برای هر checkbox
                    checkbox.dispatchEvent(new Event('change'));
                });
            }
        });
    }

    // مدیریت چک‌باکس انتخاب همه برای خریدهای آرشیو شده
    const selectAllArchived = document.querySelector('.select-all-checkbox-archived');
    if (selectAllArchived) {
        selectAllArchived.addEventListener('change', function() {
            const archivedTable = document.getElementById('archivedPurchasesTable');
            if (archivedTable) {
                const rowCheckboxes = archivedTable.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    // فراخوانی event change برای هر checkbox
                    checkbox.dispatchEvent(new Event('change'));
                });
            }
        });
    }

    // بروزرسانی وضعیت چک‌باکس‌های انتخاب همه بر اساس انتخاب ردیف‌ها
    document.addEventListener('change', function(e) {
        if (e.target && e.target.classList.contains('row-checkbox')) {
            const table = e.target.closest('table');
            if (table) {
                const selectAllCheckbox = table.querySelector('.select-all-checkbox, .select-all-checkbox-pending, .select-all-checkbox-archived');
                if (selectAllCheckbox) {
                    const allCheckboxes = table.querySelectorAll('.row-checkbox');
                    const checkedCheckboxes = table.querySelectorAll('.row-checkbox:checked');
                    
                    if (checkedCheckboxes.length === 0) {
                        selectAllCheckbox.checked = false;
                        selectAllCheckbox.indeterminate = false;
                    } else if (checkedCheckboxes.length === allCheckboxes.length) {
                        selectAllCheckbox.checked = true;
                        selectAllCheckbox.indeterminate = false;
                    } else {
                        selectAllCheckbox.checked = false;
                        selectAllCheckbox.indeterminate = true;
                    }
                }
            }
        }
    });
}

function togglePurchaseSection(section) {
    const content = document.getElementById(section + 'Content');
    const icon = document.getElementById(section + 'Icon');

    // Toggle content visibility
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
        // ذخیره وضعیت در sessionStorage
        sessionStorage.setItem(`purchase_section_${section}`, 'open');
    } else {
        content.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
        // ذخیره وضعیت در sessionStorage
        sessionStorage.setItem(`purchase_section_${section}`, 'closed');
    }
}

// تابع بازیابی وضعیت بخش‌ها
function restoreSectionStates() {
    const sections = ['active', 'pending', 'archived'];
    sections.forEach(section => {
        const state = sessionStorage.getItem(`purchase_section_${section}`);
        const content = document.getElementById(section + 'Content');
        const icon = document.getElementById(section + 'Icon');
        
        if (content && icon) {
            if (state === 'open') {
                content.style.display = 'block';
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            } else if (state === 'closed') {
                content.style.display = 'none';
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            } else {
                // حالت پیش‌فرض: active باز، بقیه بسته
                if (section === 'active') {
                    content.style.display = 'block';
                    icon.classList.remove('fa-chevron-down');
                    icon.classList.add('fa-chevron-up');
                } else {
                    content.style.display = 'none';
                    icon.classList.remove('fa-chevron-up');
                    icon.classList.add('fa-chevron-down');
                }
            }
        }
    });
}

// اضافه کردن تابع بازیابی وضعیت به هنگام بارگذاری صفحه
document.addEventListener('DOMContentLoaded', function() {
    // بازیابی وضعیت بخش‌ها
    setTimeout(restoreSectionStates, 100);
});

// Pagination functionality
class PurchasePagination {
    constructor() {
        this.currentFilters = this.getFiltersFromURL();
        this.isLoading = false;
        this.init();
    }

    init() {
        this.attachEventListeners();
        console.log('🔧 Pagination initialized with Ajax support');
    }

    attachEventListeners() {
        // Event listener برای کلیک روی لینک‌های pagination
        document.addEventListener('click', (e) => {
            if (e.target.closest('.page-link[data-page]')) {
                e.preventDefault();
                const link = e.target.closest('.page-link[data-page]');
                const page = link.getAttribute('data-page');
                const section = link.getAttribute('data-section');
                
                if (!this.isLoading && page && section) {
                    console.log(`👆 Clicked on page ${page} for section ${section}`);
                    this.loadPage(page, section);
                }
            }
        });

        // Event listener برای تغییر تعداد نمایش در هر صفحه
        ['activePerPage', 'pendingPerPage', 'archivedPerPage'].forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select) {
                select.addEventListener('change', (e) => {
                    const section = selectId.replace('PerPage', '');
                    const perPage = e.target.value;
                    console.log(`📏 Changed items per page to ${perPage} for section ${section}`);
                    this.changePerPage(section, perPage);
                });
            }
        });

        // Event listener برای فیلترهای جدول
        document.addEventListener('tableFiltered', () => {
            console.log('🔍 Table filtered, resetting pagination to page 1');
            this.resetPaginationToFirstPage();
        });
    }

    getFiltersFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        const filters = {};
        
        // دریافت تمام پارامترهای فیلتر از URL
        for (const [key, value] of urlParams.entries()) {
            if (!key.includes('_page') && key !== 'per_page') {
                filters[key] = value;
            }
        }
        
        return filters;
    }

    updateFilters() {
        // بروزرسانی فیلترها از فرم جستجو
        const searchForm = document.getElementById('searchForm');
        if (searchForm) {
            const formData = new FormData(searchForm);
            this.currentFilters = {};
            
            for (const [key, value] of formData.entries()) {
                if (value && value.trim() !== '') {
                    this.currentFilters[key] = value;
                }
            }
        }

        // دریافت فیلترهای جدول از table_filter
        if (window.tableFilter && typeof window.tableFilter.getActiveFilters === 'function') {
            const tableFilters = window.tableFilter.getActiveFilters();
            Object.assign(this.currentFilters, tableFilters);
        }
    }

    loadPage(page, section) {
        if (this.isLoading) return;
        
        console.log(`📄 Loading page ${page} for section ${section}`);
        
        // ذخیره وضعیت فعلی بخش‌ها
        this.saveCurrentTableState();
        
        // بروزرسانی فیلترها
        this.updateFilters();
        
        // دریافت تعداد نمایش در هر صفحه از select box
        const perPage = this.getPerPageValue(section);
        
        console.log(`📄 Loading page ${page} for section ${section} with ${perPage} items per page`);
        
        // استفاده از روش بدون AJAX برای بارگذاری مطمئن صفحه
        this.fallbackToFullReload(section, page);
    }

    changePerPage(section, perPage) {
        // تغییر تعداد نمایش در هر صفحه و بازگشت به صفحه اول
        console.log(`📊 Changing items per page to ${perPage} for ${section}`);
        
        // ذخیره تعداد نمایش برای همه select boxes
        ['active', 'pending', 'archived'].forEach(s => {
            const select = document.getElementById(`${s}PerPage`);
            if (select) {
                select.value = perPage;
            }
        });
        
        // بروزرسانی تنظیمات در پیکربندی
        if (window.PurchaseListConfig) {
            window.PurchaseListConfig.perPage = parseInt(perPage);
        }
        
        // ذخیره وضعیت فعلی بخش‌ها
        this.saveCurrentTableState();
        
        // بارگذاری صفحه با پارامترهای جدید
        const url = new URL(window.location);
        url.searchParams.set('per_page', perPage);
        
        // بازگشت به صفحه اول برای همه بخش‌ها
        ['active', 'pending', 'archived'].forEach(s => {
            url.searchParams.set(`${s}_page`, 1);
        });
        
        // هدایت به URL جدید
        window.location.href = url.toString();
    }

    getPerPageValue(section) {
        const select = document.getElementById(`${section}PerPage`);
        if (select) {
            return select.value;
        }
        
        // اگر select نبود، از URL بخوان
        const urlParams = new URLSearchParams(window.location.search);
        const perPage = urlParams.get('per_page');
        
        // مقدار پیش‌فرض 5
        return perPage || 5;
    }

    updatePaginationUI(section, paginationData) {
        const container = document.getElementById(`${section}Pagination`);
        if (!container) {
            console.warn(`⚠️ Pagination container for ${section} not found`);
            return;
        }

        // بروزرسانی اطلاعات صفحه‌بندی
        const details = container.querySelector('.pagination-details');
        if (details) {
            const perPage = this.getPerPageValue(section);
            const startIndex = ((paginationData.number - 1) * perPage) + 1;
            const endIndex = Math.min(startIndex + perPage - 1, paginationData.count);
            
            details.innerHTML = `
                <span class="text-muted">نمایش ${startIndex} تا ${endIndex} از ${paginationData.count} خرید ${this.getSectionTitle(section)}</span>
            `;
        }

        // بروزرسانی لینک‌های pagination
        this.updatePaginationLinks(section, paginationData);
    }

    updatePaginationLinks(section, paginationData) {
        const nav = document.querySelector(`#${section}Pagination nav ul.pagination`);
        if (!nav) {
            console.warn(`⚠️ Pagination navigation for ${section} not found`);
            return;
        }
        
        // فقط اگر بیش از یک صفحه وجود داشته باشد، نمایش دهیم
        if (paginationData.num_pages <= 1) {
            nav.innerHTML = '';
            return;
        }

        let html = '';

        // دکمه اول و قبلی
        if (paginationData.has_previous) {
            html += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1" data-section="${section}">
                        <i class="fas fa-angle-double-right"></i> اول
                    </a>
                </li>
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${paginationData.number - 1}" data-section="${section}">
                        <i class="fas fa-angle-right"></i> قبلی
                    </a>
                </li>
            `;
        }

        // شماره صفحات با پشتیبانی از بیش‌نقطه (...)
        if (Array.isArray(paginationData.page_range)) {
            paginationData.page_range.forEach(pageNum => {
                if (pageNum === '...' || pageNum === -1) {
                    html += `
                        <li class="page-item disabled">
                            <span class="page-link">...</span>
                        </li>
                    `;
                } else {
                    const isActive = pageNum === paginationData.number;
                    html += `
                        <li class="page-item ${isActive ? 'active' : ''}">
                            <a class="page-link" href="#" data-page="${pageNum}" data-section="${section}">${pageNum}</a>
                        </li>
                    `;
                }
            });
        }

        // دکمه بعدی و آخر
        if (paginationData.has_next) {
            html += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${paginationData.number + 1}" data-section="${section}">
                        بعدی <i class="fas fa-angle-left"></i>
                    </a>
                </li>
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${paginationData.num_pages}" data-section="${section}">
                        آخر <i class="fas fa-angle-double-left"></i>
                    </a>
                </li>
            `;
        }

        nav.innerHTML = html;
    }

    getSectionTitle(section) {
        const titles = {
            'active': 'فعال',
            'pending': 'در انتظار پرداخت',
            'archived': 'آرشیو شده'
        };
        return titles[section] || section;
    }

    updateURL(page, section, perPage = null) {
        const url = new URL(window.location);
        
        // بروزرسانی پارامترهای URL
        url.searchParams.set(`${section}_page`, page);
        
        if (perPage) {
            url.searchParams.set('per_page', perPage);
        }
        
        // بروزرسانی URL بدون reload صفحه
        window.history.pushState({}, '', url);
        
        console.log(`🔗 URL updated: ${url.href}`);
    }

    resetPaginationToFirstPage() {
        // بازگشت به صفحه اول برای همه بخش‌ها بعد از اعمال فیلتر
        ['active', 'pending', 'archived'].forEach(section => {
            const currentPage = this.getCurrentPage(section);
            if (currentPage !== 1) {
                this.loadPage(1, section);
            }
        });
    }

    getCurrentPage(section) {
        const url = new URL(window.location);
        return parseInt(url.searchParams.get(`${section}_page`)) || 1;
    }

    reloadTableSection(section) {
        console.log(`🔄 Reloading table section ${section} with AJAX`);
        
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading(section);
        
        // ذخیره وضعیت فعلی بخش‌ها
        this.saveCurrentTableState();
        
        // ساخت پارامترهای درخواست
        const params = new URLSearchParams(this.currentFilters);
        const currentPage = this.getCurrentPage(section);
        params.append(`${section}_page`, currentPage);
        params.append('per_page', this.getPerPageValue(section));
        
        // برای اطمینان از دریافت پاسخ JSON با داده‌های تازه
        params.append('X-Requested-With', 'XMLHttpRequest');
        
        // ارسال درخواست AJAX برای دریافت HTML جدول
        fetch(`${window.location.pathname}?${params.toString()}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log(`✅ Received data for ${section}:`, data);
                
                // بروزرسانی UI پگینیشن
                this.updatePaginationUI(section, data.data[section]);
                
                // بروزرسانی URL بدون reload صفحه
                this.updateURL(currentPage, section, this.getPerPageValue(section));
                
                // چون نمی‌توانیم مستقیماً داده‌ها را در جدول نمایش دهیم (نیاز به HTML داریم)
                // مجبوریم کل صفحه را بارگذاری مجدد کنیم
                // در آینده می‌توان با دریافت HTML بخش جدول این مشکل را حل کرد
                this.fallbackToFullReload(section, currentPage);
            } else {
                console.error(`❌ Error in AJAX response:`, data);
                this.fallbackToFullReload(section, currentPage);
            }
        })
        .catch(error => {
            console.error(`❌ Error in AJAX update:`, error);
            this.fallbackToFullReload(section, currentPage);
        })
        .finally(() => {
            this.isLoading = false;
            this.hideLoading(section);
        });
    }
    
    // حالت پشتیبانی برای وقتی که AJAX با مشکل مواجه می‌شود
    fallbackToFullReload(section, page) {
        console.warn(`⚠️ Falling back to full page reload for ${section}`);
        
        // ساخت URL جدید
        const url = new URL(window.location);
        url.searchParams.set(`${section}_page`, page);
        url.searchParams.set('per_page', this.getPerPageValue(section));
        
        // اضافه کردن پارامتر تصادفی برای جلوگیری از کش
        url.searchParams.set('_', new Date().getTime());
        
        // بارگذاری مجدد صفحه
        window.location.href = url.toString();
    }

    showLoading(section) {
        const container = document.getElementById(`${section}Pagination`);
        if (container) {
            container.classList.add('pagination-loading');
        }
    }

    hideLoading(section) {
        const container = document.getElementById(`${section}Pagination`);
        if (container) {
            container.classList.remove('pagination-loading');
        }
    }

    showError(section, message) {
        console.error(`Error in ${section} pagination:`, message);
        
        // نمایش toast خطا
        showErrorToast(`خطا در بارگذاری صفحه: ${message}`);
    }

    // ذخیره وضعیت فعلی جدول‌ها
    saveCurrentTableState() {
        const sections = ['active', 'pending', 'archived'];
        sections.forEach(section => {
            const content = document.getElementById(section + 'Content');
            if (content) {
                const isVisible = content.style.display !== 'none';
                sessionStorage.setItem(`purchase_section_${section}`, isVisible ? 'open' : 'closed');
            }
        });
    }
}

// Toast functions for error display
function showErrorToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast-error';
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Add styles
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #dc3545;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.style.opacity = '1';
    }, 100);
    
    // Hide and remove toast
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 5000);
}

// تابع اصلی راه‌اندازی
function initializePurchaseListPage() {
    console.log('🚀 Initializing Purchase List Page with Pagination...');
    
    // اضافه کردن واحدها به هدرهای جدول
    addUnitsToHeaders();
    
    // راه‌اندازی دکمه خروجی اکسل
    initializeExportButton();
    
    // راه‌اندازی انتخاب سطرها
    initializeRowSelection();
    
    // راه‌اندازی چک‌باکس‌های انتخاب همه
    initializeSelectAllCheckboxes();
    
    // راه‌اندازی تاریخچه تغییرات
    initializeEditHistory();

    // بازیابی وضعیت بخش‌ها
    restoreSectionStates();
    
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
    
    // Initialize pagination
    window.purchasePagination = new PurchasePagination();
    
    console.log('✅ Purchase List Page fully initialized');
}

// راه‌اندازی هنگام بارگیری DOM
document.addEventListener('DOMContentLoaded', function() {
    initializePurchaseListPage();
}); 

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔒 راه‌اندازی سیستم blur فیلدهای مالی...');
    
    // تابع برای toggle کردن blur
    function toggleFinancialFieldBlur(fieldElement) {
        const valueElement = fieldElement.querySelector('.financial-value');
        
        console.log('🖱️ کلیک روی فیلد مالی:', fieldElement.querySelector('h6').textContent.trim());
        console.log('📊 کلاس‌های فعلی valueElement:', valueElement.className);
        console.log('📊 کلاس‌های فعلی fieldElement:', fieldElement.className);
        
        if (valueElement.classList.contains('blurred')) {
            // نمایش دادن
            valueElement.classList.remove('blurred');
            valueElement.classList.add('revealed');
            fieldElement.classList.remove('blurred');
            fieldElement.classList.add('revealed');
            console.log('🔓 فیلد مالی نمایش داده شد - کلاس‌های جدید:', valueElement.className);
        } else {
            // مخفی کردن
            valueElement.classList.remove('revealed');
            valueElement.classList.add('blurred');
            fieldElement.classList.remove('revealed');
            fieldElement.classList.add('blurred');
            console.log('🔒 فیلد مالی مخفی شد - کلاس‌های جدید:', valueElement.className);
        }
    }
    
    // اضافه کردن event listener به همه فیلدهای مالی (به جز سود)
    function initializeFinancialFields() {
        const financialFields = document.querySelectorAll('.financial-field');
        
        console.log(`🔍 پیدا شد ${financialFields.length} فیلد مالی`);
        
        financialFields.forEach(function(field, index) {
            const valueElement = field.querySelector('.financial-value');
            const titleElement = field.querySelector('h6');
            
            if (!valueElement || !titleElement) {
                console.log(`❌ فیلد ${index + 1} ساختار نامعتبر دارد`);
                return;
            }
            
            // اگر این کادر سود است، آن را skip کنیم
            if (valueElement.id === 'profit') {
                console.log(`💰 کادر سود skip شد - مدیریت جداگانه دارد`);
                return;
            }
            
            // حذف event listener های قبلی
            field.removeEventListener('click', toggleFinancialFieldBlur);
            
            // ابتدا همه فیلدها را blur می‌کنیم
            valueElement.classList.remove('revealed');
            valueElement.classList.add('blurred');
            field.classList.remove('revealed'); 
            field.classList.add('blurred');
            
            // اضافه کردن event listener برای کلیک
            const clickHandler = function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('🖱️ کلیک شناسایی شد روی:', titleElement.textContent.trim());
                toggleFinancialFieldBlur(field);
            };
            
            field.addEventListener('click', clickHandler);
            
            // آیکون نشانگر برای مشاهده بهتر
            field.style.position = 'relative';
            
            console.log(`✅ فیلد مالی ${index + 1} راه‌اندازی شد:`, titleElement.textContent.trim());
        });
        
        console.log(`✅ ${financialFields.length} فیلد مالی راه‌اندازی شدند (به جز سود)`);
    }
    
    // راه‌اندازی اولیه با تأخیر کوتاه
    setTimeout(function() {
        initializeFinancialFields();
    }, 1000);
    
    // راه‌اندازی مجدد پس از بارگذاری آمار جدید
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                const aggregatedStats = document.getElementById('aggregatedStats');
                if (aggregatedStats && aggregatedStats.style.display !== 'none') {
                    console.log('🔄 باکس آمار نمایش داده شد - راه‌اندازی مجدد blur');
                    setTimeout(initializeFinancialFields, 500);
                }
            }
        });
    });
    
    // نظارت بر تغییرات در باکس آمار
    const aggregatedStats = document.getElementById('aggregatedStats');
    if (aggregatedStats) {
        observer.observe(aggregatedStats, { 
            childList: true, 
            subtree: true,
            attributes: true,
            attributeFilter: ['style']
        });
        console.log('👁️ نظارت بر باکس آمار فعال شد');
    }
    
    // اضافه کردن نظارت بر تغییرات کل صفحه برای catch کردن آپدیت‌های دیرهنگام
    const bodyObserver = new MutationObserver(function(mutations) {
        const hasFinancialFields = document.querySelectorAll('.financial-field').length > 0;
        if (hasFinancialFields) {
            console.log('🔄 فیلدهای مالی در DOM شناسایی شدند');
            setTimeout(initializeFinancialFields, 200);
        }
    });
    
    bodyObserver.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    
    
    // اضافه کردن مدیریت مخصوص کادر سود
    function setupProfitField() {
        console.log('💰 راه‌اندازی مخصوص کادر سود...');
        
        const profitElement = document.getElementById('profit');
        const profitField = profitElement ? profitElement.closest('.financial-field') : null;
        
        if (profitElement && profitField) {
            console.log('✅ کادر سود پیدا شد');
            
            // حذف تمام event listeners قبلی
            const clonedField = profitField.cloneNode(true);
            profitField.parentNode.replaceChild(clonedField, profitField);
            
            // references جدید بعد از clone
            const newProfitElement = document.getElementById('profit');
            const newProfitField = newProfitElement.closest('.financial-field');
            
            // اطمینان از وجود کلاس‌های لازم
            newProfitElement.classList.add('financial-value', 'blurred');
            newProfitField.classList.add('financial-field', 'blurred');
            
            // اعمال style مستقیم برای اطمینان
            newProfitElement.style.filter = 'blur(8px)';
            newProfitElement.style.transition = 'filter 0.3s ease';
            newProfitElement.style.userSelect = 'none';
            newProfitElement.style.pointerEvents = 'none';
            
            console.log('🔒 blur مستقیم روی کادر سود اعمال شد');
            
            // اضافه کردن listener جدید
            const profitClickHandler = function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('🖱️ کلیک روی کادر سود شناسایی شد');
                console.log('📊 وضعیت فعلی:', {
                    classes: newProfitElement.className,
                    style: newProfitElement.style.cssText,
                    isBlurred: newProfitElement.classList.contains('blurred')
                });
                
                if (newProfitElement.classList.contains('blurred')) {
                    // نمایش دادن
                    newProfitElement.classList.remove('blurred');
                    newProfitElement.classList.add('revealed');
                    newProfitField.classList.remove('blurred');
                    newProfitField.classList.add('revealed');
                    
                    // حذف blur مستقیم
                    newProfitElement.style.filter = 'blur(0px)';
                    newProfitElement.style.userSelect = 'text';
                    newProfitElement.style.pointerEvents = 'auto';
                    
                    console.log('🔓 کادر سود نمایش داده شد');
                } else {
                    // مخفی کردن
                    newProfitElement.classList.remove('revealed');
                    newProfitElement.classList.add('blurred');
                    newProfitField.classList.remove('revealed');
                    newProfitField.classList.add('blurred');
                    
                    // اعمال blur مستقیم
                    newProfitElement.style.filter = 'blur(8px)';
                    newProfitElement.style.userSelect = 'none';
                    newProfitElement.style.pointerEvents = 'none';
                    
                    console.log('🔒 کادر سود مخفی شد');
                }
                
                // وضعیت جدید
                console.log('📊 وضعیت جدید:', {
                    classes: newProfitElement.className,
                    style: newProfitElement.style.cssText
                });
            };
            
            newProfitField.addEventListener('click', profitClickHandler);
            
            // تنظیم cursor
            newProfitField.style.cursor = 'pointer';
            newProfitField.style.position = 'relative';
            
            console.log('💰 مدیریت مخصوص کادر سود راه‌اندازی شد');
            
            return true;
        } else {
            console.log('❌ کادر سود پیدا نشد');
            return false;
        }
    }
    
    // تلاش مجدد تا کادر سود پیدا شود
    function attemptProfitSetup() {
        if (!setupProfitField()) {
            console.log('⏳ تلاش مجدد برای راه‌اندازی کادر سود...');
            setTimeout(attemptProfitSetup, 500);
        }
    }
    
    setTimeout(attemptProfitSetup, 1000);
    
    // محافظت از کادر سود در مقابل تداخلات
    function protectProfitBlur() {
        const profitElement = document.getElementById('profit');
        if (profitElement && profitElement.classList.contains('blurred')) {
            // اگر کادر سود باید blur باشد اما نیست، دوباره blur کنیم
            if (profitElement.style.filter !== 'blur(8px)') {
                console.log('🛡️ محافظت از blur کادر سود - اعمال مجدد');
                profitElement.style.filter = 'blur(8px)';
                profitElement.style.userSelect = 'none';
                profitElement.style.pointerEvents = 'none';
            }
        }
    }
    
    // چک کردن هر 2 ثانیه
    setInterval(protectProfitBlur, 2000);
    
    console.log('🔒 سیستم blur فیلدهای مالی آماده است');
});