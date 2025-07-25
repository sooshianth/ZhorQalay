/**
 * کلاس مدیریت فیلتر سمت سرور برای جدول مشتریان
 */
class CustomerServerFilter {
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
        const perPageSelector = document.querySelector('#customerPerPage');
        if (perPageSelector && perPageSelector.value) {
            return parseInt(perPageSelector.value);
        }
        
        return 25; // پیش‌فرض
    }
    
    init() {
        console.log('CustomerServerFilter: init() called');
        console.log('CustomerServerFilter: filterUrl =', this.filterUrl);
        console.log('CustomerServerFilter: columnValuesUrl =', this.columnValuesUrl);
        
        if (!this.filterUrl || !this.columnValuesUrl) {
            console.warn('URL های فیلتر تنظیم نشده‌اند');
            return;
        }
        
        // غیرفعال کردن traditional pagination برای این جدول
        this.disableTraditionalPagination();
        
        this.setupFilterButtons();
        this.setupPerPageSelector();
        this.setupGlobalSearchHandler();
        
        // بارگذاری اولیه داده‌ها 
        setTimeout(() => {
            this.loadInitialData();
        }, 100);
        
        console.log('CustomerServerFilter: init() completed');
    }
    
    disableTraditionalPagination() {
        // علامت‌گذاری جدول به عنوان دارای server filter
        this.tableElement.setAttribute('data-server-filter-active', 'true');
        
        // غیرفعال کردن traditional pagination links
        const traditionalPaginationContainer = document.querySelector('#customerPagination');
        
        if (traditionalPaginationContainer) {
            traditionalPaginationContainer.style.display = 'none';
        }
        
        // غیرفعال کردن traditional per-page selectors
        const traditionalPerPageSelect = document.querySelector('#customerPerPage:not([data-server-filter-listener])');
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
        const existingSelector = document.querySelector('#customerPerPage');
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
        perPageContainer.className = 'per-page-container mb-3 d-flex align-items-center';
        perPageContainer.innerHTML = `
            <label for="customerPerPageFilter" class="form-label me-2">تعداد در هر صفحه:</label>
            <select id="customerPerPageFilter" class="form-select form-select-sm w-auto">
                <option value="5" ${this.perPage === 5 ? 'selected' : ''}>5</option>
                <option value="10" ${this.perPage === 10 ? 'selected' : ''}>10</option>
                <option value="25" ${this.perPage === 25 ? 'selected' : ''}>25</option>
                <option value="50" ${this.perPage === 50 ? 'selected' : ''}>50</option>
                <option value="100" ${this.perPage === 100 ? 'selected' : ''}>100</option>
                <option value="200" ${this.perPage === 200 ? 'selected' : ''}>200</option>
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
        // پیدا کردن input جستجوی سریع
        const globalSearchInput = document.querySelector('#real-time-search, #globalSearch, #global_search, [name="global_search"], [name="search"]');
        
        console.log('CustomerServerFilter: Global search input found:', globalSearchInput);
        console.log('CustomerServerFilter: Input element details:', {
            id: globalSearchInput?.id,
            name: globalSearchInput?.name,
            value: globalSearchInput?.value,
            tagName: globalSearchInput?.tagName
        });
        
        if (globalSearchInput && !globalSearchInput.hasAttribute('data-server-filter-listener')) {
            console.log('CustomerServerFilter: Setting up search listener');
            globalSearchInput.setAttribute('data-server-filter-listener', 'true');
            
            let searchTimeout;
            globalSearchInput.addEventListener('input', (e) => {
                console.log('CustomerServerFilter: Search input changed:', e.target.value);
                clearTimeout(searchTimeout);
                
                // نمایش loading indicator
                const loadingIndicator = document.querySelector('#search-loading');
                if (loadingIndicator) {
                    loadingIndicator.classList.remove('d-none');
                }
                
                searchTimeout = setTimeout(() => {
                    this.currentPage = 1;
                    this.applyFilters();
                    
                    // مخفی کردن loading indicator
                    if (loadingIndicator) {
                        loadingIndicator.classList.add('d-none');
                    }
                }, 500);
            });
        } else if (!globalSearchInput) {
            console.warn('CustomerServerFilter: Global search input not found');
        }
    }
    
    setupFilterButtons() {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const columnType = header.dataset.columnType || 'text';
            
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
            
            // اضافه کردن دکمه مرتب‌سازی
            header.style.cursor = 'pointer';
            header.onclick = (e) => {
                if (e.target.closest('.filter-btn')) return;
                
                let direction = 'asc';
                if (this.currentSort.column === columnId && this.currentSort.direction === 'asc') {
                    direction = 'desc';
                }
                
                this.toggleSort(columnId, direction);
            };
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
    
    async getCurrentTableValues(columnId) {
        const values = new Set();
        const tbody = this.tableElement.querySelector('tbody');
        
        if (!tbody) return [];
        
        const columnIndex = this.getColumnIndex(columnId);
        if (columnIndex === -1) return [];
        
        const rows = tbody.querySelectorAll('tr:not(.no-data-row)');
        rows.forEach(row => {
            const cell = row.cells[columnIndex];
            if (cell) {
                const value = cell.textContent.trim();
                if (value && value !== '-' && value !== 'تعیین نشده') {
                    values.add(value);
                }
            }
        });
        
        return Array.from(values).filter(v => v && v !== '-' && v !== 'تعیین نشده');
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
            
            const globalSearchInput = document.querySelector('#real-time-search, #globalSearch, #global_search');
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
        
        console.log('CustomerServerFilter: applyFilters() called');
        this.isLoading = true;
        this.showLoading();
        
        try {
            const formData = new FormData();
            formData.append('filters', JSON.stringify(this.currentFilters));
            formData.append('sort', JSON.stringify(this.currentSort));
            formData.append('page', this.currentPage.toString());
            formData.append('per_page', this.perPage.toString());
            
            const globalSearchInput = document.querySelector('#real-time-search, #globalSearch, #global_search');
            if (globalSearchInput && globalSearchInput.value) {
                formData.append('global_search', globalSearchInput.value);
            }
            
            formData.append('csrfmiddlewaretoken', this.getCSRFToken());
            
            console.log('CustomerServerFilter: Sending request to', this.filterUrl);
            console.log('CustomerServerFilter: Form data:', Object.fromEntries(formData));
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData
            });
            
            console.log('CustomerServerFilter: Response received', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('CustomerServerFilter: Response data:', data);
            
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
    
    updateTableContent(customers, pagination) {
        console.log('CustomerServerFilter: updateTableContent called with:', customers);
        const tbody = this.tableElement.querySelector('tbody');
        if (!tbody) return;
        
        // پاک کردن محتوای فعلی
        tbody.innerHTML = '';
        
        if (!customers || customers.length === 0) {
            tbody.innerHTML = `
                <tr class="no-data-row">
                    <td colspan="100%" class="text-center py-4">
                        <i class="fas fa-search text-muted fa-2x mb-2"></i>
                        <p class="text-muted">هیچ مشتری یافت نشد</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        // اضافه کردن ردیف‌های جدید
        customers.forEach((customer, index) => {
            console.log(`CustomerServerFilter: Creating row ${index} for customer:`, customer);
            const row = this.createTableRow(customer);
            tbody.appendChild(row);
        });
        
        // اتصال event listener ها
        this.connectEventListeners();
        
        // بروزرسانی شمارنده
        this.updateRowCounter(pagination);
    }
    
    connectEventListeners() {
        // اتصال event listener برای دکمه‌های toggle favorite
        const favoriteButtons = this.tableElement.querySelectorAll('.toggle-favorite-btn');
        favoriteButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                // پیاده‌سازی toggle favorite
                const customerId = this.dataset.customerId;
                // فراخوانی تابع toggle favorite از اسکریپت اصلی
                if (window.toggleFavorite) {
                    window.toggleFavorite(customerId, this);
                }
            });
        });
        
        // اتصال event listener برای checkbox های انتخاب
        const selectionCheckboxes = this.tableElement.querySelectorAll('.customer-checkbox');
        selectionCheckboxes.forEach(cb => {
            cb.addEventListener('change', function() {
                // بروزرسانی شمارنده انتخاب شده‌ها
                if (window.updateSelectionCount) {
                    window.updateSelectionCount();
                }
            });
        });
    }
    
    getStatusBadgeClass(statusText) {
        const statusClasses = {
            'فعال': 'badge bg-success',
            'غیرفعال': 'badge bg-secondary',
            'مسدود': 'badge bg-danger',
            'بله': 'badge bg-success',
            'خیر': 'badge bg-secondary'
        };
        
        return statusClasses[statusText] || 'badge bg-secondary';
    }
    
    createTableRow(customer) {
        console.log('CustomerServerFilter: createTableRow called with customer:', customer);
        const row = document.createElement('tr');
        row.className = 'animate-fade-in';
        
        // تشخیص ترتیب ستون‌ها بر اساس DOM
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        console.log('CustomerServerFilter: Headers found:', Array.from(headers).map(h => h.dataset.columnId));
        
        let cellsHtml = '';
        
        // ایجاد سلول‌ها بر اساس ترتیب headers در DOM
        headers.forEach((header, index) => {
            const columnId = header.dataset.columnId;
            const isVisible = window.getComputedStyle(header).display !== 'none';
            
            console.log(`CustomerServerFilter: Processing column ${index}: ${columnId}, visible: ${isVisible}`);
            
            // ایجاد سلول حتی برای ستون‌های مخفی (اما با style مناسب)
            const cellStyle = isVisible ? '' : ' style="display: none;"';
            
            switch(columnId) {
                case 'selection':
                    cellsHtml += `
                        <td${cellStyle}>
                            <input type="checkbox" class="customer-checkbox" name="customer_ids[]" value="${customer.id}">
                        </td>
                    `;
                    break;
                    
                case 'is_favorite':
                    const favoriteClass = customer.is_favorite ? 'btn-warning' : 'btn-outline-warning';
                    const favoriteIcon = customer.is_favorite ? 'fas fa-star' : 'far fa-star';
                    cellsHtml += `
                        <td${cellStyle}>
                            <button class="btn btn-sm ${favoriteClass} toggle-favorite-btn" data-customer-id="${customer.id}">
                                <i class="${favoriteIcon}"></i>
                            </button>
                        </td>
                    `;
                    break;
                    
                case 'name':
                    cellsHtml += `<td class="fw-bold"${cellStyle}>${customer.name || ''}</td>`;
                    break;
                    
                case 'phone_number':
                    cellsHtml += `<td dir="ltr"${cellStyle}>${customer.phone_number || ''}</td>`;
                    break;
                    
                case 'city':
                    const cityValue = customer.city || '';
                    console.log(`CustomerServerFilter: City value for customer ${customer.id}:`, cityValue);
                    cellsHtml += `<td${cellStyle}>${cityValue}</td>`;
                    break;
                    
                case 'field_of_activity':
                    const activityValue = customer.field_of_activity || '';
                    console.log(`CustomerServerFilter: Activity value for customer ${customer.id}:`, activityValue);
                    cellsHtml += `<td${cellStyle}>${activityValue}</td>`;
                    break;
                    
                case 'purchase_count':
                    cellsHtml += `<td class="text-center"${cellStyle}>${customer.purchase_count || 0}</td>`;
                    break;
                    
                case 'total_purchase_weight':
                    const weight = customer.total_purchase_weight || 0;
                    cellsHtml += `<td class="text-center"${cellStyle}>${weight.toLocaleString()} کیلوگرم</td>`;
                    break;
                    
                case 'purchase_preferences':
                    cellsHtml += `<td${cellStyle}>${customer.purchase_preferences || ''}</td>`;
                    break;
                    
                case 'product_preferences':
                    cellsHtml += `<td${cellStyle}>${customer.product_preferences || ''}</td>`;
                    break;
                    
                case 'last_purchase_date':
                    cellsHtml += `<td${cellStyle}>${customer.last_purchase_date || '-'}</td>`;
                    break;
                    
                case 'is_active':
                    const statusText = customer.is_active ? 'فعال' : 'غیرفعال';
                    const badgeClass = this.getStatusBadgeClass(statusText);
                    cellsHtml += `<td${cellStyle}><span class="${badgeClass}">${statusText}</span></td>`;
                    break;
                    
                case 'created_at':
                    cellsHtml += `<td${cellStyle}>${customer.created_at || ''}</td>`;
                    break;
                    
                case 'updated_at':
                    cellsHtml += `<td${cellStyle}>${customer.updated_at || ''}</td>`;
                    break;
                    
                case 'actions':
                    cellsHtml += `
                        <td${cellStyle}>
                            <div class="btn-group" role="group">
                                <a href="/sales/customer/?customer_id=${customer.id}" class="btn btn-sm btn-primary">
                                    <i class="fas fa-edit"></i>
                                </a>
                                <button class="btn btn-sm btn-info view-details-btn" data-customer-id="${customer.id}">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </div>
                        </td>
                    `;
                    break;
                    
                default:
                    // برای ستون‌های ناشناخته
                    cellsHtml += `<td${cellStyle}>-</td>`;
                    break;
            }
        });
        
        console.log('CustomerServerFilter: Final cellsHtml:', cellsHtml);
        row.innerHTML = cellsHtml;
        console.log('CustomerServerFilter: Created row:', row.outerHTML);
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
        let filterStatusContainer = document.querySelector('#customer-filter-status');
        
        if (!filterStatusContainer) {
            // ایجاد container برای وضعیت فیلتر
            filterStatusContainer = document.createElement('div');
            filterStatusContainer.id = 'customer-filter-status';
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
        let paginationContainer = document.querySelector('#customer-server-pagination');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'customer-server-pagination';
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
                        نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} مشتری
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
    
    updateRowCounter(pagination) {
        // بروزرسانی شمارنده ردیف‌ها در بالای جدول
        let counterElement = document.querySelector('#customer-row-counter');
        
        if (!counterElement) {
            counterElement = document.createElement('div');
            counterElement.id = 'customer-row-counter';
            counterElement.className = 'row-counter text-muted small mb-2';
            
            const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
            tableContainer.insertBefore(counterElement, tableContainer.firstChild);
        }
        
        counterElement.innerHTML = `
            <i class="fas fa-list me-1"></i>
            نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} مشتری
        `;
    }
    
    async loadInitialData() {
        // بارگذاری داده‌های اولیه
        await this.applyFilters();
    }
    
    showLoading() {
        // نمایش loading indicator
        let loadingElement = document.querySelector('#customer-table-loading');
        
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.id = 'customer-table-loading';
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
        const loadingElement = document.querySelector('#customer-table-loading');
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
}

// --- Helper functions for date conversion ---
function gregorianToJalali(gy, gm, gd) {
    var g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334];
    var jy = (gy <= 1600) ? 0 : 979;
    gy -= (gy <= 1600) ? 621 : 1600;
    var gy2 = (gm > 2) ? (gy + 1) : gy;
    var days = (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
        jy += Math.floor((days - 365) / 365);
        days = (days - 365) % 365;
    }
    var jm = (days < 186) ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    var jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
    return [jy, jm, jd];
}

function formatJalaliDateString(gregorianStr) {
    if (!gregorianStr) return '';
    let parts = gregorianStr.split('-');
    if (parts.length !== 3) {
        parts = gregorianStr.split('/');
    }
    if (parts.length !== 3) return gregorianStr;
    let gy = parseInt(parts[0], 10);
    let gm = parseInt(parts[1], 10);
    let gd = parseInt(parts[2], 10);
    if (isNaN(gy) || isNaN(gm) || isNaN(gd)) return gregorianStr;
    let [jy, jm, jd] = gregorianToJalali(gy, gm, gd);
    return `${jy}/${jm.toString().padStart(2, '0')}/${jd.toString().padStart(2, '0')}`;
}

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    console.log('Customer Server Filter: DOM loaded');
    // راه‌اندازی فیلتر برای جدول مشتریان
    const customerTable = document.querySelector('#customersTable');
    if (customerTable) {
        console.log('Customer Server Filter: Table found, initializing...');
        window.customerServerFilter = new CustomerServerFilter('#customersTable');
        console.log('Customer Server Filter: Initialized successfully');
    } else {
        console.warn('Customer Server Filter: Table #customersTable not found');
    }
});
