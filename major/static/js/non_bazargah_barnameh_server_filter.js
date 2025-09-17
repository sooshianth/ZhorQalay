/**
 * کلاس مدیریت فیلتر سمت سرور برای جدول بارنامه‌های خارج بازارگاه
 */
class NonBazargahBarnamehServerFilter {
    constructor(tableSelector) {
        this.tableId = tableSelector;
        this.tableElement = document.querySelector(tableSelector);
        
        if (!this.tableElement) {
            console.warn(`جدول با selector ${tableSelector} یافت نشد`);
            return;
        }
        
        this.filterUrl = this.tableElement.dataset.filterUrl;
        this.columnValuesUrl = this.tableElement.dataset.columnValuesUrl;
        
        // Initialize state
        this.currentFilters = {};
        this.currentSort = { column: null, direction: 'asc' };
        this.currentPage = 1;
        this.perPage = this.getInitialPerPage();
        
        this.isLoading = false;
        
        // Cache برای مقادیر ستون‌ها
        this.columnValuesCache = {};
        
        this.init();
    }
    
    getInitialPerPage() {
        // بررسی selector موجود در template
        const perPageSelector = document.querySelector('#barnamehPerPage');
        if (perPageSelector && perPageSelector.value) {
            return parseInt(perPageSelector.value);
        }
        
        return 20; // پیش‌فرض
    }
    
    init() {
        console.log('NonBazargahBarnamehServerFilter: init() called');
        console.log('NonBazargahBarnamehServerFilter: filterUrl =', this.filterUrl);
        console.log('NonBazargahBarnamehServerFilter: columnValuesUrl =', this.columnValuesUrl);
        
        if (!this.filterUrl || !this.columnValuesUrl) {
            console.warn('URL های فیلتر تنظیم نشده‌اند');
            return;
        }
        
        // اطمینان از نمایش ستون‌های الزامی
        this.ensureRequiredColumnsVisible();
        
        // غیرفعال کردن traditional pagination برای این جدول
        this.disableTraditionalPagination();
        
        this.setupFilterButtons();
        this.setupPerPageSelector();
        this.setupGlobalSearchHandler();
        
        // بارگذاری اولیه داده‌ها 
        setTimeout(() => {
            this.loadInitialData();
        }, 100);
        
        console.log('NonBazargahBarnamehServerFilter: init() completed');
    }
    
    ensureRequiredColumnsVisible() {
        // اطمینان از نمایش ستون‌های الزامی
        const requiredColumns = ['select', 'actions'];
        
        requiredColumns.forEach(columnId => {
            const header = this.tableElement.querySelector(`th[data-column-id="${columnId}"]`);
            if (header) {
                header.style.display = 'table-cell';
                console.log(`NonBazargahBarnamehServerFilter: Ensuring ${columnId} column is visible`);
            }
        });
    }
    
    disableTraditionalPagination() {
        // علامت‌گذاری جدول به عنوان دارای server filter
        this.tableElement.setAttribute('data-server-filter-active', 'true');
        
        // غیرفعال کردن traditional pagination links
        const traditionalPaginationContainer = document.querySelector('#barnamehPagination');
        
        if (traditionalPaginationContainer) {
            traditionalPaginationContainer.style.display = 'none';
        }
        
        // غیرفعال کردن traditional per-page selectors
        const traditionalPerPageSelect = document.querySelector('#barnamehPerPage:not([data-server-filter-listener])');
        if (traditionalPerPageSelect && !traditionalPerPageSelect.hasAttribute('data-server-filter-listener')) {
            traditionalPerPageSelect.setAttribute('data-server-filter-listener', 'true');
            traditionalPerPageSelect.addEventListener('change', (e) => {
                this.perPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.applyFilters();
            });
        }
    }
    
    setupPerPageSelector() {
        // پیدا کردن per page selector موجود در template
        const existingSelector = document.querySelector('#barnamehPerPage');
        if (existingSelector) {
            existingSelector.setAttribute('data-server-filter-listener', 'true');
            existingSelector.addEventListener('change', (e) => {
                this.perPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.applyFilters();
            });
            return;
        }
        
        // اگر selector موجود نبود، یکی ایجاد کن (fallback)
        const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
        
        const perPageContainer = document.createElement('div');
        perPageContainer.className = 'per-page-container mb-3 d-flex align-items-center gap-3';
        perPageContainer.innerHTML = `
            <label for="barnamehPerPageFilter" class="form-label me-2">تعداد در هر صفحه:</label>
            <select id="barnamehPerPageFilter" class="form-select form-select-sm w-auto">
                <option value="5" ${this.perPage === 5 ? 'selected' : ''}>5</option>
                <option value="10" ${this.perPage === 10 ? 'selected' : ''}>10</option>
                <option value="20" ${this.perPage === 20 ? 'selected' : ''}>20</option>
                <option value="50" ${this.perPage === 50 ? 'selected' : ''}>50</option>
                <option value="100" ${this.perPage === 100 ? 'selected' : ''}>100</option>
                <option value="200" ${this.perPage === 200 ? 'selected' : ''}>200</option>
                <option value="500" ${this.perPage === 500 ? 'selected' : ''}>500</option>
                <option value="1000" ${this.perPage === 1000 ? 'selected' : ''}>1000</option>
                <option value="10000" ${this.perPage === 10000 ? 'selected' : ''}>همه</option>
            </select>
        `;
        
        tableContainer.insertBefore(perPageContainer, tableContainer.firstChild);
        
        // اضافه کردن event listener
        const select = perPageContainer.querySelector('select');
        select.addEventListener('change', (e) => {
            this.perPage = parseInt(e.target.value);
            this.currentPage = 1;
            this.applyFilters();
        });
    }
    
    setupGlobalSearchHandler() {
        console.log('NonBazargahBarnamehServerFilter: Setting up global search handler...');
        
        // پیدا کردن input جستجوی سریع
        const globalSearchInput = document.querySelector('#real-time-search, #global-search, #barnameh-search');
        
        console.log('NonBazargahBarnamehServerFilter: Global search input found:', globalSearchInput);
        
        if (!globalSearchInput) {
            console.warn('NonBazargahBarnamehServerFilter: Global search input not found');
            return;
        }
        
        // حذف event listener قبلی
        globalSearchInput.removeEventListener('input', globalSearchInput._searchHandler);
        globalSearchInput.removeEventListener('keyup', globalSearchInput._searchHandler);
        
        console.log('NonBazargahBarnamehServerFilter: Adding new search listener');
        
        let searchTimeout;
        
        // تعریف handler جدید
        const searchHandler = (e) => {
            const searchValue = e.target.value.trim();
            console.log('NonBazargahBarnamehServerFilter: Search input changed to:', searchValue);
            
            // لغو timeout قبلی
            clearTimeout(searchTimeout);
            
            // نمایش loading indicator
            const loadingIndicator = document.querySelector('#search-loading');
            if (loadingIndicator) {
                loadingIndicator.classList.remove('d-none');
                console.log('NonBazargahBarnamehServerFilter: Showing loading indicator');
            }
            
            // تنظیم timeout جدید برای جستجو
            searchTimeout = setTimeout(() => {
                console.log('NonBazargahBarnamehServerFilter: Executing search for:', searchValue);
                
                // تنظیم مجدد صفحه به 1
                this.currentPage = 1;
                
                // اعمال فیلترها
                this.applyFilters().then(() => {
                    // مخفی کردن loading indicator
                    if (loadingIndicator) {
                        loadingIndicator.classList.add('d-none');
                        console.log('NonBazargahBarnamehServerFilter: Hiding loading indicator');
                    }
                }).catch((error) => {
                    console.error('NonBazargahBarnamehServerFilter: Search error:', error);
                    if (loadingIndicator) {
                        loadingIndicator.classList.add('d-none');
                    }
                });
            }, 300);
        };
        
        // ذخیره reference برای حذف بعدی
        globalSearchInput._searchHandler = searchHandler;
        
        // اضافه کردن event listener
        globalSearchInput.addEventListener('input', searchHandler);
        globalSearchInput.addEventListener('keyup', searchHandler);
        
        // تست اولیه
        console.log('NonBazargahBarnamehServerFilter: Search handler setup completed');
        console.log('NonBazargahBarnamehServerFilter: Input value:', globalSearchInput.value);
        console.log('NonBazargahBarnamehServerFilter: Input placeholder:', globalSearchInput.placeholder);
        
        // اگر مقدار اولیه وجود دارد، جستجو کن
        if (globalSearchInput.value && globalSearchInput.value.trim()) {
            console.log('NonBazargahBarnamehServerFilter: Initial search value detected, applying filters');
            setTimeout(() => {
                this.currentPage = 1;
                this.applyFilters();
            }, 500);
        }
    }
    
    setupFilterButtons() {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const columnType = header.dataset.columnType || 'text';
            
            // skip selection column
            if (columnId === 'select' || columnId === 'selection' || columnId === 'actions') {
                return;
            }
            
            // اضافه کردن دکمه فیلتر
            if (!header.querySelector('.filter-btn')) {
                const filterBtn = document.createElement('button');
                filterBtn.className = 'filter-btn btn btn-sm btn-outline-secondary ms-2';
                filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
                filterBtn.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.showFilterModal(columnId, columnType, header);
                };
                header.appendChild(filterBtn);
            }
            
            // حذف قابلیت مرتب‌سازی مستقیم روی header
            header.style.cursor = 'default';
        });
    }
    
    async showFilterModal(columnId, columnType, headerElement) {
        this.showLoading();
        
        try {
            const serverValues = await this.getColumnValues(columnId);
            this.createFilterModal(columnId, columnType, serverValues, headerElement);
        } catch (error) {
            console.error('خطا در دریافت مقادیر ستون:', error);
            this.showToast('خطا در دریافت مقادیر ستون', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    getColumnIndex(columnId) {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        for (let i = 0; i < headers.length; i++) {
            if (headers[i].dataset.columnId === columnId) {
                return i;
            }
        }
        return -1;
    }
    
    async getColumnValues(columnId) {
        // برای column values همیشه cache رو نادیده بگیر تا فیلترهای جدید اعمال بشه
        try {
            const formData = new FormData();
            formData.append('column_id', columnId);
            formData.append('current_filters', JSON.stringify(this.currentFilters));
            
            const globalSearchInput = document.querySelector('#real-time-search, #global-search, #barnameh-search');
            if (globalSearchInput && globalSearchInput.value) {
                formData.append('global_search', globalSearchInput.value);
            }
            
            formData.append('csrfmiddlewaretoken', this.getCSRFToken());
            
            const response = await fetch(this.columnValuesUrl, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                return data.values || [];
            } else {
                throw new Error(data.message || 'خطا در دریافت مقادیر');
            }
        } catch (error) {
            console.error('خطا در دریافت مقادیر ستون:', error);
            throw error;
        }
    }
    
    createFilterModal(columnId, columnType, serverValues, headerElement) {
        // حذف مودال قبلی اگر وجود دارد
        const existingModal = document.getElementById('filterModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // ایجاد مودال با Bootstrap classes
        const modal = document.createElement('div');
        modal.id = 'filterModal';
        modal.className = 'modal fade filter-modal';
        modal.style.display = 'flex';
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-labelledby', 'filterModalLabel');
        modal.setAttribute('aria-hidden', 'true');
        
        const modalDialog = document.createElement('div');
        modalDialog.className = 'modal-dialog modal-dialog-centered';
        
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        
        // Header مودال
        const modalHeader = document.createElement('div');
        modalHeader.className = 'modal-header';
        
        const modalTitle = document.createElement('h5');
        modalTitle.className = 'modal-title';
        modalTitle.id = 'filterModalLabel';
        modalTitle.innerHTML = `<i class="fas fa-filter me-2"></i>فیلتر ${headerElement.textContent.replace(/[🔽🔼]/g, '').trim()}`;
        
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('aria-label', 'Close');
        closeBtn.onclick = () => modal.remove();
        
        modalHeader.appendChild(modalTitle);
        modalHeader.appendChild(closeBtn);
        
        // Body مودال
        const modalBody = document.createElement('div');
        modalBody.className = 'modal-body';
        
        // نوع فیلتر
        const filterTypeContainer = document.createElement('div');
        filterTypeContainer.className = 'mb-3';
        filterTypeContainer.innerHTML = `
            <label class="form-label">نوع فیلتر:</label>
            <div class="btn-group w-100" role="group">
                <input type="radio" class="btn-check" name="filterType" id="includeType" value="include" checked>
                <label class="btn btn-outline-success" for="includeType">شامل</label>
                
                <input type="radio" class="btn-check" name="filterType" id="excludeType" value="exclude">
                <label class="btn btn-outline-danger" for="excludeType">حذف</label>
            </div>
        `;
        
        // جعبه جستجو
        const searchContainer = document.createElement('div');
        searchContainer.className = 'mb-3';
        searchContainer.innerHTML = `
            <label for="filterSearch" class="form-label">جستجو در مقادیر:</label>
            <input type="text" id="filterSearch" class="form-control" placeholder="تایپ کنید...">
        `;
        
        // دکمه‌های مرتب‌سازی
        const sortContainer = document.createElement('div');
        sortContainer.className = 'mb-3';
        sortContainer.innerHTML = `
            <label class="form-label">مرتب‌سازی:</label>
            <div class="btn-group w-100" role="group">
                <button type="button" class="btn btn-outline-primary sort-btn" data-direction="asc">
                    <i class="fas fa-sort-amount-up me-2"></i>صعودی
                </button>
                <button type="button" class="btn btn-outline-primary sort-btn" data-direction="desc">
                    <i class="fas fa-sort-amount-down me-2"></i>نزولی
                </button>
            </div>
        `;
        
        // اضافه کردن event listener برای دکمه‌های مرتب‌سازی
        const sortButtons = sortContainer.querySelectorAll('.sort-btn');
        sortButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                // حذف کلاس active از همه دکمه‌ها
                sortButtons.forEach(b => b.classList.remove('btn-primary', 'active'));
                sortButtons.forEach(b => b.classList.add('btn-outline-primary'));
                
                // اضافه کردن کلاس active به دکمه کلیک شده
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-primary', 'active');
                
                // اعمال مرتب‌سازی
                const direction = btn.dataset.direction;
                this.toggleSort(columnId, direction);
                modal.remove();
            });
        });
        
        // تنظیم وضعیت فعلی مرتب‌سازی
        if (this.currentSort.column === columnId) {
            const activeBtn = sortContainer.querySelector(`[data-direction="${this.currentSort.direction}"]`);
            if (activeBtn) {
                activeBtn.classList.remove('btn-outline-primary');
                activeBtn.classList.add('btn-primary', 'active');
            }
        }
        
        // لیست مقادیر
        const valuesContainer = document.createElement('div');
        valuesContainer.className = 'values-container';
        valuesContainer.style.maxHeight = '300px';
        valuesContainer.style.overflowY = 'auto';
        
        // ایجاد لیست checkbox ها
        const createValuesList = (values) => {
            valuesContainer.innerHTML = '';
            
            if (!values || values.length === 0) {
                valuesContainer.innerHTML = '<div class="text-muted text-center py-3">مقدار موجود نیست</div>';
                return;
            }
            
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'form-check mb-2 border-bottom pb-2';
            selectAllContainer.innerHTML = `
                <input class="form-check-input" type="checkbox" id="selectAll" checked>
                <label class="form-check-label fw-bold" for="selectAll">
                    انتخاب همه (${values.length})
                </label>
            `;
            valuesContainer.appendChild(selectAllContainer);
            
            const selectAllCheckbox = selectAllContainer.querySelector('#selectAll');
            
            values.forEach((value, index) => {
                const valueContainer = document.createElement('div');
                valueContainer.className = 'form-check';
                
                const checkboxId = `value_${index}`;
                valueContainer.innerHTML = `
                    <input class="form-check-input value-checkbox" type="checkbox" id="${checkboxId}" value="${value}" checked>
                    <label class="form-check-label" for="${checkboxId}">
                        ${value}
                    </label>
                `;
                
                valuesContainer.appendChild(valueContainer);
            });
            
            // مدیریت انتخاب همه
            selectAllCheckbox.addEventListener('change', function() {
                const valueCheckboxes = valuesContainer.querySelectorAll('.value-checkbox');
                valueCheckboxes.forEach(cb => cb.checked = this.checked);
            });
            
            // مدیریت تغییر checkbox های جزئی
            valuesContainer.addEventListener('change', function(e) {
                if (e.target.classList.contains('value-checkbox')) {
                    const allCheckboxes = valuesContainer.querySelectorAll('.value-checkbox');
                    const checkedCheckboxes = valuesContainer.querySelectorAll('.value-checkbox:checked');
                    
                    if (checkedCheckboxes.length === allCheckboxes.length) {
                        selectAllCheckbox.checked = true;
                        selectAllCheckbox.indeterminate = false;
                    } else if (checkedCheckboxes.length === 0) {
                        selectAllCheckbox.checked = false;
                        selectAllCheckbox.indeterminate = false;
                    } else {
                        selectAllCheckbox.checked = false;
                        selectAllCheckbox.indeterminate = true;
                    }
                }
            });
        };
        
        createValuesList(serverValues);
        
        // جستجو در مقادیر
        const searchInput = searchContainer.querySelector('#filterSearch');
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const filteredValues = serverValues.filter(value => 
                value.toString().toLowerCase().includes(searchTerm)
            );
            createValuesList(filteredValues);
        });
        
        modalBody.appendChild(filterTypeContainer);
        modalBody.appendChild(sortContainer);
        modalBody.appendChild(searchContainer);
        modalBody.appendChild(valuesContainer);
        
        // Footer مودال
        const modalFooter = document.createElement('div');
        modalFooter.className = 'modal-footer';
        
        const applyBtn = document.createElement('button');
        applyBtn.type = 'button';
        applyBtn.className = 'btn btn-primary';
        applyBtn.innerHTML = '<i class="fas fa-check me-2"></i>اعمال فیلتر';
        
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'btn btn-warning';
        clearBtn.innerHTML = '<i class="fas fa-times me-2"></i>حذف فیلتر';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-secondary';
        cancelBtn.innerHTML = 'لغو';
        cancelBtn.onclick = () => modal.remove();
        
        // عملیات دکمه‌ها
        applyBtn.onclick = () => {
            const selectedValues = Array.from(valuesContainer.querySelectorAll('.value-checkbox:checked'))
                .map(cb => cb.value);
            
            const filterType = modalBody.querySelector('input[name="filterType"]:checked').value;
            
            if (selectedValues.length > 0) {
                this.currentFilters[columnId] = {
                    values: selectedValues,
                    type: filterType
                };
            } else {
                delete this.currentFilters[columnId];
            }
            
            this.currentPage = 1;
            this.applyFilters();
            modal.remove();
        };
        
        clearBtn.onclick = () => {
            delete this.currentFilters[columnId];
            this.currentPage = 1;
            this.applyFilters();
            modal.remove();
        };
        
        modalFooter.appendChild(applyBtn);
        modalFooter.appendChild(clearBtn);
        modalFooter.appendChild(cancelBtn);
        
        // ترکیب همه قسمت‌ها
        modalContent.appendChild(modalHeader);
        modalContent.appendChild(modalBody);
        modalContent.appendChild(modalFooter);
        modalDialog.appendChild(modalContent);
        modal.appendChild(modalDialog);
        
        // نمایش مودال
        document.body.appendChild(modal);
        modal.style.display = 'block';
        modal.classList.add('show');
        
        // تنظیم فیلتر فعلی
        if (this.currentFilters[columnId]) {
            const currentFilter = this.currentFilters[columnId];
            
            // تنظیم نوع فیلتر
            const typeRadio = modalBody.querySelector(`input[name="filterType"][value="${currentFilter.type}"]`);
            if (typeRadio) typeRadio.checked = true;
            
            // تنظیم مقادیر انتخاب شده
            setTimeout(() => {
                const checkboxes = valuesContainer.querySelectorAll('.value-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = currentFilter.values.includes(cb.value);
                });
                
                // بروزرسانی انتخاب همه
                const selectAllCb = valuesContainer.querySelector('#selectAll');
                const checkedCount = valuesContainer.querySelectorAll('.value-checkbox:checked').length;
                const totalCount = checkboxes.length;
                
                if (checkedCount === totalCount) {
                    selectAllCb.checked = true;
                    selectAllCb.indeterminate = false;
                } else if (checkedCount === 0) {
                    selectAllCb.checked = false;
                    selectAllCb.indeterminate = false;
                } else {
                    selectAllCb.checked = false;
                    selectAllCb.indeterminate = true;
                }
            }, 100);
        }
    }
    
    toggleSort(columnId, direction) {
        this.currentSort = { column: columnId, direction: direction };
        this.currentPage = 1;
        this.applyFilters();
    }
    
    async applyFilters() {
        if (this.isLoading) return;
        
        console.log('NonBazargahBarnamehServerFilter: applyFilters() called');
        this.isLoading = true;
        this.showLoading();
        
        try {
            const formData = new FormData();
            formData.append('filters', JSON.stringify(this.currentFilters));
            formData.append('sort', JSON.stringify(this.currentSort));
            formData.append('page', this.currentPage.toString());
            formData.append('per_page', this.perPage.toString());
            
            // دریافت مقدار جستجوی عمومی
            const globalSearchInput = document.querySelector('#real-time-search, #global-search, #barnameh-search');
            const searchValue = globalSearchInput ? globalSearchInput.value.trim() : '';
            
            if (searchValue) {
                formData.append('global_search', searchValue);
                console.log('NonBazargahBarnamehServerFilter: Adding global search:', searchValue);
            } else {
                console.log('NonBazargahBarnamehServerFilter: No global search value');
            }
            
            formData.append('csrfmiddlewaretoken', this.getCSRFToken());
            
            console.log('NonBazargahBarnamehServerFilter: Sending request to', this.filterUrl);
            console.log('NonBazargahBarnamehServerFilter: Request data:', {
                filters: this.currentFilters,
                sort: this.currentSort,
                page: this.currentPage,
                per_page: this.perPage,
                global_search: searchValue
            });
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData
            });
            
            console.log('NonBazargahBarnamehServerFilter: Response received', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('NonBazargahBarnamehServerFilter: Response data:', data);
            
            if (data.status === 'success') {
                this.updateTableContent(data.data, data);
                this.updateFilterIndicators();
                this.updatePagination(data);
            } else {
                throw new Error(data.message || 'خطا در اعمال فیلتر');
            }
            
        } catch (error) {
            console.error('خطا در اعمال فیلتر:', error);
            this.showToast('خطا در اعمال فیلتر', 'error');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    updateTableContent(barnamehs, pagination) {
        console.log('NonBazargahBarnamehServerFilter: updateTableContent called with:', barnamehs);
        const tbody = this.tableElement.querySelector('tbody');
        if (!tbody) return;
        
        // پاک کردن محتوای فعلی
        tbody.innerHTML = '';
        
        if (!barnamehs || barnamehs.length === 0) {
            tbody.innerHTML = `
                <tr class="no-data-row">
                    <td colspan="100%" class="text-center py-4">
                        <i class="fas fa-search text-muted fa-2x mb-2"></i>
                        <p class="text-muted">هیچ بارنامه‌ای یافت نشد</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        // اضافه کردن ردیف‌های جدید
        barnamehs.forEach((barnameh, index) => {
            console.log(`NonBazargahBarnamehServerFilter: Creating row ${index} for barnameh:`, barnameh);
            const row = this.createTableRow(barnameh);
            tbody.appendChild(row);
        });
        
        // اتصال event listener ها برای bulk edit
        this.connectBulkEditListeners();
        
        // بروزرسانی شمارنده
        this.updateRowCounter(pagination);
    }
    
    createTableRow(barnameh) {
        console.log('NonBazargahBarnamehServerFilter: createTableRow called with barnameh:', barnameh);
        const row = document.createElement('tr');
        row.className = 'animate-fade-in';
        
        // تشخیص ترتیب ستون‌ها بر اساس DOM
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        console.log('NonBazargahBarnamehServerFilter: Headers found:', Array.from(headers).map(h => h.dataset.columnId));
        
        let cellsHtml = '';
        
        // ایجاد سلول‌ها بر اساس ترتیب headers در DOM
        headers.forEach((header, index) => {
            const columnId = header.dataset.columnId;
            const isVisible = window.getComputedStyle(header).display !== 'none';
            
            console.log(`NonBazargahBarnamehServerFilter: Processing column ${index}: ${columnId}, visible: ${isVisible}`);
            
            // ایجاد سلول حتی برای ستون‌های مخفی (اما با style مناسب)
            const cellStyle = isVisible ? '' : ' style="display: none;"';
            
            // استفاده از data-column برای سازگاری با مدیریت ستون‌ها
            const cellDataAttr = ` data-column="${columnId}"`;
            
            switch(columnId) {
                case 'select':
                case 'selection':
                    cellsHtml += `
                        <td${cellDataAttr}${cellStyle}>
                            <input type="checkbox" class="row-checkbox" name="barnameh_ids[]" value="${barnameh.id}" data-id="${barnameh.id}" title="انتخاب این بارنامه" onchange="toggleRowSelection(this)">
                        </td>
                    `;
                    break;
                    
                case 'number':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}><strong>${barnameh.number || 'تعیین نشده'}</strong></td>`;
                    break;
                    
                case 'serial':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.serial || '-'}</td>`;
                    break;
                    
                case 'tonnage':
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${barnameh.tonnage || 0}</td>`;
                    break;
                    
                case 'driver_name':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.driver_name || '-'}</td>`;
                    break;
                    
                case 'driver_phone':
                    cellsHtml += `<td${cellDataAttr} dir="ltr"${cellStyle}>${barnameh.driver_phone || '-'}</td>`;
                    break;
                    
                case 'vehicle_plate':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.vehicle_plate || '-'}</td>`;
                    break;
                    
                case 'receiver_name':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.receiver_name || '-'}</td>`;
                    break;
                    
                case 'destination':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.destination || '-'}</td>`;
                    break;
                    
                case 'barnameh_date':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.barnameh_date || '-'}</td>`;
                    break;
                    
                case 'purchase_number':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}><strong>${barnameh.purchase_number || 'تعیین نشده'}</strong></td>`;
                    break;
                    
                case 'customer':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.customer || '-'}</td>`;
                    break;
                    
                case 'product':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.product || '-'}</td>`;
                    break;
                    
                case 'buyer_name':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.buyer_name || '-'}</td>`;
                    break;
                    
                case 'company_price':
                    const companyPrice = barnameh.company_price || 0;
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${companyPrice.toLocaleString()}</td>`;
                    break;
                    
                case 'customer_price':
                    const customerPrice = barnameh.customer_price || 0;
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${customerPrice.toLocaleString()}</td>`;
                    break;
                    
                case 'total_sales_amount':
                    const totalSales = barnameh.total_sales_amount || 0;
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${totalSales.toLocaleString()}</td>`;
                    break;
                    
                case 'total_purchase_amount':
                    const totalPurchase = barnameh.total_purchase_amount || 0;
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${totalPurchase.toLocaleString()}</td>`;
                    break;
                    
                case 'origin':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.origin || '-'}</td>`;
                    break;
                    
                case 'rent':
                    const rent = barnameh.rent || 0;
                    cellsHtml += `<td${cellDataAttr} class="text-center"${cellStyle}>${rent.toLocaleString()}</td>`;
                    break;
                    
                case 'empty_vehicle_weight':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.empty_vehicle_weight || '-'}</td>`;
                    break;
                    
                case 'loaded_vehicle_weight':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.loaded_vehicle_weight || '-'}</td>`;
                    break;
                    
                case 'final_delivered_weight':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.final_delivered_weight || '-'}</td>`;
                    break;
                    
                case 'vehicle_arrival_time':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.vehicle_arrival_time || '-'}</td>`;
                    break;
                    
                case 'departure_time':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.departure_time || '-'}</td>`;
                    break;
                    
                case 'delivery_time':
                    cellsHtml += `<td${cellDataAttr}${cellStyle}>${barnameh.delivery_time || '-'}</td>`;
                    break;
                    
                case 'actions':
                    cellsHtml += `
                        <td${cellDataAttr}${cellStyle}>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-sm btn-outline-primary">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button type="button" class="btn btn-sm btn-outline-secondary">
                                    <i class="fas fa-edit"></i>
                                </button>
                            </div>
                        </td>
                    `;
                    break;
                    
                default:
                    // برای ستون‌های دینامیک یا ناشناخته
                    const dynamicValue = barnameh[columnId];
                    if (dynamicValue !== undefined) {
                        cellsHtml += `<td${cellDataAttr}${cellStyle}>${dynamicValue || '-'}</td>`;
                    } else {
                        cellsHtml += `<td${cellDataAttr}${cellStyle}>-</td>`;
                    }
                    break;
            }
        });
        
        console.log('NonBazargahBarnamehServerFilter: Final cellsHtml:', cellsHtml);
        row.innerHTML = cellsHtml;
        console.log('NonBazargahBarnamehServerFilter: Created row:', row.outerHTML);
        return row;
    }
    
    updateFilterIndicators() {
        // بروزرسانی نشانگرهای فیلتر
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const filterBtn = header.querySelector('.filter-btn');
            
            if (filterBtn) {
                if (this.currentFilters[columnId]) {
                    filterBtn.className = 'filter-btn btn btn-sm btn-warning ms-2';
                    filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
                } else {
                    filterBtn.className = 'filter-btn btn btn-sm btn-outline-secondary ms-2';
                    filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
                }
            }
            
            // بروزرسانی آیکون مرتب‌سازی
            const currentSortIcon = header.querySelector('.sort-icon');
            if (currentSortIcon) currentSortIcon.remove();
            
            if (this.currentSort.column === columnId) {
                const sortIcon = document.createElement('i');
                sortIcon.className = `fas fa-sort-${this.currentSort.direction === 'asc' ? 'up' : 'down'} sort-icon ms-1`;
                header.appendChild(sortIcon);
            }
        });
        
        // بروزرسانی جعبه وضعیت فیلتر
        this.updateFilterStatusBox();
    }
    
    updateFilterStatusBox() {
        let filterStatusContainer = document.querySelector('#barnameh-filter-status');
        
        if (!filterStatusContainer) {
            // ایجاد container برای وضعیت فیلتر
            filterStatusContainer = document.createElement('div');
            filterStatusContainer.id = 'barnameh-filter-status';
            filterStatusContainer.className = 'filter-status-container mb-3';
            
            const tableContainer = this.tableElement.closest('.table-container') || this.tableElement.parentNode;
            tableContainer.insertBefore(filterStatusContainer, tableContainer.firstChild);
        }
        
        const filterCount = Object.keys(this.currentFilters).length;
        const hasSorting = this.currentSort.column !== null;
        
        if (filterCount === 0 && !hasSorting) {
            filterStatusContainer.innerHTML = '';
            return;
        }
        
        let statusHtml = '<div class="alert alert-info d-flex align-items-center justify-content-between">';
        statusHtml += '<div>';
        statusHtml += '<i class="fas fa-info-circle me-2"></i>';
        
        if (filterCount > 0) {
            statusHtml += `<span>${filterCount} فیلتر فعال</span>`;
        }
        
        if (hasSorting) {
            if (filterCount > 0) statusHtml += ' • ';
            statusHtml += `<span>مرتب‌سازی: ${this.currentSort.column} (${this.currentSort.direction === 'asc' ? 'صعودی' : 'نزولی'})</span>`;
        }
        
        statusHtml += '</div>';
        statusHtml += '<button type="button" class="btn btn-sm btn-outline-danger" id="clear-all-filters">';
        statusHtml += '<i class="fas fa-times me-1"></i>پاک کردن همه';
        statusHtml += '</button>';
        statusHtml += '</div>';
        
        filterStatusContainer.innerHTML = statusHtml;
        
        // اتصال event listener برای پاک کردن همه فیلترها
        this.attachFilterStatusEventListeners(filterStatusContainer);
    }
    
    attachFilterStatusEventListeners(container) {
        const clearAllBtn = container.querySelector('#clear-all-filters');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.currentFilters = {};
                this.currentSort = { column: null, direction: 'asc' };
                this.currentPage = 1;
                this.applyFilters();
            });
        }
    }
    
    updatePagination(pagination) {
        // پیدا کردن یا ایجاد container pagination
        let paginationContainer = document.querySelector('#barnameh-server-pagination');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'barnameh-server-pagination';
            paginationContainer.className = 'pagination-container mt-4';
            
            // اضافه کردن بعد از جدول
            const tableContainer = this.tableElement.closest('.table-container') || this.tableElement.parentNode;
            tableContainer.insertAdjacentElement('afterend', paginationContainer);
        }
        
        // بروزرسانی اطلاعات pagination
        this.updatePaginationInfo(paginationContainer, pagination);
    }
    
    updatePaginationInfo(paginationContainer, pagination) {
        let paginationHtml = '';
        
        // اطلاعات pagination
        paginationHtml += `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <p class="text-muted mb-0">
                        نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} بارنامه
                    </p>
                </div>
                <div class="col-md-6">
                    <nav aria-label="Page navigation">
                        <ul class="pagination justify-content-end mb-0">
        `;
        
        // دکمه قبلی
        if (pagination.has_previous) {
            paginationHtml += `
                <li class="page-item">
                    <button class="page-link" data-page="${pagination.current_page - 1}">
                        <i class="fas fa-chevron-right"></i>
                    </button>
                </li>
            `;
        } else {
            paginationHtml += `
                <li class="page-item disabled">
                    <span class="page-link"><i class="fas fa-chevron-right"></i></span>
                </li>
            `;
        }
        
        // شماره صفحات
        const startPage = Math.max(1, pagination.current_page - 2);
        const endPage = Math.min(pagination.total_pages, pagination.current_page + 2);
        
        if (startPage > 1) {
            paginationHtml += `
                <li class="page-item">
                    <button class="page-link" data-page="1">1</button>
                </li>
            `;
            if (startPage > 2) {
                paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            if (i === pagination.current_page) {
                paginationHtml += `
                    <li class="page-item active">
                        <span class="page-link">${i}</span>
                    </li>
                `;
            } else {
                paginationHtml += `
                    <li class="page-item">
                        <button class="page-link" data-page="${i}">${i}</button>
                    </li>
                `;
            }
        }
        
        if (endPage < pagination.total_pages) {
            if (endPage < pagination.total_pages - 1) {
                paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
            paginationHtml += `
                <li class="page-item">
                    <button class="page-link" data-page="${pagination.total_pages}">${pagination.total_pages}</button>
                </li>
            `;
        }
        
        // دکمه بعدی
        if (pagination.has_next) {
            paginationHtml += `
                <li class="page-item">
                    <button class="page-link" data-page="${pagination.current_page + 1}">
                        <i class="fas fa-chevron-left"></i>
                    </button>
                </li>
            `;
        } else {
            paginationHtml += `
                <li class="page-item disabled">
                    <span class="page-link"><i class="fas fa-chevron-left"></i></span>
                </li>
            `;
        }
        
        paginationHtml += `
                        </ul>
                    </nav>
                </div>
            </div>
        `;
        
        paginationContainer.innerHTML = paginationHtml;
        
        // اتصال event listener ها
        const pageButtons = paginationContainer.querySelectorAll('button[data-page]');
        pageButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                this.currentPage = parseInt(btn.dataset.page);
                this.applyFilters();
            });
        });
    }
    
    connectBulkEditListeners() {
        console.log('NonBazargahBarnamehServerFilter: Connecting bulk edit listeners...');
        
        // همیشه fallback استفاده کن تا مطمئن باشیم که کار می‌کند
        console.log('NonBazargahBarnamehServerFilter: Setting up bulk edit integration...');
        
        // بررسی وجود BulkEditManager و ارسال رویداد
        if (window.bulkEditManager) {
            console.log('NonBazargahBarnamehServerFilter: BulkEditManager found, triggering update...');
            
            // ارسال رویداد برای اطلاع BulkEditManager از تغییر محتوای جدول
            document.dispatchEvent(new CustomEvent('tableContentUpdated', {
                detail: { tableId: this.tableId }
            }));
            
            // بروزرسانی مستقیم panel ها
            setTimeout(() => {
                if (window.bulkEditManager.updateAllControlPanels) {
                    window.bulkEditManager.updateAllControlPanels();
                }
            }, 100);
        }
        
        // همیشه fallback را نیز راه‌اندازی کن
        this.setupFallbackBulkEdit();
    }
    
    setupFallbackBulkEdit() {
        // مدیریت مستقیم checkbox ها در صورت عدم وجود BulkEditManager
        const rowCheckboxes = this.tableElement.querySelectorAll('.row-checkbox');
        rowCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                updateBulkEditPanel();
            });
        });
        
        // اتصال select all checkbox
        const selectAllCheckbox = this.tableElement.querySelector('#selectAllCheckbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const rowCheckboxes = document.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(cb => {
                    cb.checked = this.checked;
                });
                updateBulkEditPanel();
            });
        }
    }
    
    updateRowCounter(pagination) {
        // بروزرسانی شمارنده ردیف‌ها در بالای جدول
        let counterElement = document.querySelector('#barnameh-row-counter');
        
        if (!counterElement) {
            counterElement = document.createElement('div');
            counterElement.id = 'barnameh-row-counter';
            counterElement.className = 'row-counter text-muted small mb-2';
            
            const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
            tableContainer.insertBefore(counterElement, tableContainer.firstChild);
        }
        
        counterElement.innerHTML = `
            <i class="fas fa-list me-1"></i>
            نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} بارنامه
        `;
    }
    
    async loadInitialData() {
        // بارگذاری داده‌های اولیه
        await this.applyFilters();
    }
    
    showLoading() {
        // نمایش loading indicator
        let loadingElement = document.querySelector('#barnameh-table-loading');
        
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.id = 'barnameh-table-loading';
            loadingElement.className = 'table-loading text-center py-4';
            loadingElement.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">در حال بارگذاری...</span>
                </div>
                <p class="mt-2 text-muted">در حال بارگذاری...</p>
            `;
            
            const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
            tableContainer.appendChild(loadingElement);
        }
        
        loadingElement.style.display = 'block';
    }
    
    hideLoading() {
        // مخفی کردن loading indicator
        const loadingElement = document.querySelector('#barnameh-table-loading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
    
    showToast(message, type = 'info') {
        // نمایش toast notification
        const toastContainer = document.querySelector('.toast-container') || document.body;
        
        const toast = document.createElement('div');
        toast.className = `toast show align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // حذف خودکار بعد از 5 ثانیه
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
    
    getCSRFToken() {
        // دریافت CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }
    
    // متد برای همگام‌سازی با مدیریت ستون‌ها
    syncWithColumnManager() {
        // بروزرسانی فیلتر بعد از تغییر ستون‌ها
        this.applyFilters();
    }
    
    // متد برای بروزرسانی ستون‌ها بدون reload کامل
    updateColumnVisibility(columnVisibilityMap) {
        console.log('NonBazargahBarnamehServerFilter: Updating column visibility:', columnVisibilityMap);
        
        // ستون‌های الزامی که نباید مخفی شوند
        const requiredColumns = ['select', 'actions'];
        
        // بروزرسانی header های جدول
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            if (columnVisibilityMap.hasOwnProperty(columnId)) {
                // اگر ستون الزامی است، همیشه نمایش ده
                const isVisible = requiredColumns.includes(columnId) ? true : columnVisibilityMap[columnId];
                header.style.display = isVisible ? 'table-cell' : 'none';
                
                console.log(`NonBazargahBarnamehServerFilter: Column ${columnId} visibility: ${isVisible} (required: ${requiredColumns.includes(columnId)})`);
                
                // بروزرسانی دکمه فیلتر (ستون انتخاب فیلتر ندارد)
                const filterBtn = header.querySelector('.filter-btn');
                if (filterBtn && columnId !== 'select' && columnId !== 'actions') {
                    filterBtn.style.display = isVisible ? '' : 'none';
                }
            }
        });
        
        // بروزرسانی سلول‌های موجود در جدول
        const rows = this.tableElement.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td[data-column]');
            cells.forEach(cell => {
                const columnId = cell.dataset.column;
                if (columnVisibilityMap.hasOwnProperty(columnId)) {
                    // اگر ستون الزامی است، همیشه نمایش ده
                    const isVisible = requiredColumns.includes(columnId) ? true : columnVisibilityMap[columnId];
                    cell.style.display = isVisible ? 'table-cell' : 'none';
                }
            });
        });
    }
}

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    console.log('Non-Bazargah Barnameh Server Filter: DOM loaded');
    
    // راه‌اندازی فیلتر برای جدول بارنامه‌های خارج بازارگاه
    const barnamehTable = document.querySelector('#barnamehsTable');
    if (barnamehTable) {
        console.log('Non-Bazargah Barnameh Server Filter: Table found, initializing...');
        window.nonBazargahBarnamehServerFilter = new NonBazargahBarnamehServerFilter('#barnamehsTable');
        console.log('Non-Bazargah Barnameh Server Filter: Initialized successfully');
        
        // تست جستجوی عمومی
        setTimeout(() => {
            const searchInput = document.querySelector('#real-time-search, #global-search, #barnameh-search');
            if (searchInput) {
                console.log('Non-Bazargah Barnameh Server Filter: Search input found in DOM test');
                console.log('Non-Bazargah Barnameh Server Filter: Search input value:', searchInput.value);
                console.log('Non-Bazargah Barnameh Server Filter: Search input has listener:', searchInput.hasAttribute('data-server-filter-listener'));
            } else {
                console.warn('Non-Bazargah Barnameh Server Filter: Search input NOT found in DOM test');
            }
        }, 1000);
        
    } else {
        console.warn('Non-Bazargah Barnameh Server Filter: Table #barnamehsTable not found');
    }
});
