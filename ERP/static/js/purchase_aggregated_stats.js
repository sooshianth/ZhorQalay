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
        this.urgentPurchasesCountElement = document.getElementById('urgentPurchasesCount');
        this.totalExtelafWeightElement = document.getElementById('totalExtelafWeight');
        this.totalExtelafAmountElement = document.getElementById('totalExtelafAmount');
        
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
    
    handleRowSelection(checkbox) {
        const purchaseId = checkbox.getAttribute('data-id');
        
        if (checkbox.checked) {
            this.selectedPurchases.add(purchaseId);
        } else {
            this.selectedPurchases.delete(purchaseId);
        }
        
        this.updateStats();
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
    }
    
    updateStats() {
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
            this.statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        });
        
        document.querySelectorAll('.select-all-checkbox, .select-all-checkbox-archived').forEach(checkbox => {
            checkbox.checked = false;
        });
        
        this.hideStats();
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
        const apiUrl = '/purchases/aggregated-stats/';
        
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
        let urgentCount = 0;
        let totalExtelafWeight = 0;
        let totalExtelafAmount = 0;
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
            totalExtelafWeight += data.extelafWeight || 0;
            totalExtelafAmount += data.extelafAmount || 0;
            
            if (data.companyPrice > 0) {
                totalCompanyPrice += data.companyPrice;
                validCompanyPriceCount++;
            }
            
            if (data.customerPrice > 0) {
                totalCustomerPrice += data.customerPrice;
                validCustomerPriceCount++;
            }
            
            if (data.isUrgent) {
                urgentCount++;
            }
        });
        
        // محاسبه میانگین‌ها
        const avgCompanyPrice = validCompanyPriceCount > 0 ? totalCompanyPrice / validCompanyPriceCount : 0;
        const avgCustomerPrice = validCustomerPriceCount > 0 ? totalCustomerPrice / validCustomerPriceCount : 0;
        
        // نمایش آمار
        this.displayStats({
            totalOrderWeight,
            totalDeliveredWeight,
            avgCompanyPrice,
            avgCustomerPrice,
            totalAmountPaid,
            urgentCount,
            totalExtelafWeight,
            totalExtelafAmount
        });
    }
    
    displayStatsFromServer(serverStats, hideSensitiveInfo = false) {
        // نمایش آمار دریافت شده از سرور
        const stats = {
            totalOrderWeight: serverStats.total_order_weight,
            totalDeliveredWeight: serverStats.total_delivered_weight,
            avgCustomerPrice: serverStats.avg_customer_price,
            urgentCount: serverStats.urgent_purchases_count,
            totalExtelafWeight: serverStats.total_extelaf_weight
        };
        
        // آمار حساس فقط برای نقش‌های مجاز
        if (!hideSensitiveInfo) {
            stats.avgCompanyPrice = serverStats.avg_company_price || 0;
            stats.totalAmountPaid = serverStats.total_amount_paid || 0;
            stats.totalExtelafAmount = serverStats.total_extelaf_amount || 0;
        } else {
            // برای کارشناسان فروش و پیگیری
            stats.avgCompanyPrice = 0;
            stats.totalAmountPaid = 0;
            stats.totalExtelafAmount = 0;
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
        if (this.urgentPurchasesCountElement) {
            this.urgentPurchasesCountElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        if (this.totalExtelafWeightElement) {
            this.totalExtelafWeightElement.innerHTML = loadingText;
        }
        if (this.totalExtelafAmountElement) {
            this.totalExtelafAmountElement.innerHTML = loadingText;
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
            extelafWeight: 0,
            extelafAmount: 0,
            isUrgent: false
        };
        
        try {
            // استخراج وزن سفارش
            const weightCell = row.querySelector('.column-weight');
            if (weightCell) {
                const weightText = weightCell.textContent.trim().replace(/,/g, '');
                data.orderWeight = parseFloat(weightText) || 0;
            }
            
            // استخراج وزن بارنامه شده
            const deliveredWeightCell = row.querySelector('.column-delivered_weight');
            if (deliveredWeightCell) {
                const deliveredWeightText = deliveredWeightCell.textContent.trim().replace(/,/g, '');
                data.deliveredWeight = parseFloat(deliveredWeightText) || 0;
            }
            
            // استخراج قیمت خرید
            const companyPriceCell = row.querySelector('.column-company_price');
            if (companyPriceCell) {
                const companyPriceText = companyPriceCell.textContent.trim().replace(/,/g, '').replace(/-/g, '0');
                data.companyPrice = parseFloat(companyPriceText) || 0;
            }
            
            // استخراج قیمت فروش
            const customerPriceCell = row.querySelector('.column-customer_price');
            if (customerPriceCell) {
                const customerPriceText = customerPriceCell.textContent.trim().replace(/,/g, '').replace(/-/g, '0');
                data.customerPrice = parseFloat(customerPriceText) || 0;
            }
            
            // استخراج مبلغ پرداختی
            const amountPaidCell = row.querySelector('.column-amount_paid');
            if (amountPaidCell) {
                const amountPaidText = amountPaidCell.textContent.trim().replace(/,/g, '').replace(/-/g, '0');
                data.amountPaid = parseFloat(amountPaidText) || 0;
            }
            
            // استخراج وزن اختلاف
            const extelafWeightCell = row.querySelector('.column-extelaf_weight');
            if (extelafWeightCell) {
                const extelafWeightText = extelafWeightCell.textContent.trim().replace(/,/g, '').replace(/-/g, '0');
                data.extelafWeight = parseFloat(extelafWeightText) || 0;
            }
            
            // استخراج مبلغ اختلاف
            const extelafAmountCell = row.querySelector('.column-extelaf_amount');
            if (extelafAmountCell) {
                const extelafAmountText = extelafAmountCell.textContent.trim().replace(/,/g, '').replace(/-/g, '0');
                data.extelafAmount = parseFloat(extelafAmountText) || 0;
            }
            
            // بررسی وضعیت فوری
            data.isUrgent = row.classList.contains('urgent-row') || 
                           row.querySelector('.urgent-badge') !== null;
            
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
        
        if (this.urgentPurchasesCountElement) {
            this.urgentPurchasesCountElement.textContent = stats.urgentCount;
        }
        
        if (this.totalExtelafWeightElement) {
            this.totalExtelafWeightElement.innerHTML = `${this.formatNumber(stats.totalExtelafWeight)} <small>کیلوگرم</small>`;
        }
        
        // نمایش مبلغ اختلاف فقط اگر مجاز باشد
        if (this.totalExtelafAmountElement && stats.totalExtelafAmount !== undefined) {
            this.totalExtelafAmountElement.innerHTML = `${this.formatNumber(stats.totalExtelafAmount)} <small>ریال</small>`;
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
        
        // بروزرسانی لیست انتخاب‌ها
        this.selectedPurchases = visibleSelectedPurchases;
        
        // بروزرسانی آمار
        this.updateStats();
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