/**
 * مدیریت ستون‌های جدول خریدهای خارج از بازارگاه
 * این فایل شامل قابلیت‌های مدیریت ستون‌ها، نمایش/مخفی کردن ستون‌ها و ذخیره تنظیمات کاربر است
 */

document.addEventListener('DOMContentLoaded', function() {
    // متغیرهای سراسری
    const table = document.getElementById('purchasesTable');
    const columnsModal = document.getElementById('columnsModal');
    const columnsForm = document.getElementById('columnsForm');
    const selectAllBtn = document.getElementById('selectAllColumns');
    const deselectAllBtn = document.getElementById('deselectAllColumns');
    const saveColumnsBtn = document.getElementById('saveColumnsBtn');
    
    // متغیرهای مربوط به انتخاب سطرها و خروجی اکسل
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const selectAllRowsBtn = document.getElementById('selectAllRowsBtn');
    const deselectAllRowsBtn = document.getElementById('deselectAllRowsBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    
    // کلید ذخیره تنظیمات در localStorage
    const STORAGE_KEY = 'non_bazargah_purchase_columns';
    
    // تنظیمات پیش‌فرض ستون‌ها
    const DEFAULT_COLUMNS = [
        'select',
        'purchase_number',
        'created_at', 
        'unique_sales_agent',
        'total_weight',
        'state',
        'product',
        'unit',
        'customer',
        'buyer_name',
        'customer_price',
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
     * دریافت تمام checkbox های سطرها
     */
    function getRowCheckboxes() {
        return table ? table.querySelectorAll('tbody .row-checkbox') : [];
    }
    
    /**
     * دریافت شناسه‌های خریدهای انتخاب شده
     */
    function getSelectedPurchaseIds() {
        const checkboxes = getRowCheckboxes();
        const selectedIds = [];
        
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                selectedIds.push(checkbox.value);
            }
        });
        
        return selectedIds;
    }
    
    /**
     * بروزرسانی وضعیت دکمه خروجی اکسل
     */
    function updateExportButtonState() {
        const selectedIds = getSelectedPurchaseIds();
        const hasSelection = selectedIds.length > 0;
        
        if (exportExcelBtn) {
            exportExcelBtn.disabled = !hasSelection;
            exportExcelBtn.title = hasSelection 
                ? `خروجی اکسل از ${selectedIds.length} خرید انتخاب شده`
                : 'ابتدا خریدهای مورد نظر را انتخاب کنید';
        }
    }
    
    /**
     * بروزرسانی ظاهر سطرهای انتخاب شده
     */
    function updateRowAppearance() {
        const checkboxes = getRowCheckboxes();
        
        checkboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                if (checkbox.checked) {
                    row.classList.add('table-active', 'selected-row');
                    row.style.backgroundColor = '#e3f2fd';
                    row.style.borderLeft = '4px solid #2196f3';
                } else {
                    row.classList.remove('table-active', 'selected-row');
                    row.style.backgroundColor = '';
                    row.style.borderLeft = '';
                }
            }
        });
    }
    
    /**
     * انتخاب همه سطرها
     */
    function selectAllRows() {
        const checkboxes = getRowCheckboxes();
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = true;
        }
        
        updateRowAppearance();
        updateExportButtonState();
    }
    
    /**
     * لغو انتخاب همه سطرها
     */
    function deselectAllRows() {
        const checkboxes = getRowCheckboxes();
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        updateRowAppearance();
        updateExportButtonState();
    }
    
    /**
     * بررسی وضعیت انتخاب همه
     */
    function updateSelectAllCheckbox() {
        const checkboxes = getRowCheckboxes();
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        const totalCount = checkboxes.length;
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = checkedCount === totalCount && totalCount > 0;
            selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
        }
        
        updateRowAppearance();
        updateExportButtonState();
    }
    
    /**
     * خروجی اکسل از خریدهای انتخاب شده
     */
    function exportSelectedPurchasesToExcel() {
        const selectedIds = getSelectedPurchaseIds();
        
        if (selectedIds.length === 0) {
            alert('لطفاً ابتدا خریدهای مورد نظر را انتخاب کنید.');
            return;
        }
        
        // دریافت ستون‌های قابل مشاهده
        const visibleColumns = loadColumnSettings();
        
        // ایجاد فرم برای ارسال داده‌ها
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/major/non-bazargah-purchases/export-excel/';
        form.style.display = 'none';
        
        // اضافه کردن CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = csrfToken.value;
            form.appendChild(csrfInput);
        }
        
        // اضافه کردن شناسه‌های انتخاب شده
        const idsInput = document.createElement('input');
        idsInput.type = 'hidden';
        idsInput.name = 'ids';
        idsInput.value = selectedIds.join(',');
        form.appendChild(idsInput);
        
        // اضافه کردن ستون‌های قابل مشاهده
        const columnsInput = document.createElement('input');
        columnsInput.type = 'hidden';
        columnsInput.name = 'columns';
        columnsInput.value = visibleColumns.join(',');
        form.appendChild(columnsInput);
        
        // ارسال فرم
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
        
        // نمایش پیام موفقیت
        showSuccessMessage(`خروجی اکسل از ${selectedIds.length} خرید انتخاب شده در حال آماده‌سازی است...`);
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
        
        // Event listeners مربوط به انتخاب سطرها
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    selectAllRows();
                } else {
                    deselectAllRows();
                }
            });
        }
        
        if (selectAllRowsBtn) {
            selectAllRowsBtn.addEventListener('click', selectAllRows);
        }
        
        if (deselectAllRowsBtn) {
            deselectAllRowsBtn.addEventListener('click', deselectAllRows);
        }
        
        if (exportExcelBtn) {
            exportExcelBtn.addEventListener('click', exportSelectedPurchasesToExcel);
        }
        
        // Event listener برای تغییر checkbox های سطرها
        if (table) {
            table.addEventListener('change', function(e) {
                if (e.target.classList.contains('row-checkbox')) {
                    updateSelectAllCheckbox();
                }
            });
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
        
        // تنظیم وضعیت اولیه دکمه خروجی اکسل
        updateExportButtonState();
        
        // تنظیم ظاهر اولیه سطرها
        updateRowAppearance();
        
        console.log('مدیریت ستون‌های جدول خریدهای خارج از بازارگاه راه‌اندازی شد.');
    }
    
    // راه‌اندازی اولیه
    initialize();
    
    // اضافه کردن توابع به window برای دسترسی از خارج
    window.NonBazargahPurchaseColumns = {
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