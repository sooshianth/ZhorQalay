/**
 * سیستم پیجینیشن جاوااسکریپتی برای جداول
 * با قابلیت فیلتر و سورت روی تمام داده‌ها
 */
class TablePagination {
    constructor(config = {}) {
        this.config = {
            tableSelector: config.tableSelector || 'table',
            perPage: config.perPage || 50,
            perPageOptions: config.perPageOptions || [5, 10, 25, 50, 100, 200],
            paginationContainer: config.paginationContainer || null,
            infoContainer: config.infoContainer || null,
            perPageSelector: config.perPageSelector || '#perPageSelect',
            showFirstLast: config.showFirstLast !== false,
            showPrevNext: config.showPrevNext !== false,
            maxVisiblePages: config.maxVisiblePages || 5,
            debug: config.debug || false,
            ...config
        };
        
        this.currentPage = 1;
        this.totalPages = 0;
        this.totalRows = 0;
        this.filteredRows = 0;
        this.allRows = [];
        this.filteredRowsCache = [];
        this.table = null;
        this.tbody = null;
        this.isUpdating = false;
        this.updateTimeout = null;
        this.observer = null;
        
        if (this.config.debug) {
            console.log('TablePagination config:', this.config);
        }
        
        this.init();
    }
    
    init() {
        this.table = document.querySelector(this.config.tableSelector);
        if (!this.table) {
            console.warn('Table not found:', this.config.tableSelector);
            return;
        }
        
        this.tbody = this.table.querySelector('tbody');
        if (!this.tbody) {
            console.warn('Table body not found');
            return;
        }
        
        // ذخیره تمام ردیف‌ها
        this.allRows = Array.from(this.tbody.querySelectorAll('tr'));
        this.totalRows = this.allRows.length;
        this.filteredRowsCache = [...this.allRows];
        this.filteredRows = this.totalRows;
        
        if (this.config.debug) {
            console.log(`TablePagination init: Found ${this.totalRows} rows in table ${this.config.tableSelector}`);
        }
        
        // ایجاد المان‌های UI
        this.createPaginationUI();
        this.setupEventListeners();
        
        // محاسبه صفحات و نمایش اولیه
        this.updatePagination();
        this.showPage(1);
        
        console.log(`Table pagination initialized: ${this.totalRows} rows`);
    }
    
    createPaginationUI() {
        // ایجاد کنترل تعداد نمایش در صفحه
        this.createPerPageControl();
        
        // ایجاد اطلاعات پیجینیشن
        this.createPaginationInfo();
        
        // ایجاد دکمه‌های پیجینیشن
        this.createPaginationControls();
    }
    
    createPerPageControl() {
        const perPageSelect = document.querySelector(this.config.perPageSelector);
        if (perPageSelect) {
            // تنظیم مقدار فعلی
            perPageSelect.value = this.config.perPage;
            
            // اضافه کردن event listener
            perPageSelect.addEventListener('change', (e) => {
                this.config.perPage = parseInt(e.target.value);
                this.currentPage = 1; // بازگشت به صفحه اول
                this.updatePagination();
                this.showPage(1);
            });
        }
    }
    
    createPaginationInfo() {
        if (this.config.infoContainer) {
            const container = document.querySelector(this.config.infoContainer);
            if (container) {
                this.infoElement = container;
            }
        } else {
            // ایجاد المان اطلاعات در بالای جدول
            this.infoElement = document.createElement('div');
            this.infoElement.className = 'pagination-info d-flex justify-content-between align-items-center mb-3';
            this.table.parentNode.insertBefore(this.infoElement, this.table);
        }
    }
    
    createPaginationControls() {
        if (this.config.paginationContainer) {
            const container = document.querySelector(this.config.paginationContainer);
            if (container) {
                this.paginationElement = container;
            }
        } else {
            // ایجاد المان پیجینیشن زیر جدول
            this.paginationElement = document.createElement('div');
            this.paginationElement.className = 'pagination-wrapper d-flex justify-content-center mt-3';
            this.table.parentNode.insertBefore(this.paginationElement, this.table.nextSibling);
        }
    }
    
    setupEventListeners() {
        // اگر table filter موجود است، به رویدادهای آن گوش کنیم
        document.addEventListener('tableFilterApplied', (e) => {
            this.onFilterApplied();
        });
        
        document.addEventListener('tableFilterCleared', (e) => {
            this.onFilterCleared();
        });
        
        document.addEventListener('tableFiltersCleared', (e) => {
            this.onAllFiltersCleared();
        });
        
        // گوش دادن به رویداد مرتب‌سازی
        document.addEventListener('tableSorted', (e) => {
            this.onTableSorted(e.detail);
        });
        
        // گوش دادن به تغییرات DOM برای تشخیص فیلترها
        this.observeTableChanges();
    }
    
    observeTableChanges() {
        if (!this.tbody) return;
        
        this.observer = new MutationObserver((mutations) => {
            let shouldUpdate = false;
            let hasFilterChanges = false;
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && 
                    mutation.attributeName === 'style' &&
                    mutation.target.tagName === 'TR' &&
                    !mutation.target.classList.contains('pagination-updating')) {
                    
                    // بررسی که آیا این تغییر مربوط به فیلتر است یا pagination
                    const newDisplay = mutation.target.style.display;
                    const oldDisplay = mutation.oldValue ? 
                        (mutation.oldValue.includes('display: none') ? 'none' : '') : '';
                    
                    if (newDisplay !== oldDisplay) {
                        shouldUpdate = true;
                        hasFilterChanges = true;
                    }
                }
            });
            
            if (shouldUpdate && !this.isUpdating) {
                this.isUpdating = true;
                
                if (this.config.debug) {
                    console.log('TablePagination: Table changes detected, updating...');
                }
                
                // کمی تاخیر برای اطمینان از اتمام فیلترها
                clearTimeout(this.updateTimeout);
                this.updateTimeout = setTimeout(() => {
                    this.updateFilteredRows();
                    this.updatePagination();
                    
                    // اگر فیلتر جدید اعمال شده، برو به صفحه اول
                    if (hasFilterChanges) {
                        this.currentPage = 1;
                    }
                    
                    // اطمینان از صحت شماره صفحه
                    if (this.currentPage > this.totalPages && this.totalPages > 0) {
                        this.showPage(this.totalPages);
                    } else {
                        this.showPage(this.currentPage);
                    }
                    this.isUpdating = false;
                }, 150);
            }
        });
        
        this.observer.observe(this.tbody, {
            attributes: true,
            subtree: true,
            attributeFilter: ['style'],
            attributeOldValue: true
        });
    }
    
    onFilterApplied() {
        if (this.config.debug) {
            console.log('TablePagination: Filter applied');
        }
        this.isUpdating = true;
        
        // بروزرسانی ردیف‌های فیلتر شده
        this.updateFilteredRows();
        
        // بازگشت به صفحه اول بعد از اعمال فیلتر
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
        
        setTimeout(() => {
            this.isUpdating = false;
        }, 100);
        
        if (this.config.debug) {
            console.log(`TablePagination: Filter applied. Showing ${this.filteredRows} of ${this.totalRows} rows`);
        }
    }
    
    onFilterCleared() {
        if (this.config.debug) {
            console.log('TablePagination: Filter cleared');
        }
        this.isUpdating = true;
        this.updateFilteredRows();
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
        setTimeout(() => {
            this.isUpdating = false;
        }, 100);
    }
    
    onAllFiltersCleared() {
        if (this.config.debug) {
            console.log('TablePagination: All filters cleared');
        }
        this.isUpdating = true;
        this.filteredRowsCache = [...this.allRows];
        this.filteredRows = this.totalRows;
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
        setTimeout(() => {
            this.isUpdating = false;
        }, 100);
    }
    
    onTableSorted(detail) {
        if (this.config.debug) {
            console.log('TablePagination: Table sorted', detail);
        }
        
        // بررسی اینکه آیا این sorting مربوط به همین جدول است
        const tableElement = this.table;
        if (!tableElement || tableElement.id !== detail.tableId) {
            return;
        }
        
        this.isUpdating = true;
        
        // بروزرسانی لیست تمام ردیف‌ها با ترتیب جدید
        this.allRows = Array.from(this.tbody.querySelectorAll('tr'));
        this.totalRows = this.allRows.length;
        
        // بروزرسانی ردیف‌های فیلتر شده
        this.updateFilteredRows();
        
        // اگر فیلتری فعال نیست، همه ردیف‌ها باید در نظر گرفته شوند
        if (this.filteredRowsCache.length === 0 || this.filteredRowsCache.length === this.totalRows) {
            this.filteredRowsCache = [...this.allRows];
            this.filteredRows = this.totalRows;
        }
        
        // بازگشت به صفحه اول بعد از sorting
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
        
        setTimeout(() => {
            this.isUpdating = false;
        }, 100);
        
        if (this.config.debug) {
            console.log(`TablePagination: Updated after sorting. Total rows: ${this.totalRows}, Filtered rows: ${this.filteredRows}`);
        }
    }
    
    updateFilteredRows() {
        // پیدا کردن ردیف‌های نمایش داده شده (غیر مخفی)
        this.filteredRowsCache = this.allRows.filter(row => {
            // نادیده گرفتن ردیف‌هایی که توسط pagination مخفی شده‌اند
            if (row.classList.contains('pagination-updating')) {
                return true; // فرض کن که این ردیف قابل نمایش است
            }
            
            // فقط ردیف‌هایی که توسط فیلتر مخفی نشده‌اند
            return row.style.display !== 'none';
        });
        
        this.filteredRows = this.filteredRowsCache.length;
        
        if (this.config.debug) {
            console.log(`TablePagination: Filtered rows updated: ${this.filteredRows} of ${this.totalRows} total rows`);
        }
    }
    
    updatePagination() {
        this.totalPages = Math.ceil(this.filteredRows / this.config.perPage);
        
        // محدود کردن صفحه فعلی
        if (this.currentPage > this.totalPages) {
            this.currentPage = Math.max(1, this.totalPages);
        }
        
        this.updatePaginationInfo();
        this.updatePaginationControls();
    }
    
    updatePaginationInfo() {
        if (!this.infoElement) return;
        
        if (this.filteredRows === 0) {
            this.infoElement.innerHTML = `
                <span class="text-muted">
                    <i class="fas fa-info-circle me-1"></i>
                    هیچ رکوردی یافت نشد
                </span>
            `;
            return;
        }
        
        const startIndex = (this.currentPage - 1) * this.config.perPage + 1;
        const endIndex = Math.min(this.currentPage * this.config.perPage, this.filteredRows);
        
        let infoHtml = `
            <span class="text-muted">
                <i class="fas fa-info-circle me-1"></i>
                نمایش ${startIndex.toLocaleString('fa')} تا ${endIndex.toLocaleString('fa')} از ${this.filteredRows.toLocaleString('fa')} رکورد
        `;
        
        if (this.filteredRows !== this.totalRows) {
            infoHtml += ` (فیلتر شده از ${this.totalRows.toLocaleString('fa')} رکورد کل)`;
        }
        
        infoHtml += '</span>';
        
        if (this.totalPages > 1) {
            infoHtml += `
                <span class="badge bg-primary">
                    صفحه ${this.currentPage.toLocaleString('fa')} از ${this.totalPages.toLocaleString('fa')}
                </span>
            `;
        }
        
        this.infoElement.innerHTML = infoHtml;
    }
    
    updatePaginationControls() {
        if (!this.paginationElement || this.totalPages <= 1) {
            if (this.paginationElement) {
                this.paginationElement.innerHTML = '';
            }
            return;
        }
        
        let paginationHtml = '<nav aria-label="صفحه‌بندی"><ul class="pagination justify-content-center mb-0">';
        
        // دکمه اولین صفحه
        if (this.config.showFirstLast && this.currentPage > 1) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1" aria-label="اولین صفحه">
                        <span aria-hidden="true">&laquo;&laquo;</span>
                    </a>
                </li>
            `;
        }
        
        // دکمه صفحه قبلی
        if (this.config.showPrevNext && this.currentPage > 1) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${this.currentPage - 1}" aria-label="صفحه قبلی">
                        <span aria-hidden="true">&laquo;</span>
                    </a>
                </li>
            `;
        }
        
        // صفحات میانی
        const { startPage, endPage } = this.calculatePageRange();
        
        // اضافه کردن صفحه اول و ... اگر نیاز باشد
        if (startPage > 1) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1">1</a>
                </li>
            `;
            if (startPage > 2) {
                paginationHtml += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
        }
        
        // صفحات قابل مشاهده
        for (let i = startPage; i <= endPage; i++) {
            const isActive = i === this.currentPage;
            paginationHtml += `
                <li class="page-item ${isActive ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i.toLocaleString('fa')}</a>
                </li>
            `;
        }
        
        // اضافه کردن ... و صفحه آخر اگر نیاز باشد
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                paginationHtml += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${this.totalPages}">${this.totalPages.toLocaleString('fa')}</a>
                </li>
            `;
        }
        
        // دکمه صفحه بعدی
        if (this.config.showPrevNext && this.currentPage < this.totalPages) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${this.currentPage + 1}" aria-label="صفحه بعدی">
                        <span aria-hidden="true">&raquo;</span>
                    </a>
                </li>
            `;
        }
        
        // دکمه آخرین صفحه
        if (this.config.showFirstLast && this.currentPage < this.totalPages) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${this.totalPages}" aria-label="آخرین صفحه">
                        <span aria-hidden="true">&raquo;&raquo;</span>
                    </a>
                </li>
            `;
        }
        
        paginationHtml += '</ul></nav>';
        
        this.paginationElement.innerHTML = paginationHtml;
        
        // اضافه کردن event listener به دکمه‌ها
        this.paginationElement.querySelectorAll('a.page-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.getAttribute('data-page') || e.target.closest('a').getAttribute('data-page'));
                this.showPage(page);
            });
        });
    }
    
    calculatePageRange() {
        const maxVisible = this.config.maxVisiblePages;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(this.totalPages, startPage + maxVisible - 1);
        
        // تنظیم مجدد اگر صفحات کافی نداریم
        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        
        return { startPage, endPage };
    }
    
    showPage(pageNumber) {
        if (pageNumber < 1 || pageNumber > this.totalPages) {
            if (this.config.debug) {
                console.log(`TablePagination: Invalid page number ${pageNumber}. Total pages: ${this.totalPages}`);
            }
            return;
        }
        
        this.currentPage = pageNumber;
        
        if (this.config.debug) {
            console.log(`TablePagination: Showing page ${pageNumber} of ${this.totalPages}`);
        }
        
        // جلوگیری از infinite loop
        this.isUpdating = true;
        
        // اضافه کردن class برای جلوگیری از تشخیص توسط observer
        this.allRows.forEach(row => {
            row.classList.add('pagination-updating');
        });
        
        // ابتدا همه ردیف‌ها را مخفی کن
        this.allRows.forEach(row => {
            row.style.display = 'none';
        });
        
        // محاسبه ردیف‌های قابل نمایش در این صفحه
        const startIndex = (pageNumber - 1) * this.config.perPage;
        const endIndex = startIndex + this.config.perPage;
        
        // فقط ردیف‌های فیلتر شده را در نظر بگیر
        const rowsToShow = this.filteredRowsCache.slice(startIndex, endIndex);
        
        if (this.config.debug) {
            console.log(`TablePagination: Showing ${rowsToShow.length} rows (${startIndex}-${endIndex-1}) from ${this.filteredRowsCache.length} filtered rows`);
        }
        
        // نمایش ردیف‌های مربوط به این صفحه
        rowsToShow.forEach(row => {
            // اطمینان از اینکه این ردیف باید نمایش داده شود
            if (this.filteredRowsCache.includes(row)) {
                row.style.display = '';
            }
        });
        
        // حذف class و flag
        setTimeout(() => {
            this.allRows.forEach(row => {
                row.classList.remove('pagination-updating');
            });
            this.isUpdating = false;
        }, 50);
        
        // بروزرسانی UI
        this.updatePaginationInfo();
        this.updatePaginationControls();
        
        // ارسال رویداد
        this.dispatchEvent('pageChanged', {
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            totalRows: this.filteredRows,
            rowsPerPage: this.config.perPage
        });
    }
    
    goToPage(pageNumber) {
        this.showPage(pageNumber);
    }
    
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.showPage(this.currentPage + 1);
        }
    }
    
    prevPage() {
        if (this.currentPage > 1) {
            this.showPage(this.currentPage - 1);
        }
    }
    
    firstPage() {
        this.showPage(1);
    }
    
    lastPage() {
        this.showPage(this.totalPages);
    }
    
    setPerPage(perPage) {
        this.config.perPage = perPage;
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
    }
    
    refresh() {
        // بروزرسانی لیست ردیف‌ها
        this.allRows = Array.from(this.tbody.querySelectorAll('tr'));
        this.totalRows = this.allRows.length;
        
        // بروزرسانی ردیف‌های فیلتر شده
        this.updateFilteredRows();
        
        // اگر فیلتری فعال نیست، همه ردیف‌ها قابل نمایش هستند
        if (this.filteredRowsCache.length === 0) {
            this.filteredRowsCache = [...this.allRows];
            this.filteredRows = this.totalRows;
        }
        
        // بروزرسانی pagination
        this.updatePagination();
        
        // اطمینان از صحت شماره صفحه
        if (this.currentPage > this.totalPages && this.totalPages > 0) {
            this.currentPage = this.totalPages;
        } else if (this.currentPage < 1) {
            this.currentPage = 1;
        }
        
        this.showPage(this.currentPage);
        
        if (this.config.debug) {
            console.log(`TablePagination refreshed: ${this.totalRows} total rows, ${this.filteredRows} filtered rows, showing page ${this.currentPage} of ${this.totalPages}`);
        }
    }
    
    destroy() {
        // حذف event listener ها
        if (this.observer) {
            this.observer.disconnect();
        }
        
        // حذف timeout ها
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        
        // حذف المان‌های UI ایجاد شده
        if (this.infoElement && !this.config.infoContainer) {
            this.infoElement.remove();
        }
        
        if (this.paginationElement && !this.config.paginationContainer) {
            this.paginationElement.remove();
        }
        
        // نمایش همه ردیف‌ها
        this.allRows.forEach(row => {
            row.style.display = '';
            row.classList.remove('pagination-updating');
        });
        
        if (this.config.debug) {
            console.log('TablePagination destroyed');
        }
    }
    
    dispatchEvent(eventName, detail) {
        const event = new CustomEvent(`tablePagination${eventName}`, {
            detail: detail,
            bubbles: true
        });
        document.dispatchEvent(event);
    }
    
    // متدهای کمکی
    getCurrentPageInfo() {
        return {
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            totalRows: this.filteredRows,
            rowsPerPage: this.config.perPage,
            startIndex: (this.currentPage - 1) * this.config.perPage + 1,
            endIndex: Math.min(this.currentPage * this.config.perPage, this.filteredRows)
        };
    }
    
    getTotalRowsCount() {
        return this.totalRows;
    }
    
    getFilteredRowsCount() {
        return this.filteredRows;
    }
    
    isFirstPage() {
        return this.currentPage === 1;
    }
    
    isLastPage() {
        return this.currentPage === this.totalPages;
    }
}

// تابع سازنده برای سهولت استفاده
function createTablePagination(config) {
    return new TablePagination(config);
}

// نمونه کامل برای جداول چندگانه
class MultiTablePagination {
    constructor() {
        this.paginators = new Map();
    }
    
    addTable(tableId, config) {
        const tablePagination = new TablePagination({
            tableSelector: `#${tableId}`,
            ...config
        });
        this.paginators.set(tableId, tablePagination);
        return tablePagination;
    }
    
    getTable(tableId) {
        return this.paginators.get(tableId);
    }
    
    removeTable(tableId) {
        const paginator = this.paginators.get(tableId);
        if (paginator) {
            paginator.destroy();
            this.paginators.delete(tableId);
        }
    }
    
    refreshAll() {
        this.paginators.forEach(paginator => {
            paginator.refresh();
        });
    }
    
    destroyAll() {
        this.paginators.forEach(paginator => {
            paginator.destroy();
        });
        this.paginators.clear();
    }
}

// Export برای استفاده در ماژول‌ها
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TablePagination, MultiTablePagination, createTablePagination };
} 