/**
 * مدیریت آمار اجماعی خریدهای انتخاب شده
 * Purchase Aggregated Statistics Manager
 */

class PurchaseAggregatedStats {
    constructor() {
        this.selectedPurchases = new Set();
        this.statsContainer = document.getElementById('aggregatedStats');
        this.selectedRowsCountElement = document.getElementById('selectedRowsCount');
        this.closeButton = document.getElementById('closeAggregatedStats');
        
        // عناصر نمایش آمار
        this.totalOrderWeightElement = document.getElementById('totalOrderWeight');
        this.totalDeliveredWeightElement = document.getElementById('totalDeliveredWeight');
        this.avgCompanyPriceElement = document.getElementById('avgCompanyPrice');
        this.avgCustomerPriceElement = document.getElementById('avgCustomerPrice');
        this.totalAmountPaidElement = document.getElementById('totalAmountPaid');
        this.purchaseBaseInvoiceElement = document.getElementById('purchaseBaseInvoice');
        this.salesBaseInvoiceElement = document.getElementById('salesBaseInvoice');
        this.profitElement = document.getElementById('profit');
        
        this.init();
    }
    
    init() {
        // گوش دادن به تغییرات انتخاب سطرها
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox')) {
                this.handleRowSelection(e.target);
            } else if (e.target.classList.contains('select-all-checkbox')) {
                this.handleSelectAll(e.target);
            } else if (e.target.classList.contains('select-all-checkbox-archived')) {
                this.handleSelectAllArchived(e.target);
            } else if (e.target.classList.contains('select-all-checkbox-pending')) {
                this.handleSelectAllPending(e.target);
            }
        });
        
        // دکمه بستن آمار
        if (this.closeButton) {
            this.closeButton.addEventListener('click', () => {
                this.hideStats();
                this.clearAllSelections();
            });
        }
        
        // گوش دادن به کلیک‌های bulk edit برای sync کردن انتخاب‌ها
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('clear-selection-btn')) {
                this.clearAllSelections();
            }
        });

        // دکمه‌های انتخاب کلی جدید
        this.initGlobalSelectionButtons();
        
        // راه‌اندازی دکمه‌های dropdown انتخاب
        this.initDropdownSelectionButtons();
        
        // گوش دادن به تغییرات فیلتر
        document.addEventListener('tableFilterApplied', () => {
            this.updateStatsAfterFilter();
        });
        
        document.addEventListener('tableFilterCleared', () => {
            this.updateStatsAfterFilter();
        });
        
        document.addEventListener('tableFiltersCleared', () => {
            this.updateStatsAfterFilter();
        });
    }

    initGlobalSelectionButtons() {
        // دکمه لغو همه انتخاب‌ها
        const clearAllBtn = document.getElementById('clearAllSelections');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.clearAllSelections();
            });
        }
    }

    initDropdownSelectionButtons() {
        // راه‌اندازی دکمه‌های dropdown برای انتخاب صفحه و بخش
        
        // انتخاب همه در صفحه (active)
        const selectPageActive = document.querySelector('.select-page-active');
        if (selectPageActive) {
            selectPageActive.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectCurrentPageSection('active');
            });
        }
        
        // انتخاب همه در بخش (active)
        const selectSectionActive = document.querySelector('.select-section-active');
        if (selectSectionActive) {
            selectSectionActive.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectAllInSection('active');
            });
        }
        
        // پاک کردن انتخاب‌ها (active)
        const clearSelectionActive = document.querySelector('.clear-selection-active');
        if (clearSelectionActive) {
            clearSelectionActive.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearSectionSelection('active');
            });
        }
        
        // انتخاب همه در صفحه (pending)
        const selectPagePending = document.querySelector('.select-page-pending');
        if (selectPagePending) {
            selectPagePending.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectCurrentPageSection('pending');
            });
        }
        
        // انتخاب همه در بخش (pending)
        const selectSectionPending = document.querySelector('.select-section-pending');
        if (selectSectionPending) {
            selectSectionPending.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectAllInSection('pending');
            });
        }
        
        // پاک کردن انتخاب‌ها (pending)
        const clearSelectionPending = document.querySelector('.clear-selection-pending');
        if (clearSelectionPending) {
            clearSelectionPending.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearSectionSelection('pending');
            });
        }
        
        // انتخاب همه در صفحه (archived)
        const selectPageArchived = document.querySelector('.select-page-archived');
        if (selectPageArchived) {
            selectPageArchived.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectCurrentPageSection('archived');
            });
        }
        
        // انتخاب همه در بخش (archived)
        const selectSectionArchived = document.querySelector('.select-section-archived');
        if (selectSectionArchived) {
            selectSectionArchived.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectAllInSection('archived');
            });
        }
        
        // پاک کردن انتخاب‌ها (archived)
        const clearSelectionArchived = document.querySelector('.clear-selection-archived');
        if (clearSelectionArchived) {
            clearSelectionArchived.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearSectionSelection('archived');
            });
        }
    }

    selectCurrentPageSection(section) {
        // انتخاب فقط خریدهای نمایش داده شده در صفحه فعلی یک بخش خاص
        // ابتدا تمام انتخاب‌های قبلی را بدون پیام پاک می‌کنیم
        this.clearAllSelectionsSilent();
        
        const tableMap = {
            'active': 'activePurchasesTable',
            'pending': 'pendingPurchasesTable', 
            'archived': 'archivedPurchasesTable'
        };
        
        const tableId = tableMap[section];
        if (!tableId) return;
        
        const checkboxes = document.querySelectorAll(`#${tableId} tbody tr:not([style*="display: none"]) .row-checkbox`);
        let selectedCount = 0;
        
        checkboxes.forEach(checkbox => {
            const purchaseId = checkbox.getAttribute('data-id');
            this.selectedPurchases.add(purchaseId);
            checkbox.checked = true;
            selectedCount++;
            
            // بروزرسانی رنگ سطر
            const row = checkbox.closest('tr');
            if (row) {
                row.classList.add('table-warning', 'selected-row');
            }
        });

        // بروزرسانی چک‌باکس سرستون
        this.updateSelectAllCheckboxes();
        this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
        
        // نمایش پیام
        this.showSuccessMessage(`${selectedCount} خرید از صفحه فعلی بخش ${this.getSectionTitle(section)} انتخاب شد`);
    }

    selectAllInSection(section) {
        // انتخاب تمام خریدهای یک بخش (تمام صفحات)
        // ابتدا تمام انتخاب‌های قبلی را بدون پیام پاک می‌کنیم
        this.clearAllSelectionsSilent();
        
        const btn = document.querySelector(`.select-section-${section}`);
        const originalText = btn ? btn.innerHTML : '';
        
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>در حال انتخاب...';
            btn.style.pointerEvents = 'none';
        }

        // ساخت URL با فیلترهای فعلی و Table Filter
        const currentUrl = new URL(window.location);
        const params = new URLSearchParams(currentUrl.search);
        params.set('section', section);
        
        // اضافه کردن فیلترهای Table Filter
        if (window.tableFilter && typeof window.tableFilter.getActiveFilters === 'function') {
            const tableFilters = window.tableFilter.getActiveFilters();
            Object.keys(tableFilters).forEach(key => {
                if (tableFilters[key] && tableFilters[key].length > 0) {
                    params.set(key, tableFilters[key].join(','));
                }
            });
        }
        
        fetch(`/erp/purchases/section-ids/?${params.toString()}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // انتخاب تمام خریدهای بخش
                data.purchase_ids.forEach(id => {
                    this.selectedPurchases.add(id.toString());
                });

                // بروزرسانی چک‌باکس‌های نمایش داده شده
                document.querySelectorAll('.row-checkbox').forEach(checkbox => {
                    const purchaseId = checkbox.getAttribute('data-id');
                    if (this.selectedPurchases.has(purchaseId)) {
                        checkbox.checked = true;
                        
                        // بروزرسانی رنگ سطر
                        const row = checkbox.closest('tr');
                        if (row) {
                            row.classList.add('table-warning', 'selected-row');
                        }
                    }
                });

                // بروزرسانی وضعیت‌ها
                this.updateSelectAllCheckboxes();
                this.updateStats();
                this.updateGlobalSelectionCount();

                // بروزرسانی دکمه‌های bulk edit و export
                if (window.updateExportButton) {
                    window.updateExportButton();
                }
                
                // بروزرسانی bulk edit manager اگر موجود باشد
                if (window.bulkEditManager) {
                    window.bulkEditManager.updateControlPanel();
                }

                // نمایش پیام موفقیت
                this.showSuccessMessage(`${data.count} خرید از تمام صفحات بخش ${this.getSectionTitle(section)} انتخاب شد`);
            } else {
                console.error('خطا در دریافت لیست خریدها:', data.message);
                this.showErrorMessage('خطا در انتخاب کل بخش');
            }
        })
        .catch(error => {
            console.error('خطا در ارتباط با سرور:', error);
            this.showErrorMessage('خطا در ارتباط با سرور');
        })
        .finally(() => {
            // بازگردانی وضعیت دکمه
            if (btn) {
                btn.innerHTML = originalText;
                btn.style.pointerEvents = 'auto';
            }
        });
    }

    clearSectionSelection(section) {
        // پاک کردن انتخاب‌های یک بخش خاص
        const tableMap = {
            'active': 'activePurchasesTable',
            'pending': 'pendingPurchasesTable', 
            'archived': 'archivedPurchasesTable'
        };
        
        const tableId = tableMap[section];
        if (!tableId) return;
        
        const checkboxes = document.querySelectorAll(`#${tableId} .row-checkbox`);
        let clearedCount = 0;
        
        checkboxes.forEach(checkbox => {
            const purchaseId = checkbox.getAttribute('data-id');
            if (this.selectedPurchases.has(purchaseId)) {
                this.selectedPurchases.delete(purchaseId);
                checkbox.checked = false;
                clearedCount++;
                
                // حذف رنگ سطر
                const row = checkbox.closest('tr');
                if (row) {
                    row.classList.remove('table-warning', 'selected-row');
                }
            }
        });

        // بروزرسانی چک‌باکس سرستون
        this.updateSelectAllCheckboxes();
        this.updateStats();
        this.updateGlobalSelectionCount();
        
        // نمایش پیام
        if (clearedCount > 0) {
            this.showSuccessMessage(`${clearedCount} خرید از بخش ${this.getSectionTitle(section)} انتخاب لغو شد`);
        }
    }

    getSectionTitle(section) {
        const titles = {
            'active': 'خریدهای فعال',
            'pending': 'در انتظار پرداخت',
            'archived': 'آرشیو شده'
        };
        return titles[section] || section;
    }



    updateSelectAllCheckboxes() {
        // بروزرسانی وضعیت چک‌باکس‌های سرستون
        const tables = ['activePurchasesTable', 'pendingPurchasesTable', 'archivedPurchasesTable'];
        
        tables.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;

            const allCheckboxes = table.querySelectorAll('tbody .row-checkbox');
            const checkedCheckboxes = table.querySelectorAll('tbody .row-checkbox:checked');
            const selectAllCheckbox = table.querySelector('thead .select-all-checkbox, thead .select-all-checkbox-pending, thead .select-all-checkbox-archived');

            if (selectAllCheckbox) {
                if (allCheckboxes.length === checkedCheckboxes.length && allCheckboxes.length > 0) {
                    selectAllCheckbox.checked = true;
                    selectAllCheckbox.indeterminate = false;
                } else if (checkedCheckboxes.length > 0) {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = true;
                } else {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = false;
                }
            }
        });
    }

    updateGlobalSelectionCount() {
        const countElement = document.getElementById('globalSelectionCount');
        const infoElement = document.getElementById('globalSelectionInfo');
        
        if (countElement) {
            countElement.textContent = this.selectedPurchases.size;
        }
        
        // نمایش یا مخفی کردن شمارنده بر اساس تعداد انتخاب‌ها
        if (infoElement) {
            if (this.selectedPurchases.size > 0) {
                infoElement.style.display = 'block';
            } else {
                infoElement.style.display = 'none';
            }
        }
    }

    showSuccessMessage(message) {
        // نمایش پیام موفقیت
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);

        // حذف خودکار بعد از 3 ثانیه
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 3000);
    }

    showErrorMessage(message) {
        // نمایش پیام خطا
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-circle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);

        // حذف خودکار بعد از 5 ثانیه
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }
    
    handleRowSelection(checkbox) {
        const purchaseId = checkbox.getAttribute('data-id');
        
        if (checkbox.checked) {
            this.selectedPurchases.add(purchaseId);
        } else {
            this.selectedPurchases.delete(purchaseId);
        }
        
        this.updateSelectAllCheckboxes();
        this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }
    
    handleSelectAll(selectAllCheckbox) {
        const tableId = 'activePurchasesTable';
        const checkboxes = document.querySelectorAll(`#${tableId} tbody tr:not([style*="display: none"]) .row-checkbox`);
        
        checkboxes.forEach(checkbox => {
            const purchaseId = checkbox.getAttribute('data-id');
            if (selectAllCheckbox.checked) {
                this.selectedPurchases.add(purchaseId);
                checkbox.checked = true;
            } else {
                this.selectedPurchases.delete(purchaseId);
                checkbox.checked = false;
            }
        });
        
                this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }

    handleSelectAllArchived(selectAllCheckbox) {
        const tableId = 'archivedPurchasesTable';
        const checkboxes = document.querySelectorAll(`#${tableId} tbody tr:not([style*="display: none"]) .row-checkbox`);
        
        checkboxes.forEach(checkbox => {
            const purchaseId = checkbox.getAttribute('data-id');
            if (selectAllCheckbox.checked) {
                this.selectedPurchases.add(purchaseId);
                checkbox.checked = true;
            } else {
                this.selectedPurchases.delete(purchaseId);
                checkbox.checked = false;
            }
        });
        
                this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }

    handleSelectAllPending(selectAllCheckbox) {
        const tableId = 'pendingPurchasesTable';
        const checkboxes = document.querySelectorAll(`#${tableId} tbody tr:not([style*="display: none"]) .row-checkbox`);
        
        checkboxes.forEach(checkbox => {
            const purchaseId = checkbox.getAttribute('data-id');
            if (selectAllCheckbox.checked) {
                this.selectedPurchases.add(purchaseId);
                checkbox.checked = true;
            } else {
                this.selectedPurchases.delete(purchaseId);
                checkbox.checked = false;
            }
        });
        
                this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }

    updateStats() {
        this.updateGlobalSelectionCount();
        
        if (this.selectedPurchases.size === 0) {
            this.hideStats();
            return;
        }
        
        this.showStats();
        this.calculateAndDisplayStats();
    }
    
    showStats() {
        if (this.statsContainer) {
            this.statsContainer.style.display = 'block';
            // حذف اسکرول خودکار تا کاربر در همان موقعیت بماند
            // this.statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    hideStats() {
        if (this.statsContainer) {
            this.statsContainer.style.display = 'none';
        }
    }
    
    clearAllSelections() {
        this.selectedPurchases.clear();
        
        // پاک کردن تمام چک‌باکس‌ها
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            
            // حذف رنگ سطر
            const row = checkbox.closest('tr');
            if (row) {
                row.classList.remove('table-warning', 'selected-row');
            }
        });
        
        document.querySelectorAll('.select-all-checkbox, .select-all-checkbox-archived, .select-all-checkbox-pending').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        });
        
        this.hideStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
        
        // نمایش پیام
        this.showSuccessMessage('تمام انتخاب‌ها پاک شد');
    }
    
    clearAllSelectionsSilent() {
        // پاک کردن تمام انتخاب‌ها بدون نمایش پیام
        this.selectedPurchases.clear();
        
        // پاک کردن تمام چک‌باکس‌ها
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            
            // حذف رنگ سطر
            const row = checkbox.closest('tr');
            if (row) {
                row.classList.remove('table-warning', 'selected-row');
            }
        });
        
        document.querySelectorAll('.select-all-checkbox, .select-all-checkbox-archived, .select-all-checkbox-pending').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        });
        
        this.hideStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی export button و bulk edit manager
        if (window.updateExportButton) {
            window.updateExportButton();
        }
        
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }
    
    calculateAndDisplayStats() {
        // بروزرسانی تعداد سطرهای انتخاب شده
        if (this.selectedRowsCountElement) {
            this.selectedRowsCountElement.textContent = this.selectedPurchases.size;
        }
        
        // همیشه از API سرور استفاده کن برای محاسبه دقیق‌تر آمار
        // تا مشکل ستون‌های مخفی شده برای نقش‌های مختلف حل شود
        this.calculateStatsFromServer();
    }
    
    calculateStatsFromServer() {
        // استفاده از API سرور برای محاسبه دقیق‌تر آمار
        const purchaseIds = Array.from(this.selectedPurchases).join(',');
        
        // نمایش لودینگ
        this.showLoadingStats();
        
        // ساخت URL به صورت پویا
        const apiUrl = window.PurchaseListConfig?.purchaseAggregatedStatsUrl || '/erp/purchases/aggregated-stats/';
        
        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: `purchase_ids=${encodeURIComponent(purchaseIds)}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.displayStatsFromServer(data.stats, data.hide_sensitive_info);
            } else {
                console.error('خطا در دریافت آمار از سرور:', data.message);
                // در صورت خطا از محاسبه محلی استفاده کن
                this.calculateStatsFromDOM();
            }
        })
        .catch(error => {
            console.error('خطا در ارتباط با سرور:', error);
            // در صورت خطا از محاسبه محلی استفاده کن
            this.calculateStatsFromDOM();
        });
    }
    
    calculateStatsFromDOM() {
        let totalOrderWeight = 0;
        let totalDeliveredWeight = 0;
        let totalCompanyPrice = 0;
        let totalCustomerPrice = 0;
        let totalAmountPaid = 0;
        let purchaseBaseInvoice = 0;
        let salesBaseInvoice = 0;
        let validCompanyPriceCount = 0;
        let validCustomerPriceCount = 0;
        
        // محاسبه آمار برای هر خرید انتخاب شده
        this.selectedPurchases.forEach(purchaseId => {
            const row = document.querySelector(`tr[data-id="${purchaseId}"]`);
            if (!row) return;
            
            // استخراج داده‌ها از سطر جدول
            const data = this.extractDataFromRow(row);
            
            // جمع‌آوری آمار
            totalOrderWeight += data.orderWeight || 0;
            totalDeliveredWeight += data.deliveredWeight || 0;
            totalAmountPaid += data.amountPaid || 0;
            
            if (data.companyPrice > 0) {
                totalCompanyPrice += data.companyPrice;
                validCompanyPriceCount++;
            }
            
            if (data.customerPrice > 0) {
                totalCustomerPrice += data.customerPrice;
                validCustomerPriceCount++;
            }
            
            // محاسبه فاکتور خرید و فروش مبنا بر اساس فرمول جدید
            if (data.companyPrice > 0 && data.customerPrice > 0) {
                // تعیین n بر اساس factor_code (که برابر با صدور فاکتور است)
                const factorCode = data.isFactored; // فاکتور مبنا = صدور فاکتور
                const n = factorCode ? 1 : 0;
                
                // محاسبه فاکتور خرید مبنا
                const purchaseBase = (n * data.companyPrice * data.deliveredWeight) + ((1 - n) * data.companyPrice * data.orderWeight);
                purchaseBaseInvoice += purchaseBase;
                
                // محاسبه فاکتور فروش مبنا
                const salesBase = (n * data.customerPrice * data.deliveredWeight) + ((1 - n) * data.customerPrice * data.orderWeight);
                salesBaseInvoice += salesBase;
            }
        });
        
        // محاسبه میانگین‌ها
        const avgCompanyPrice = validCompanyPriceCount > 0 ? totalCompanyPrice / validCompanyPriceCount : 0;
        const avgCustomerPrice = validCustomerPriceCount > 0 ? totalCustomerPrice / validCustomerPriceCount : 0;
        
        // محاسبه سود
        const profit = salesBaseInvoice - purchaseBaseInvoice;
        
        // نمایش آمار
        this.displayStats({
            totalOrderWeight,
            totalDeliveredWeight,
            avgCompanyPrice,
            avgCustomerPrice,
            totalAmountPaid,
            purchaseBaseInvoice,
            salesBaseInvoice,
            profit
        });
    }
    
    displayStatsFromServer(serverStats, hideSensitiveInfo = false) {
        // نمایش آمار دریافت شده از سرور
        const stats = {
            totalOrderWeight: serverStats.total_order_weight,
            totalDeliveredWeight: serverStats.total_delivered_weight,
            avgCustomerPrice: serverStats.avg_customer_price
        };
        
        // آمار حساس فقط برای نقش‌های مجاز
        if (!hideSensitiveInfo) {
            stats.avgCompanyPrice = serverStats.avg_company_price || 0;
            stats.totalAmountPaid = serverStats.total_amount_paid || 0;
            stats.purchaseBaseInvoice = serverStats.purchase_base_invoice || 0;
            stats.salesBaseInvoice = serverStats.sales_base_invoice || 0;
            stats.profit = serverStats.profit || 0;
        } else {
            // برای کارشناسان فروش و پیگیری
            stats.avgCompanyPrice = 0;
            stats.totalAmountPaid = 0;
            stats.purchaseBaseInvoice = 0;
            stats.salesBaseInvoice = 0;
            stats.profit = 0;
        }
        
        this.displayStats(stats);
    }
    
    showLoadingStats() {
        // نمایش لودینگ در المان‌های آمار
        const loadingText = '<i class="fas fa-spinner fa-spin"></i> در حال محاسبه...';
        
        if (this.totalOrderWeightElement) {
            this.totalOrderWeightElement.innerHTML = loadingText;
        }
        if (this.totalDeliveredWeightElement) {
            this.totalDeliveredWeightElement.innerHTML = loadingText;
        }
        if (this.avgCompanyPriceElement) {
            this.avgCompanyPriceElement.innerHTML = loadingText;
        }
        if (this.avgCustomerPriceElement) {
            this.avgCustomerPriceElement.innerHTML = loadingText;
        }
        if (this.totalAmountPaidElement) {
            this.totalAmountPaidElement.innerHTML = loadingText;
        }
        if (this.purchaseBaseInvoiceElement) {
            this.purchaseBaseInvoiceElement.innerHTML = loadingText;
        }
        if (this.salesBaseInvoiceElement) {
            this.salesBaseInvoiceElement.innerHTML = loadingText;
        }
        if (this.profitElement) {
            this.profitElement.innerHTML = loadingText;
        }
    }
    
    getCSRFToken() {
        // دریافت CSRF token از cookie یا meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }
        
        // اگر در meta tag نبود، از cookie بخوان
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        
        return cookieValue || '';
    }
    
    extractDataFromRow(row) {
        const data = {
            orderWeight: 0,
            deliveredWeight: 0,
            companyPrice: 0,
            customerPrice: 0,
            amountPaid: 0,
            isFactored: false
        };
        
        try {
            // استفاده اولویت‌دار از data attributes که قابل اطمینان‌ترند
            
            // استخراج وزن سفارش
            const orderWeightAttr = row.getAttribute('data-order-weight');
            if (orderWeightAttr && orderWeightAttr !== 'None') {
                data.orderWeight = parseFloat(orderWeightAttr) || 0;
            }
            
            // استخراج وزن بارنامه شده
            const deliveredWeightAttr = row.getAttribute('data-delivered-weight');
            if (deliveredWeightAttr && deliveredWeightAttr !== 'None') {
                data.deliveredWeight = parseFloat(deliveredWeightAttr) || 0;
            }
            
            // استخراج قیمت خرید
            const companyPriceAttr = row.getAttribute('data-company-price');
            if (companyPriceAttr && companyPriceAttr !== 'None') {
                data.companyPrice = parseFloat(companyPriceAttr) || 0;
            }
            
            // استخراج قیمت فروش
            const customerPriceAttr = row.getAttribute('data-customer-price');
            if (customerPriceAttr && customerPriceAttr !== 'None') {
                data.customerPrice = parseFloat(customerPriceAttr) || 0;
            }
            
            // استخراج مبلغ پرداختی
            const amountPaidAttr = row.getAttribute('data-amount-paid');
            if (amountPaidAttr && amountPaidAttr !== 'None') {
                data.amountPaid = parseFloat(amountPaidAttr) || 0;
            }
            
            // استخراج factor_code (فاکتور مبنا)
            const factorCodeAttr = row.getAttribute('data-factor-code');
            if (factorCodeAttr) {
                data.isFactored = factorCodeAttr === '1';
            } else {
                // fallback: استخراج از data-is-factored
                const isFactoredAttr = row.getAttribute('data-is-factored');
                if (isFactoredAttr) {
                    data.isFactored = isFactoredAttr === 'true';
                }
            }
            
            console.log(`استخراج داده برای ردیف ${row.getAttribute('data-id')}:`, data);
            
        } catch (error) {
            console.error('خطا در استخراج داده‌ها از سطر:', error);
        }
        
        return data;
    }
    
    displayStats(stats) {
        // نمایش آمار با فرمت مناسب
        if (this.totalOrderWeightElement) {
            this.totalOrderWeightElement.innerHTML = `${this.formatNumber(stats.totalOrderWeight)} <small>کیلوگرم</small>`;
        }
        
        if (this.totalDeliveredWeightElement) {
            this.totalDeliveredWeightElement.innerHTML = `${this.formatNumber(stats.totalDeliveredWeight)} <small>کیلوگرم</small>`;
        }
        
        // نمایش قیمت خرید فقط اگر مجاز باشد
        if (this.avgCompanyPriceElement && stats.avgCompanyPrice !== undefined) {
            this.avgCompanyPriceElement.innerHTML = `${this.formatNumber(Math.round(stats.avgCompanyPrice))} <small>ریال</small>`;
        }
        
        if (this.avgCustomerPriceElement) {
            this.avgCustomerPriceElement.innerHTML = `${this.formatNumber(Math.round(stats.avgCustomerPrice))} <small>ریال</small>`;
        }
        
        // نمایش مبلغ پرداختی فقط اگر مجاز باشد
        if (this.totalAmountPaidElement && stats.totalAmountPaid !== undefined) {
            this.totalAmountPaidElement.innerHTML = `${this.formatNumber(stats.totalAmountPaid)} <small>ریال</small>`;
        }
        
        // نمایش فاکتور خرید مبنا فقط اگر مجاز باشد
        if (this.purchaseBaseInvoiceElement && stats.purchaseBaseInvoice !== undefined) {
            this.purchaseBaseInvoiceElement.innerHTML = `${this.formatNumber(stats.purchaseBaseInvoice)} <small>ریال</small>`;
        }
        
        // نمایش فاکتور فروش مبنا فقط اگر مجاز باشد
        if (this.salesBaseInvoiceElement && stats.salesBaseInvoice !== undefined) {
            this.salesBaseInvoiceElement.innerHTML = `${this.formatNumber(stats.salesBaseInvoice)} <small>ریال</small>`;
        }
        
        // نمایش سود فقط اگر مجاز باشد
        if (this.profitElement && stats.profit !== undefined) {
            // تغییر رنگ بر اساس مثبت یا منفی بودن سود
            const profitClass = stats.profit >= 0 ? 'text-success' : 'text-danger';
            this.profitElement.innerHTML = `${this.formatNumber(stats.profit)} <small>ریال</small>`;
            this.profitElement.className = `fw-bold ${profitClass}`;
        }
    }
    
    formatNumber(num) {
        // فرمت کردن اعداد با کاما
        return new Intl.NumberFormat('fa-IR').format(num);
    }
    
    // متد عمومی برای دریافت آمار فعلی (برای استفاده در سایر قسمت‌ها)
    getCurrentStats() {
        if (this.selectedPurchases.size === 0) {
            return null;
        }
        
        const stats = {
            selectedCount: this.selectedPurchases.size,
            selectedIds: Array.from(this.selectedPurchases)
        };
        
        return stats;
    }
    
    // متد برای انتخاب خریدهای خاص (برای استفاده در سایر قسمت‌ها)
    selectPurchases(purchaseIds) {
        this.clearAllSelections();
        
        purchaseIds.forEach(id => {
            this.selectedPurchases.add(id.toString());
            const checkbox = document.querySelector(`input[data-id="${id}"]`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
        
        this.updateStats();
    }
    
    // متد جدید: بروزرسانی آمار بعد از تغییر فیلتر
    updateStatsAfterFilter() {
        // بررسی کنیم که آیا خریدهای انتخاب شده هنوز نمایش داده می‌شوند یا خیر
        const visibleSelectedPurchases = new Set();
        
        this.selectedPurchases.forEach(purchaseId => {
            const row = document.querySelector(`tr[data-id="${purchaseId}"]`);
            // اگر ردیف وجود دارد و نمایش داده می‌شود
            if (row && row.style.display !== 'none') {
                visibleSelectedPurchases.add(purchaseId);
                // مطمئن شویم که checkbox هم چک شده باشد
                const checkbox = row.querySelector('.row-checkbox');
                if (checkbox) {
                    checkbox.checked = true;
                }
            }
        });
        
        // اگر همه انتخاب‌ها پاک شدند، آمار را مخفی کن
        if (visibleSelectedPurchases.size === 0) {
            this.selectedPurchases = visibleSelectedPurchases;
            this.hideStats();
            this.updateGlobalSelectionCount();
            return;
        }
        
        // بروزرسانی لیست انتخاب‌ها
        this.selectedPurchases = visibleSelectedPurchases;
        
        // اگر انتخاب‌هایی باقی مانده‌اند، آمار را با API محاسبه کن
        // تا آمار دقیق کل خریدهای فیلتر شده ارائه شود
        this.updateStats();
        this.updateGlobalSelectionCount();
        
        // بروزرسانی دکمه خروجی اکسل
        if (window.updateExportButton) {
            window.updateExportButton();
        }
    }
    
    // متد جدید: همگام‌سازی با bulk edit manager
    syncWithBulkEditManager() {
        if (window.bulkEditManager) {
            // همگام‌سازی انتخاب‌ها
            this.selectedPurchases = new Set(window.bulkEditManager.selectedIds);
            this.updateStats();
        }
    }
}

// ایجاد instance اصلی
let purchaseStatsManager;

// راه‌اندازی پس از بارگذاری صفحه
document.addEventListener('DOMContentLoaded', function() {
    purchaseStatsManager = new PurchaseAggregatedStats();
    
    // در دسترس قرار دادن برای استفاده در سایر قسمت‌ها
    window.purchaseStatsManager = purchaseStatsManager;
    
    console.log('Purchase Aggregated Stats Manager initialized');
});

// Export برای استفاده در ماژول‌های دیگر
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PurchaseAggregatedStats;
} 