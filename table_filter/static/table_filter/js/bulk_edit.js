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
        
        this.updateControlPanel();
    }

    handleSelectAll(checkbox) {
        const table = checkbox.closest('table');
        const rowCheckboxes = table.querySelectorAll('.row-checkbox');
        
        rowCheckboxes.forEach(rowCheckbox => {
            const rowId = rowCheckbox.getAttribute('data-id');
            
            if (checkbox.checked) {
                rowCheckbox.checked = true;
                this.selectedIds.add(rowId);
                rowCheckbox.closest('tr').classList.add(this.config.selectedClass);
            } else {
                rowCheckbox.checked = false;
                this.selectedIds.delete(rowId);
                rowCheckbox.closest('tr').classList.remove(this.config.selectedClass);
            }
        });
        
        this.updateControlPanel();
    }

    updateControlPanel() {
        const count = this.selectedIds.size;
        
        this.controlPanels.forEach(panel => {
            const countElement = panel.querySelector('.count');
            if (countElement) {
                countElement.textContent = count;
            }
            
            panel.style.display = count > 0 ? 'block' : 'none';
        });
    }

    clearSelection() {
        this.selectedIds.clear();
        
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.closest('tr').classList.remove(this.config.selectedClass);
        });
        
        document.querySelectorAll('.select-all-checkbox, .select-all-checkbox-archived').forEach(checkbox => {
            checkbox.checked = false;
        });
        
        this.updateControlPanel();
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
        if (this.selectedIds.size === 0) {
            this.showToast('لطفاً ابتدا موارد مورد نظر را انتخاب کنید', 'warning');
            return;
        }

        const tableType = this.detectTableType();
        const selectedIdsArray = Array.from(this.selectedIds);
        
        const params = new URLSearchParams({
            ids: selectedIdsArray.join(','),
            table_type: tableType,
            model: this.getModelName(tableType),
            app: this.getAppName(tableType)
        });

        window.open(`${this.config.bulkEditPageUrl}?${params.toString()}`, '_blank');
    }

    openExcelEditPage() {
        if (this.selectedIds.size === 0) {
            this.showToast('لطفاً ابتدا موارد مورد نظر را انتخاب کنید', 'warning');
            return;
        }

        const tableType = this.detectTableType();
        const selectedIdsArray = Array.from(this.selectedIds);
        
        const params = new URLSearchParams({
            ids: selectedIdsArray.join(','),
            table_type: tableType,
            model: this.getModelName(tableType),
            app: this.getAppName(tableType)
        });

        window.open(`${this.config.excelEditPageUrl}?${params.toString()}`, '_blank');
    }

    downloadExcelTemplate() {
        if (this.selectedIds.size === 0) {
            this.showToast('لطفاً ابتدا موارد مورد نظر را انتخاب کنید', 'warning');
            return;
        }

        const tableType = this.detectTableType();
        const selectedIdsArray = Array.from(this.selectedIds);
        
        const params = new URLSearchParams({
            table_type: tableType,
            selected_ids: selectedIdsArray.join(','),
            model: this.getModelName(tableType),
            app: this.getAppName(tableType)
        });

        // ایجاد لینک مخفی برای دانلود
        const downloadLink = document.createElement('a');
        downloadLink.href = `${this.config.downloadTemplateUrl}?${params.toString()}`;
        downloadLink.download = `bulk_edit_template_${tableType}.xlsx`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        
        this.showToast('دانلود قالب اکسل آغاز شد', 'success');
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
`;
document.head.appendChild(style);

// ایجاد instance global
window.bulkEditManager = new BulkEditManager();

// Export برای استفاده در سایر فایل‌ها
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BulkEditManager;
} 