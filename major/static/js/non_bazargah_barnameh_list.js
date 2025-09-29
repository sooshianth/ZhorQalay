/**
 * مدیریت ستون‌های جدول بارنامه‌های خارج از بازارگاه
 * این فایل شامل قابلیت‌های مدیریت ستون‌ها، نمایش/مخفی کردن ستون‌ها و ذخیره تنظیمات کاربر است
 */

document.addEventListener('DOMContentLoaded', function() {
    // متغیرهای سراسری
    const table = document.getElementById('barnamehsTable');
    const columnsModal = document.getElementById('columnsModal');
    const columnsForm = document.getElementById('columnsForm');
    const selectAllBtn = document.getElementById('selectAllColumns');
    const deselectAllBtn = document.getElementById('deselectAllColumns');
    const saveColumnsBtn = document.getElementById('saveColumnsBtn');
    
    // متغیرهای مربوط به انتخاب ردیف‌ها و خروجی اکسل
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');
    const selectAllRowsBtn = document.getElementById('selectAllRowsBtn');
    const deselectAllRowsBtn = document.getElementById('deselectAllRowsBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    
    // کلید ذخیره تنظیمات در localStorage
    const STORAGE_KEY = 'non_bazargah_barnameh_columns';
    
    // تنظیمات پیش‌فرض ستون‌ها
    const DEFAULT_COLUMNS = [
        'select',
        'number',
        'serial',
        'tonnage',
        'driver_name',
        'driver_phone',
        'vehicle_plate',
        'receiver_name',
        'destination',
        'barnameh_date',
        'purchase_number',
        'customer',
        'product',
        'buyer_name',
        'company_price',
        'customer_price',
        'total_sales_amount',
        'total_purchase_amount',
        'actions'
    ];
    
    /**
     * بارگذاری تنظیمات ستون‌ها از localStorage
     */
    function loadColumnSettings() {
        try {
            const savedSettings = localStorage.getItem(STORAGE_KEY);
            if (savedSettings) {
                return JSON.parse(savedSettings);
            }
        } catch (error) {
            console.warn('خطا در بارگذاری تنظیمات ستون‌ها:', error);
        }
        return DEFAULT_COLUMNS;
    }
    
    /**
     * ذخیره تنظیمات ستون‌ها در localStorage
     */
    function saveColumnSettings(visibleColumns) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(visibleColumns));
            console.log('تنظیمات ستون‌ها ذخیره شد:', visibleColumns);
        } catch (error) {
            console.error('خطا در ذخیره تنظیمات ستون‌ها:', error);
        }
    }
    
    /**
     * اعمال تنظیمات ستون‌ها به جدول
     */
    function applyColumnSettings(visibleColumns) {
        if (!table) return;
        
        // پیدا کردن تمام ستون‌ها
        const headers = table.querySelectorAll('thead th[data-column-id]');
        const rows = table.querySelectorAll('tbody tr');
        
        headers.forEach(header => {
            const columnId = header.getAttribute('data-column-id');
            const isVisible = visibleColumns.includes(columnId);
            
            // نمایش/مخفی کردن header
            header.style.display = isVisible ? '' : 'none';
            
            // نمایش/مخفی کردن سلول‌های مربوطه در هر ردیف
            rows.forEach(row => {
                const cell = row.querySelector(`td[data-column="${columnId}"]`);
                if (cell) {
                    cell.style.display = isVisible ? '' : 'none';
                }
            });
        });
        
        // بروزرسانی checkbox ها در modal
        updateModalCheckboxes(visibleColumns);
        
        // حفظ استایل‌های انتخاب ردیف‌ها
        rows.forEach(row => {
            const checkbox = row.querySelector('.row-checkbox');
            if (checkbox && checkbox.checked) {
                row.classList.add('selected');
            }
        });
    }
    
    /**
     * بروزرسانی checkbox های modal بر اساس ستون‌های قابل مشاهده
     */
    function updateModalCheckboxes(visibleColumns) {
        const checkboxes = columnsForm.querySelectorAll('input[name="columns[]"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = visibleColumns.includes(checkbox.value);
        });
    }
    
    /**
     * دریافت ستون‌های انتخاب شده از modal
     */
    function getSelectedColumns() {
        const checkboxes = columnsForm.querySelectorAll('input[name="columns[]"]:checked');
        return Array.from(checkboxes).map(checkbox => checkbox.value);
    }
    
    /**
     * انتخاب همه ستون‌ها
     */
    function selectAllColumns() {
        const checkboxes = columnsForm.querySelectorAll('input[name="columns[]"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
    }
    
    /**
     * لغو انتخاب همه ستون‌ها
     */
    function deselectAllColumns() {
        const checkboxes = columnsForm.querySelectorAll('input[name="columns[]"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
    }
    
    /**
     * اعمال تنظیمات جدید و ذخیره آن‌ها
     */
    function applyAndSaveSettings() {
        const selectedColumns = getSelectedColumns();
        
        // حداقل یک ستون باید انتخاب شده باشد
        if (selectedColumns.length === 0) {
            alert('لطفاً حداقل یک ستون را انتخاب کنید.');
            return;
        }
        
        // اعمال تنظیمات جدید
        applyColumnSettings(selectedColumns);
        
        // ذخیره تنظیمات
        saveColumnSettings(selectedColumns);
        
        // بستن modal
        const modal = bootstrap.Modal.getInstance(columnsModal);
        if (modal) {
            modal.hide();
        }
        
        // نمایش پیام موفقیت
        showSuccessMessage('تنظیمات ستون‌ها با موفقیت ذخیره شد.');
    }
    
    /**
     * نمایش پیام موفقیت
     */
    function showSuccessMessage(message) {
        // ایجاد toast notification
        const toastContainer = document.getElementById('toast-container') || createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = 'toast align-items-center text-white bg-success border-0';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-check-circle me-2"></i>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // حذف toast بعد از نمایش
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
    
    /**
     * ایجاد container برای toast notifications
     */
    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }
    
    /**
     * انتخاب همه ردیف‌ها
     */
    function selectAllRows() {
        const checkboxes = document.querySelectorAll('.row-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            updateRowSelection(checkbox);
        });
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = true;
        }
        updateExportButtonState();
    }
    
    /**
     * لغو انتخاب همه ردیف‌ها
     */
    function deselectAllRows() {
        const checkboxes = document.querySelectorAll('.row-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            updateRowSelection(checkbox);
        });
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        updateExportButtonState();
    }
    
    /**
     * بروزرسانی استایل ردیف بر اساس وضعیت انتخاب
     */
    function updateRowSelection(checkbox) {
        const row = checkbox.closest('tr');
        if (!row) return;
        
        if (checkbox.checked) {
            // اضافه کردن کلاس انتخاب با انیمیشن
            row.classList.add('selecting');
            setTimeout(() => {
                row.classList.remove('selecting');
                row.classList.add('selected');
            }, 500);
        } else {
            // حذف کلاس انتخاب
            row.classList.remove('selected');
        }
    }
    
    /**
     * دریافت شناسه‌های بارنامه‌های انتخاب شده
     */
    function getSelectedBarnamehIds() {
        const checkboxes = document.querySelectorAll('.row-checkbox:checked');
        return Array.from(checkboxes).map(checkbox => checkbox.value);
    }
    
    /**
     * بروزرسانی وضعیت دکمه خروجی اکسل
     */
    function updateExportButtonState() {
        const selectedIds = getSelectedBarnamehIds();
        if (exportExcelBtn) {
            exportExcelBtn.disabled = selectedIds.length === 0;
            if (selectedIds.length > 0) {
                exportExcelBtn.innerHTML = `<i class="fas fa-file-excel me-2"></i>خروجی اکسل (${selectedIds.length})`;
            } else {
                exportExcelBtn.innerHTML = `<i class="fas fa-file-excel me-2"></i>خروجی اکسل`;
            }
        }
    }
    
    /**
     * خروجی اکسل
     */
    function exportToExcel() {
        const selectedIds = getSelectedBarnamehIds();
        if (selectedIds.length === 0) {
            alert('لطفاً حداقل یک بارنامه را انتخاب کنید.');
            return;
        }
        
        const visibleColumns = loadColumnSettings();
        
        // ایجاد فرم برای ارسال درخواست POST
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/major/non-bazargah-barnamehs/export-excel/';
        form.style.display = 'none';
        
        // اضافه کردن CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);
        
        // اضافه کردن شناسه‌های انتخاب شده
        const idsInput = document.createElement('input');
        idsInput.type = 'hidden';
        idsInput.name = 'ids';
        idsInput.value = selectedIds.join(',');
        form.appendChild(idsInput);
        
        // اضافه کردن ستون‌های انتخاب شده
        const columnsInput = document.createElement('input');
        columnsInput.type = 'hidden';
        columnsInput.name = 'columns';
        columnsInput.value = visibleColumns.join(',');
        form.appendChild(columnsInput);
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    }
    
    /**
     * تنظیم event listeners
     */
    function setupEventListeners() {
        // دکمه انتخاب همه
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', selectAllColumns);
        }
        
        // دکمه لغو انتخاب همه
        if (deselectAllBtn) {
            deselectAllBtn.addEventListener('click', deselectAllColumns);
        }
        
        // دکمه ذخیره تنظیمات
        if (saveColumnsBtn) {
            saveColumnsBtn.addEventListener('click', applyAndSaveSettings);
        }
        
        // تنظیم مجدد ستون‌ها هنگام باز شدن modal
        if (columnsModal) {
            columnsModal.addEventListener('show.bs.modal', function() {
                const visibleColumns = loadColumnSettings();
                updateModalCheckboxes(visibleColumns);
            });
        }
        
        // Event listeners برای انتخاب ردیف‌ها
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const checkboxes = document.querySelectorAll('.row-checkbox');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    updateRowSelection(checkbox);
                });
                updateExportButtonState();
            });
        }
        
        // Event listeners برای checkbox های ردیف‌ها
        document.addEventListener('change', function(e) {
            if (e.target.classList.contains('row-checkbox')) {
                updateRowSelection(e.target);
                updateExportButtonState();
                
                // بروزرسانی checkbox انتخاب همه
                const allCheckboxes = document.querySelectorAll('.row-checkbox');
                const checkedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = allCheckboxes.length === checkedCheckboxes.length;
                    selectAllCheckbox.indeterminate = checkedCheckboxes.length > 0 && checkedCheckboxes.length < allCheckboxes.length;
                }
            }
        });
        
        // دکمه‌های انتخاب همه/لغو انتخاب همه ردیف‌ها
        if (selectAllRowsBtn) {
            selectAllRowsBtn.addEventListener('click', selectAllRows);
        }
        
        if (deselectAllRowsBtn) {
            deselectAllRowsBtn.addEventListener('click', deselectAllRows);
        }
        
        // دکمه خروجی اکسل
        if (exportExcelBtn) {
            exportExcelBtn.addEventListener('click', exportToExcel);
        }
    }
    
    /**
     * تنظیم responsive table
     */
    function setupResponsiveTable() {
        if (!table) return;
        
        // اضافه کردن کلاس‌های responsive
        const tableContainer = table.closest('.table-responsive');
        if (tableContainer) {
            tableContainer.style.overflowX = 'auto';
            tableContainer.style.webkitOverflowScrolling = 'touch';
        }
        
        // تنظیم حداقل عرض برای ستون‌ها
        const headers = table.querySelectorAll('thead th');
        headers.forEach(header => {
            const minWidth = header.style.minWidth || '120px';
            header.style.minWidth = minWidth;
        });
    }
    
    /**
     * تنظیم اولیه صفحه
     */
    function initialize() {
        // بارگذاری تنظیمات ذخیره شده
        const visibleColumns = loadColumnSettings();
        
        // اعمال تنظیمات به جدول
        applyColumnSettings(visibleColumns);
        
        // تنظیم responsive table
        setupResponsiveTable();
        
        // تنظیم event listeners
        setupEventListeners();
        
        console.log('مدیریت ستون‌های جدول بارنامه‌های خارج از بازارگاه راه‌اندازی شد.');
    }
    
    // راه‌اندازی اولیه
    initialize();
    
    // اضافه کردن توابع به window برای دسترسی از خارج
    window.NonBazargahBarnamehColumns = {
        loadSettings: loadColumnSettings,
        saveSettings: saveColumnSettings,
        applySettings: applyColumnSettings,
        resetToDefault: function() {
            applyColumnSettings(DEFAULT_COLUMNS);
            saveColumnSettings(DEFAULT_COLUMNS);
            showSuccessMessage('تنظیمات به حالت پیش‌فرض بازگردانده شد.');
        }
    };
});