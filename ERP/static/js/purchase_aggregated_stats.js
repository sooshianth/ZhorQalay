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