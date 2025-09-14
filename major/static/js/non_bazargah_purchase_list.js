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
    
    // کلید ذخیره تنظیمات در localStorage
    const STORAGE_KEY = 'non_bazargah_purchase_columns';
    
    // تنظیمات پیش‌فرض ستون‌ها
    const DEFAULT_COLUMNS = [
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