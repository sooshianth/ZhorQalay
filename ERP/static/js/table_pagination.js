/**
 * سیستم پیجینیشن جاوااسکریپتی برای جداول
 * با قابلیت فیلتر و سورت روی تمام داده‌ها
 */
class TablePagination {
    constructor(config = {}) {
        this.config = {
            tableSelector: config.tableSelector || 'table',
            perPage: config.perPage || 50,
            perPageOptions: config.perPageOptions || [10, 25, 50, 100, 200],
            paginationContainer: config.paginationContainer || null,
            infoContainer: config.infoContainer || null,
            perPageSelector: config.perPageSelector || '#perPageSelect',
            showFirstLast: config.showFirstLast !== false,
            showPrevNext: config.showPrevNext !== false,
            maxVisiblePages: config.maxVisiblePages || 5,
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
        
        console.log(`Table pagination initializing: ${this.totalRows} total rows, ${this.config.perPage} per page`);
        
        // ایجاد المان‌های UI
        this.createPaginationUI();
        this.setupEventListeners();
        
        // محاسبه صفحات و نمایش اولیه
        this.updatePagination();
        this.showPage(1);
        
        console.log(`Table pagination initialized successfully`);
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
            // ایجاد المان اطلاعات پایین جدول
            this.infoElement = document.createElement('div');
            this.infoElement.className = 'pagination-info d-flex justify-content-between align-items-center mt-3 mb-2';
            this.table.parentNode.insertBefore(this.infoElement, this.table.nextSibling);
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
        
        // گوش دادن به تغییرات DOM برای تشخیص فیلترها
        this.observeTableChanges();
    }
    
    observeTableChanges() {
        if (!this.tbody) return;
        
        this.observer = new MutationObserver((mutations) => {
            let shouldUpdate = false;
            
            mutations.forEach((mutation) => {
                // فقط اگر تغییر style توسط فیلتر باشد، نه توسط pagination
                if (mutation.type === 'attributes' && 
                    mutation.attributeName === 'style' &&
                    mutation.target.tagName === 'TR' &&
                    !mutation.target.classList.contains('pagination-updating')) {
                    shouldUpdate = true;
                }
            });
            
            if (shouldUpdate && !this.isUpdating) {
                this.isUpdating = true;
                
                // کمی تاخیر برای اطمینان از اتمام فیلترها
                clearTimeout(this.updateTimeout);
                this.updateTimeout = setTimeout(() => {
                    this.updateFilteredRows();
                    this.updatePagination();
                    if (this.currentPage > this.totalPages && this.totalPages > 0) {
                        this.showPage(this.totalPages);
                    } else {
                        this.showPage(this.currentPage);
                    }
                    this.isUpdating = false;
                }, 200);
            }
        });
        
        this.observer.observe(this.tbody, {
            attributes: true,
            subtree: true,
            attributeFilter: ['style']
        });
    }
    
    onFilterApplied() {
        this.updateFilteredRows();
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
    }
    
    onFilterCleared() {
        this.updateFilteredRows();
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
    }
    
    onAllFiltersCleared() {
        this.filteredRowsCache = [...this.allRows];
        this.filteredRows = this.totalRows;
        this.currentPage = 1;
        this.updatePagination();
        this.showPage(1);
    }
    
    updateFilteredRows() {
        // پیدا کردن ردیف‌های نمایش داده شده (غیر مخفی)
        this.filteredRowsCache = this.allRows.filter(row => {
            return row.style.display !== 'none';
        });
        this.filteredRows = this.filteredRowsCache.length;
    }
    
    updatePagination() {
        this.totalPages = Math.ceil(this.filteredRows / this.config.perPage);
        
        console.log(`Pagination update: ${this.filteredRows} filtered rows, ${this.config.perPage} per page, ${this.totalPages} total pages`);
        
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
        if (!this.paginationElement) {
            console.warn('Pagination element not found');
            return;
        }
        
        if (this.totalPages <= 1) {
            this.paginationElement.innerHTML = '';
            return;
        }
        
        console.log(`Creating pagination controls: ${this.totalPages} pages, current: ${this.currentPage}`);
        
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
            return;
        }
        
        this.currentPage = pageNumber;
        
        // جلوگیری از infinite loop
        this.isUpdating = true;
        
        // اضافه کردن class برای جلوگیری از تشخیص توسط observer
        this.allRows.forEach(row => {
            row.classList.add('pagination-updating');
        });
        
        // مخفی کردن همه ردیف‌ها
        this.allRows.forEach(row => {
            row.style.display = 'none';
        });
        
        // محاسبه ردیف‌های قابل نمایش در این صفحه
        const startIndex = (pageNumber - 1) * this.config.perPage;
        const endIndex = startIndex + this.config.perPage;
        
        // نمایش ردیف‌های مربوط به این صفحه
        const rowsToShow = this.filteredRowsCache.slice(startIndex, endIndex);
        rowsToShow.forEach(row => {
            row.style.display = '';
        });
        
        // حذف class
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
        this.updateFilteredRows();
        this.updatePagination();
        this.showPage(this.currentPage);
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
        });
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