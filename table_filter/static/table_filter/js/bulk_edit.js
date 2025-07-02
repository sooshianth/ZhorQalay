/**
 * مدیریت ویرایش گروهی جداول
 */
class BulkEditManager {
    constructor(config = {}) {
        this.selectedIds = new Set();
        this.currentSection = 'active'; // بخش فعلی
        this.config = {
            bulkEditPageUrl: '/table_filter/bulk-edit-page/',
            excelEditPageUrl: '/table_filter/bulk-edit-excel-page/',
            downloadTemplateUrl: '/table_filter/bulk-edit-template/',
            ...config
        };
        
        // نگهداری reference به control panelهای مختلف
        this.controlPanels = {
            active: document.querySelector('.bulk-edit-controls-active'),
            pending: document.querySelector('.bulk-edit-controls-pending'), 
            archived: document.querySelector('.bulk-edit-controls-archived')
        };
        
        // حذف control panelهای null
        Object.keys(this.controlPanels).forEach(key => {
            if (!this.controlPanels[key]) {
                delete this.controlPanels[key];
            }
        });
        
        this.currentActiveTab = this.detectActiveTab();
    }

    init() {
        this.attachEventListeners();
        this.detectCurrentSection();
        console.log('✅ BulkEditManager راه‌اندازی شد');
        
        // Debug: نمایش همه جداول موجود
        console.log('🔍 Debug: جداول موجود در صفحه:');
        document.querySelectorAll('table').forEach((table, index) => {
            console.log(`  ${index + 1}. Table ID: ${table.id}, Classes: ${table.className}`);
        });
        
        // Debug: نمایش همه checkbox های موجود
        console.log('🔍 Debug: checkbox های موجود:');
        document.querySelectorAll('input[type="checkbox"]').forEach((checkbox, index) => {
            console.log(`  ${index + 1}. Class: ${checkbox.className}, ID: ${checkbox.id}, Data-ID: ${checkbox.dataset.id}`);
        });
    }
    
    detectActiveTab() {
        // تشخیص تب فعال بر اساس نمایش عناصر
        if (document.getElementById('pendingContent') && 
            getComputedStyle(document.getElementById('pendingContent')).display !== 'none') {
            return 'pending';
        } else if (document.getElementById('archivedContent') && 
            getComputedStyle(document.getElementById('archivedContent')).display !== 'none') {
            return 'archived';
        } else {
            return 'active';
        }
    }
    
    detectCurrentSection() {
        const previousSection = this.currentSection;
        this.currentActiveTab = this.detectActiveTab();
        this.currentSection = this.currentActiveTab;
        
        console.log(`📍 تشخیص بخش: ${previousSection} → ${this.currentSection}`);
        
        // بررسی وجود جداول مورد نظر
        const tableSelectors = {
            active: '#activePurchasesTable',
            pending: '#pendingPurchasesTable', 
            archived: '#archivedPurchasesTable'
        };
        
        Object.keys(tableSelectors).forEach(section => {
            const table = document.querySelector(tableSelectors[section]);
            console.log(`  ${section}: ${table ? '✅ موجود' : '❌ نامعلوم'}`);
        });
    }

    attachEventListeners() {
        // گوش دادن به تغییرات انتخاب سطرها
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox')) {
                this.handleRowSelection(e.target);
            } else if (e.target.classList.contains('select-all-checkbox') || 
                      e.target.classList.contains('select-all-checkbox-archived') ||
                      e.target.classList.contains('select-all-checkbox-pending')) {
                this.handleSelectAll(e.target);
            }
        });

        document.addEventListener('click', (e) => {
            // دکمه‌های ویرایش گروهی
            if (e.target.classList.contains('bulk-edit-btn') || 
                e.target.closest('.bulk-edit-btn')) {
                const section = e.target.dataset.section || e.target.closest('.bulk-edit-btn').dataset.section;
                this.openBulkEditPage(section);
            } else if (e.target.classList.contains('bulk-edit-excel-btn') || 
                      e.target.closest('.bulk-edit-excel-btn')) {
                const section = e.target.dataset.section || e.target.closest('.bulk-edit-excel-btn').dataset.section;
                this.openExcelEditPage(section);
            } else if (e.target.classList.contains('download-template-btn') || 
                      e.target.closest('.download-template-btn')) {
                const section = e.target.dataset.section || e.target.closest('.download-template-btn').dataset.section;
                this.downloadTemplate(section);
            } else if (e.target.classList.contains('clear-selection-btn') || 
                      e.target.closest('.clear-selection-btn')) {
                const section = e.target.dataset.section || e.target.closest('.clear-selection-btn').dataset.section;
                this.clearSelection(section);
            }
            
            // دکمه‌های تب‌ها
            if (e.target.closest('.nav-link')) {
                setTimeout(() => {
                    this.detectCurrentSection();
                    this.updateAllControlPanels();
                }, 100);
            }
        });
        
        // گوش دادن به رویداد فیلتر جدول
        document.addEventListener('tableFilterApplied', (e) => {
            console.log('🔄 فیلتر جدول اعمال شد، بروزرسانی panel کنترل...');
            this.detectCurrentSection();
            this.updateAllControlPanels();
        });
    }

    handleRowSelection(checkbox) {
        const id = checkbox.dataset.id;
        
        if (checkbox.checked) {
            this.selectedIds.add(id);
            console.log(`✅ انتخاب سطر: ${id}`);
        } else {
            this.selectedIds.delete(id);
            console.log(`❌ حذف انتخاب سطر: ${id}`);
        }
        
        // همگام‌سازی با آمار تجمعی اگر موجود باشد
        if (window.purchaseAggregatedStats) {
            if (checkbox.checked) {
                window.purchaseAggregatedStats.selectedPurchases.add(id);
            } else {
                window.purchaseAggregatedStats.selectedPurchases.delete(id);
            }
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }
        
        this.updateAllControlPanels();
    }

    handleSelectAll(checkbox) {
        const isChecked = checkbox.checked;
        let checkboxes = [];
        
        // تشخیص نوع checkbox و یافتن checkboxهای مربوطه
        if (checkbox.classList.contains('select-all-checkbox-pending')) {
            checkboxes = document.querySelectorAll('#pendingPurchasesTable .row-checkbox');
        } else if (checkbox.classList.contains('select-all-checkbox-archived')) {
            checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
        } else {
            checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
        }
        
        checkboxes.forEach(cb => {
            cb.checked = isChecked;
            const id = cb.dataset.id;
            
            if (isChecked) {
                this.selectedIds.add(id);
            } else {
                this.selectedIds.delete(id);
            }
        });
        
        // همگام‌سازی با آمار تجمعی
        if (window.purchaseAggregatedStats) {
            if (isChecked) {
                checkboxes.forEach(cb => {
                    window.purchaseAggregatedStats.selectedPurchases.add(cb.dataset.id);
                });
            } else {
                checkboxes.forEach(cb => {
                    window.purchaseAggregatedStats.selectedPurchases.delete(cb.dataset.id);
                });
            }
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }
        
        this.updateAllControlPanels();
    }
    
    updateAllControlPanels() {
        // بروزرسانی همه control panelها
        Object.keys(this.controlPanels).forEach(section => {
            this.updateControlPanel(section);
        });
    }
    
    updateControlPanel(section = null) {
        const targetSection = section || this.currentSection;
        const panel = this.controlPanels[targetSection];
        
        if (!panel) return;
        
        // محاسبه تعداد انتخاب‌های مربوط به این بخش
        let sectionCount = 0;
        let tableSelector = '';
        
        switch(targetSection) {
            case 'pending':
                tableSelector = '#pendingPurchasesTable .row-checkbox:checked';
                break;
            case 'archived':
                tableSelector = '#archivedPurchasesTable .row-checkbox:checked';
                break;
            default:
                tableSelector = '#activePurchasesTable .row-checkbox:checked';
        }
        
        sectionCount = document.querySelectorAll(tableSelector).length;
        
        const countElement = panel.querySelector('.count');
        if (countElement) {
            countElement.textContent = sectionCount;
        }
        
        // نمایش/مخفی کردن panel بر اساس انتخاب‌ها و تب فعال
        const shouldShow = sectionCount > 0 && this.currentActiveTab === targetSection;
        panel.style.display = shouldShow ? 'block' : 'none';
        
        console.log(`📊 Panel ${targetSection}: ${sectionCount} انتخاب، نمایش: ${shouldShow}`);
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
        if (url.includes('cargo-product') || url.includes('cargo_product')) {
            return 'cargo_product';
        } else if (url.includes('purchase')) {
            return 'purchase';
        } else if (url.includes('customer')) {
            return 'customer';
        }
        return 'purchase'; // پیش‌فرض
    }

    openBulkEditPage(section = null) {
        const targetSection = section || this.currentSection;
        let selectedIds = [];
        
        console.log(`🎯 درخواست ویرایش گروهی برای بخش: ${targetSection}`);
        
        // جمع‌آوری آیدی‌های انتخاب شده برای بخش مشخص
        const tableMap = {
            pending: '#pendingPurchasesTable .row-checkbox:checked',
            archived: '#archivedPurchasesTable .row-checkbox:checked',
            active: '#activePurchasesTable .row-checkbox:checked'
        };
        
        const selector = tableMap[targetSection];
        console.log(`🔍 انتخاب checkboxها با selector: ${selector}`);
        
        const checkboxes = document.querySelectorAll(selector);
        console.log(`📋 تعداد checkbox های انتخاب شده: ${checkboxes.length}`);
        
        selectedIds = Array.from(checkboxes).map(cb => {
            console.log(`  - ID: ${cb.dataset.id}, Value: ${cb.value}`);
            return cb.dataset.id || cb.value;
        });
        
        console.log(`✅ آیدی‌های جمع‌آوری شده:`, selectedIds);
        
        if (selectedIds.length === 0) {
            console.error('❌ هیچ موردی انتخاب نشده');
            alert('لطفاً حداقل یک مورد انتخاب کنید');
            return;
        }

        const tableType = this.detectTableType();
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = this.config.bulkEditPageUrl;

        const data = {
            'selected_ids': selectedIds,
            'app_name': this.getAppName(tableType),
            'model_name': this.getModelName(tableType),
            'section': targetSection
        };

        Object.keys(data).forEach(key => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            if (Array.isArray(data[key])) {
                input.value = JSON.stringify(data[key]);
            } else {
                input.value = data[key];
            }
            form.appendChild(input);
        });

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCSRFToken();
        form.appendChild(csrfInput);

        document.body.appendChild(form);
        form.submit();
    }

    openExcelEditPage(section = null) {
        const targetSection = section || this.currentSection;
        let selectedIds = [];
        
        console.log(`📊 درخواست ویرایش اکسلی برای بخش: ${targetSection}`);
        
        // جمع‌آوری آیدی‌های انتخاب شده برای بخش مشخص
        const tableMap = {
            pending: '#pendingPurchasesTable .row-checkbox:checked',
            archived: '#archivedPurchasesTable .row-checkbox:checked',
            active: '#activePurchasesTable .row-checkbox:checked'
        };
        
        const selector = tableMap[targetSection];
        console.log(`🔍 انتخاب checkboxها با selector: ${selector}`);
        
        const checkboxes = document.querySelectorAll(selector);
        console.log(`📋 تعداد checkbox های انتخاب شده: ${checkboxes.length}`);
        
        selectedIds = Array.from(checkboxes).map(cb => {
            console.log(`  - ID: ${cb.dataset.id}, Value: ${cb.value}`);
            return cb.dataset.id || cb.value;
        });
        
        console.log(`✅ آیدی‌های جمع‌آوری شده:`, selectedIds);
        
        if (selectedIds.length === 0) {
            console.error('❌ هیچ موردی انتخاب نشده');
            alert('لطفاً حداقل یک مورد انتخاب کنید');
            return;
        }
        
        const tableType = this.detectTableType();
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = this.config.excelEditPageUrl;

        const data = {
            'selected_ids': selectedIds,
            'app_name': this.getAppName(tableType),
            'model_name': this.getModelName(tableType),
            'section': targetSection
        };

        Object.keys(data).forEach(key => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            if (Array.isArray(data[key])) {
                input.value = JSON.stringify(data[key]);
            } else {
                input.value = data[key];
            }
            form.appendChild(input);
        });

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCSRFToken();
        form.appendChild(csrfInput);
        
        document.body.appendChild(form);
        form.submit();
    }

    downloadTemplate(section = null) {
        const tableType = this.detectTableType();
        const url = `${this.config.downloadTemplateUrl}?app_name=${this.getAppName(tableType)}&model_name=${this.getModelName(tableType)}`;
        
        window.open(url, '_blank');
    }

    getModelName(tableType) {
        const modelMap = {
            'purchase': 'Purchase',
            'customer': 'Customer',
            'cargo_product': 'CargoProduct'
        };
        return modelMap[tableType] || 'Purchase';
    }
    
    getAppName(tableType) {
        return 'core';
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
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

    clearSelection(section = null) {
        const targetSection = section || this.currentSection;
        let checkboxes = [];
        
        // یافتن checkboxهای مربوط به بخش
        switch(targetSection) {
            case 'pending':
                checkboxes = document.querySelectorAll('#pendingPurchasesTable .row-checkbox');
                break;
            case 'archived':
                checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
                break;
            default:
                checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
        }
        
        // پاک کردن انتخاب‌ها
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            const id = checkbox.dataset.id;
            this.selectedIds.delete(id);
        });
        
        // پاک کردن select all checkbox
        const selectAllMap = {
            pending: '.select-all-checkbox-pending',
            archived: '.select-all-checkbox-archived',
            active: '.select-all-checkbox'
        };
        
        const selectAllCheckbox = document.querySelector(selectAllMap[targetSection]);
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        // همگام‌سازی با آمار تجمعی
        if (window.purchaseAggregatedStats) {
            checkboxes.forEach(checkbox => {
                window.purchaseAggregatedStats.selectedPurchases.delete(checkbox.dataset.id);
            });
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }
        
        this.updateAllControlPanels();
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