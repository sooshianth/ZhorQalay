/**
 * مدیریت ویرایش گروهی جداول
 */
class BulkEditManager {
    constructor(config = {}) {
        this.config = {
            tableSelector: '.enable-filter',
            controlPanelClass: 'bulk-edit-controls',
            selectedClass: 'bulk-selected',
            bulkEditPageUrl: '/table_filter/bulk-edit-page/',
            excelEditPageUrl: '/table_filter/bulk-edit-excel-page/',
            downloadTemplateUrl: '/table_filter/bulk-edit-template/',
            ...config
        };
        
        this.selectedIds = new Set();
        this.tables = [];
        this.controlPanels = [];
        // اضافه کردن state برای تشخیص نوع انتخاب
        this.selectionType = 'partial'; // 'partial', 'all-visible', 'all-data'
    }

    init() {
        this.findTables();
        this.createBulkEditControls();
        this.attachEventListeners();
    }

    findTables() {
        this.tables = document.querySelectorAll(this.config.tableSelector);
        console.log('پیدا شده جداول:', this.tables.length);
    }

    createBulkEditControls() {
        this.tables.forEach(table => {
            const controlPanel = this.createControlPanel(table);
            if (controlPanel) {
                this.controlPanels.push(controlPanel);
                table.parentNode.insertBefore(controlPanel, table);
            }
        });
    }

    createControlPanel(table) {
        const existingPanel = table.parentNode.querySelector('.bulk-edit-controls');
        if (existingPanel) {
            return existingPanel;
        }

        const panel = document.createElement('div');
        panel.className = 'bulk-edit-controls';
        panel.style.display = 'none';
        panel.innerHTML = `
            <div class="bulk-edit-toolbar">
                <div class="selected-count">
                    <i class="fas fa-check-square"></i>
                    <span class="count">0</span> مورد انتخاب شده
                    <span class="selection-type"></span>
                </div>
                <div class="bulk-edit-actions">
                    <button class="btn btn-primary bulk-edit-btn" data-action="edit">
                        <i class="fas fa-edit"></i> ویرایش گروهی
                    </button>
                    <button class="btn btn-success bulk-edit-excel-btn" data-action="excel">
                        <i class="fas fa-file-excel"></i> ویرایش با اکسل
                    </button>
                    <button class="btn btn-info download-template-btn" data-action="template">
                        <i class="fas fa-download"></i> دانلود قالب اکسل
                    </button>
                    <button class="btn btn-secondary clear-selection-btn" data-action="clear">
                        <i class="fas fa-times"></i> لغو انتخاب
                    </button>
                </div>
            </div>
        `;

        return panel;
    }

    attachEventListeners() {
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox')) {
                this.handleRowSelection(e.target);
            } else if (e.target.classList.contains('select-all-checkbox') || 
                      e.target.classList.contains('select-all-checkbox-archived')) {
                this.handleSelectAll(e.target);
            }
        });

        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('bulk-edit-btn') || 
                e.target.closest('.bulk-edit-btn')) {
                this.openBulkEditPage();
            } else if (e.target.classList.contains('bulk-edit-excel-btn') || 
                      e.target.closest('.bulk-edit-excel-btn')) {
                this.openExcelEditPage();
            } else if (e.target.classList.contains('download-template-btn') || 
                      e.target.closest('.download-template-btn')) {
                this.downloadExcelTemplate();
            } else if (e.target.classList.contains('clear-selection-btn') || 
                      e.target.closest('.clear-selection-btn')) {
                this.clearSelection();
            }
        });

        // اضافه کردن listener برای تغییرات فیلتر
        document.addEventListener('tableFilterApplied', () => {
            this.updateSelectionAfterFilter();
        });
    }

    handleRowSelection(checkbox) {
        const rowId = checkbox.getAttribute('data-id');
        
        if (checkbox.checked) {
            this.selectedIds.add(rowId);
            checkbox.closest('tr').classList.add(this.config.selectedClass);
        } else {
            this.selectedIds.delete(rowId);
            checkbox.closest('tr').classList.remove(this.config.selectedClass);
        }
        
        // تعیین نوع انتخاب
        this.determineSelectionType();
        this.updateControlPanel();
    }

    handleSelectAll(checkbox) {
        const table = checkbox.closest('table');
        const rowCheckboxes = table.querySelectorAll('.row-checkbox');
        
        if (checkbox.checked) {
            // بررسی وضعیت فیلتر
            const hasActiveFilters = this.hasActiveFilters();
            
            if (hasActiveFilters) {
                // نمایش پیام انتخاب و گزینه‌ها
                this.showSelectAllOptions(table, checkbox);
                return;
            } else {
                // انتخاب همه (بدون فیلتر)
                this.selectAllRows(table, 'all-data');
            }
        } else {
            // لغو انتخاب همه
            this.deselectAllRows(table);
        }
        
        this.updateControlPanel();
    }

    showSelectAllOptions(table, checkbox) {
        // ایجاد مدال یا dropdown برای انتخاب نوع
        const modal = document.createElement('div');
        modal.className = 'select-all-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 9999;
            display: flex;
            justify-content: center;
            align-items: center;
        `;

        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            max-width: 400px;
            text-align: center;
        `;

        modalContent.innerHTML = `
            <h5 style="margin-bottom: 15px;">انتخاب همه موارد</h5>
            <p style="margin-bottom: 20px;">میخواهید کدام موارد را انتخاب کنید؟</p>
            <div style="display: flex; gap: 10px; justify-content: center;">
                <button class="btn btn-primary select-visible-btn">
                    فقط موارد نمایش داده شده (${this.getVisibleRowsCount(table)})
                </button>
                <button class="btn btn-success select-all-data-btn">
                    همه موارد (${this.getAllRowsCount(table)})
                </button>
                <button class="btn btn-secondary cancel-btn">
                    انصراف
                </button>
            </div>
        `;

        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // Event listeners برای دکمه‌ها
        modalContent.querySelector('.select-visible-btn').addEventListener('click', () => {
            this.selectAllRows(table, 'all-visible');
            document.body.removeChild(modal);
            this.updateControlPanel();
        });

        modalContent.querySelector('.select-all-data-btn').addEventListener('click', () => {
            this.selectAllRows(table, 'all-data');
            document.body.removeChild(modal);
            this.updateControlPanel();
        });

        modalContent.querySelector('.cancel-btn').addEventListener('click', () => {
            checkbox.checked = false;
            document.body.removeChild(modal);
        });

        // بستن با کلیک روی backdrop
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                checkbox.checked = false;
                document.body.removeChild(modal);
            }
        });
    }

    selectAllRows(table, type) {
        let rowCheckboxes;
        
        if (type === 'all-visible') {
            // فقط ردیف‌های نمایش داده شده
            rowCheckboxes = table.querySelectorAll('tbody tr:not([style*="display: none"]) .row-checkbox');
            this.selectionType = 'all-visible';
        } else if (type === 'all-data') {
            // همه ردیف‌ها (حتی فیلتر شده‌ها)
            rowCheckboxes = table.querySelectorAll('.row-checkbox');
            this.selectionType = 'all-data';
        }

        rowCheckboxes.forEach(rowCheckbox => {
            const rowId = rowCheckbox.getAttribute('data-id');
            rowCheckbox.checked = true;
            this.selectedIds.add(rowId);
            rowCheckbox.closest('tr').classList.add(this.config.selectedClass);
        });

        // تنظیم checkbox انتخاب همه
        const selectAllCheckbox = table.querySelector('.select-all-checkbox, .select-all-checkbox-archived');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = true;
        }
    }

    deselectAllRows(table) {
        const rowCheckboxes = table.querySelectorAll('.row-checkbox');
        
        rowCheckboxes.forEach(rowCheckbox => {
            const rowId = rowCheckbox.getAttribute('data-id');
            rowCheckbox.checked = false;
            this.selectedIds.delete(rowId);
            rowCheckbox.closest('tr').classList.remove(this.config.selectedClass);
        });

        this.selectionType = 'partial';
    }

    determineSelectionType() {
        // تعیین نوع انتخاب بر اساس موارد انتخاب شده
        const allRowsCount = this.getAllRowsCount();
        const visibleRowsCount = this.getVisibleRowsCount();
        const selectedCount = this.selectedIds.size;

        if (selectedCount === 0) {
            this.selectionType = 'partial';
        } else if (selectedCount === allRowsCount) {
            this.selectionType = 'all-data';
        } else if (selectedCount === visibleRowsCount && this.hasActiveFilters()) {
            this.selectionType = 'all-visible';
        } else {
            this.selectionType = 'partial';
        }
    }

    updateSelectionAfterFilter() {
        // بعد از اعمال فیلتر، بررسی کنیم که آیا انتخاب‌ها هنوز معتبر هستند
        if (this.selectionType === 'all-visible') {
            // اگر قبلاً همه موارد نمایش داده شده انتخاب شده بودند،
            // باید موارد جدید نمایش داده شده را هم انتخاب کنیم
            this.tables.forEach(table => {
                const visibleCheckboxes = table.querySelectorAll('tbody tr:not([style*="display: none"]) .row-checkbox');
                visibleCheckboxes.forEach(checkbox => {
                    const rowId = checkbox.getAttribute('data-id');
                    checkbox.checked = true;
                    this.selectedIds.add(rowId);
                    checkbox.closest('tr').classList.add(this.config.selectedClass);
                });
            });
        }
        
        this.updateControlPanel();
    }

    updateControlPanel() {
        // استفاده از selectedPurchases اگر موجود باشد، در غیر این صورت selectedIds
        let count = this.selectedIds.size;
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases) {
            count = window.purchaseAggregatedStats.selectedPurchases.size;
            // همگام‌سازی selectedIds با selectedPurchases
            this.selectedIds = new Set(window.purchaseAggregatedStats.selectedPurchases);
        }
        
        this.controlPanels.forEach(panel => {
            const countElement = panel.querySelector('.count');
            const selectionTypeElement = panel.querySelector('.selection-type');
            
            if (countElement) {
                countElement.textContent = count;
            }
            
            if (selectionTypeElement) {
                let typeText = '';
                if (this.selectionType === 'all-data') {
                    typeText = '(همه موارد)';
                } else if (this.selectionType === 'all-visible') {
                    typeText = '(موارد نمایش داده شده)';
                }
                selectionTypeElement.textContent = typeText;
            }
            
            panel.style.display = count > 0 ? 'block' : 'none';
        });
        
        // همگام‌سازی با آمار اجماعی خریدها
        this.syncWithAggregatedStats();
    }

    // متد جدید: همگام‌سازی با آمار اجماعی
    syncWithAggregatedStats() {
        if (window.purchaseAggregatedStats) {
            // به‌روزرسانی لیست انتخاب‌ها در آمار اجماعی
            window.purchaseAggregatedStats.selectedPurchases = new Set(this.selectedIds);
            window.purchaseAggregatedStats.updateStats();
        }
    }

    clearSelection() {
        this.selectedIds.clear();
        this.selectionType = 'partial';
        
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.closest('tr').classList.remove(this.config.selectedClass);
        });
        
        document.querySelectorAll('.select-all-checkbox, .select-all-checkbox-archived').forEach(checkbox => {
            checkbox.checked = false;
        });
        
        this.updateControlPanel();
        
        // همگام‌سازی با آمار اجماعی خریدها
        if (window.purchaseAggregatedStats) {
            window.purchaseAggregatedStats.clearAllSelections();
        }
    }

    // متدهای کمکی
    hasActiveFilters() {
        // بررسی وجود فیلتر فعال
        return document.querySelector('.active-filters-summary.show') !== null ||
               document.querySelector('.filter-dropdown-btn.has-filters') !== null;
    }

    getVisibleRowsCount(table = null) {
        if (table) {
            return table.querySelectorAll('tbody tr:not([style*="display: none"])').length;
        }
        
        let count = 0;
        this.tables.forEach(table => {
            count += table.querySelectorAll('tbody tr:not([style*="display: none"])').length;
        });
        return count;
    }

    getAllRowsCount(table = null) {
        if (table) {
            return table.querySelectorAll('tbody tr').length;
        }
        
        let count = 0;
        this.tables.forEach(table => {
            count += table.querySelectorAll('tbody tr').length;
        });
        return count;
    }

    detectTableType() {
        const url = window.location.pathname;
        if (url.includes('purchase')) {
            return 'purchase';
        } else if (url.includes('customer')) {
            return 'customer';
        } else if (url.includes('barbary')) {
            return 'barbary';
        } else if (url.includes('vared_konandeh')) {
            return 'vared_konandeh';
        } else if (url.includes('cargo_product') || url.includes('cargo-product')) {
            return 'cargo_product';
        }
        return 'generic';
    }

    openBulkEditPage() {
        // استفاده از selectedPurchases اگر موجود باشد
        let selectedIdsArray = Array.from(this.selectedIds);
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases) {
            selectedIdsArray = Array.from(window.purchaseAggregatedStats.selectedPurchases);
        }
        
        if (selectedIdsArray.length === 0) {
            this.showToast('لطفاً ابتدا موارد مورد نظر را انتخاب کنید', 'warning');
            return;
        }

        const tableType = this.detectTableType();
        
        const params = new URLSearchParams({
            ids: selectedIdsArray.join(','),
            table_type: tableType,
            model: this.getModelName(tableType),
            app: this.getAppName(tableType),
            selection_type: this.selectionType
        });

        window.open(`${this.config.bulkEditPageUrl}?${params.toString()}`, '_blank');
    }

    openExcelEditPage() {
        // استفاده از selectedPurchases اگر موجود باشد
        let selectedIds = [];
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases) {
            selectedIds = Array.from(window.purchaseAggregatedStats.selectedPurchases);
        } else {
            const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
            selectedIds = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-id')).filter(id => id);
        }
        
        if (selectedIds.length === 0) {
            this.showToast('لطفاً حداقل یک مورد را انتخاب کنید', 'warning');
            return;
        }
        
        console.log('Selected IDs for Excel edit:', selectedIds);
        
        // تشخیص نوع مدل
        const tableType = this.detectTableType();
        const modelName = this.getModelName(tableType);
        const appName = this.getAppName(tableType);
        
        console.log('Model info:', { tableType, modelName, appName });
        
        // ایجاد فرم برای ارسال داده‌ها
        const form = document.createElement('form');
        form.method = 'GET';
        form.action = this.config.excelEditPageUrl;
        form.style.display = 'none';
        
        // اضافه کردن پارامترها
        const params = [
            { name: 'selected_ids', value: selectedIds.join(' ') },
            { name: 'model', value: modelName },
            { name: 'app', value: appName },
            { name: 'table_type', value: tableType }
        ];
        
        params.forEach(param => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = param.name;
            input.value = param.value;
            form.appendChild(input);
            console.log(`Added param: ${param.name} = ${param.value}`);
        });
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    }

    downloadExcelTemplate() {
        // استفاده از selectedPurchases اگر موجود باشد
        let selectedIds = [];
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases) {
            selectedIds = Array.from(window.purchaseAggregatedStats.selectedPurchases);
        } else {
            const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
            selectedIds = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-id')).filter(id => id);
        }
        
        if (selectedIds.length === 0) {
            this.showToast('لطفاً حداقل یک مورد را انتخاب کنید', 'warning');
            return;
        }
        
        console.log('Selected IDs for template download:', selectedIds);
        
        // تشخیص نوع مدل
        const tableType = this.detectTableType();
        const modelName = this.getModelName(tableType);
        const appName = this.getAppName(tableType);
        
        console.log('Template model info:', { tableType, modelName, appName });
        
        // ساخت URL برای دانلود قالب
        const params = new URLSearchParams({
            selected_ids: selectedIds.join(' '),
            table_type: tableType,
            model: modelName,
            app: appName
        });
        
        const downloadUrl = `${this.config.downloadTemplateUrl}?${params.toString()}`;
        console.log('Template download URL:', downloadUrl);
        
        // باز کردن در تب جدید برای دانلود
        window.open(downloadUrl, '_blank');
        
        // نمایش پیام موفقیت
        this.showToast(`در حال دانلود قالب اکسل برای ${selectedIds.length} مورد انتخاب شده...`, 'success');
    }

    getModelName(tableType) {
        const modelMap = {
            'purchase': 'Purchase',
            'customer': 'Customer',
            'barbary': 'Barbary',
            'vared_konandeh': 'VaredKonandeh',
            'cargo_product': 'CargoProduct'
        };
        return modelMap[tableType] || 'Unknown';
    }
    
    getAppName(tableType) {
        return 'core';
    }

    showToast(message, type = 'info') {
        // ایجاد toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast-notification`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideIn 0.3s ease-out;
        `;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : type === 'warning' ? 'exclamation' : 'info'}-circle me-2"></i>
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;

        document.body.appendChild(toast);

        // حذف خودکار بعد از 5 ثانیه
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }
}

// استایل برای انیمیشن toast
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .toast-notification {
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 0.375rem;
    }
    
    .toast-notification .btn-close {
        background: transparent;
        border: none;
        font-size: 1.2rem;
        margin-left: 10px;
        cursor: pointer;
    }
    
    .select-all-modal .btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s;
    }
    
    .select-all-modal .btn-primary {
        background: #007bff;
        color: white;
    }
    
    .select-all-modal .btn-success {
        background: #28a745;
        color: white;
    }
    
    .select-all-modal .btn-secondary {
        background: #6c757d;
        color: white;
    }
    
    .select-all-modal .btn:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
`;
document.head.appendChild(style);

// ایجاد instance global
window.bulkEditManager = new BulkEditManager();

// Export برای استفاده در سایر فایل‌ها
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BulkEditManager;
} 