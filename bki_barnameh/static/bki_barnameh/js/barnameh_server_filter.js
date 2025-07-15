/**
 * Barnameh Server-Side Filter System
 * نسخه بارنامه از سیستم فیلتر سمت سرور
 */

class BarnamehServerFilter {
    constructor(tableSelector) {
        this.tableSelector = tableSelector;
        this.table = document.querySelector(tableSelector);
        this.currentFilters = {};
        this.currentSort = { column: null, direction: null };
        this.currentPage = 1;
        this.perPage = 50;
        this.totalPages = 1;
        this.totalCount = 0;
        this.isLoading = false;
        this.globalSearch = '';
        
        // URLs برای API calls - از config دریافت می‌شود
        this.filterUrl = null;
        this.columnValuesUrl = null;
        
        // محاسبه per_page اولیه از انتخاب کاربر
        this.perPage = this.getInitialPerPage();
        
        this.init();
    }
    
    getInitialPerPage() {
        const perPageSelector = document.getElementById('barnamehPerPage');
        if (perPageSelector) {
            const selectedValue = perPageSelector.value;
            if (selectedValue === 'all') {
                return 10000;
            }
            return parseInt(selectedValue) || 50;
        }
        return 50;
    }
    
    init() {
        console.log('Initializing Barnameh Server Filter...');
        
        if (!this.table) {
            console.error('Table not found:', this.tableSelector);
            return;
        }
        
        // دریافت URLs از server config
        const configEl = document.getElementById('barnameh-server-config');
        if (configEl) {
            this.filterUrl = configEl.dataset.filterUrl;
            this.columnValuesUrl = configEl.dataset.columnValuesUrl;
        } else {
            console.error('Barnameh server config not found');
            return;
        }
        
        // غیرفعال کردن pagination سنتی
        this.disableTraditionalPagination();
        
        // راه‌اندازی event handlers
        this.setupPerPageSelector();
        this.setupGlobalSearchHandler();
        this.setupFilterButtons();
        
        // بارگذاری داده‌های اولیه
        this.loadInitialData();
        
        console.log('Barnameh Server Filter initialized successfully');
    }
    
    disableTraditionalPagination() {
        // غیرفعال کردن لینک‌های pagination سنتی
        const paginationLinks = document.querySelectorAll('#barnamehPagination .pagination a');
        paginationLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const href = link.getAttribute('href');
                if (href) {
                    const urlParams = new URLSearchParams(href.split('?')[1]);
                    const page = parseInt(urlParams.get('page')) || 1;
                    this.currentPage = page;
                    this.applyFilters();
                }
            });
        });
        
        // غیرفعال کردن form‌های pagination
        const paginationForms = document.querySelectorAll('#barnamehPagination form');
        paginationForms.forEach(form => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const page = parseInt(formData.get('page')) || 1;
                this.currentPage = page;
                this.applyFilters();
            });
        });
    }
    
    setupPerPageSelector() {
        const perPageSelector = document.getElementById('barnamehPerPage');
        if (perPageSelector) {
            perPageSelector.addEventListener('change', () => {
                const selectedValue = perPageSelector.value;
                if (selectedValue === 'all') {
                    this.perPage = 10000;
                } else {
                    this.perPage = parseInt(selectedValue) || 50;
                }
                this.currentPage = 1; // بازگشت به صفحه اول
                this.applyFilters();
            });
        }
    }
    
    setupGlobalSearchHandler() {
        // ایجاد input جستجوی سریع اگر وجود ندارد
        let globalSearchInput = document.getElementById('globalBarnamehSearch');
        
        if (!globalSearchInput) {
            // ایجاد container جستجوی سریع
            const searchContainer = document.createElement('div');
            searchContainer.className = 'global-search-container mb-3';
            searchContainer.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="fas fa-search"></i>
                            </span>
                            <input type="text" 
                                   id="globalBarnamehSearch" 
                                   class="form-control" 
                                   placeholder="جستجوی سریع در همه فیلدها..."
                                   autocomplete="off">
                            <button class="btn btn-outline-secondary" type="button" id="clearBarnamehSearch">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            // اضافه کردن قبل از جدول
            const tableContainer = this.table.closest('.table-responsive');
            if (tableContainer) {
                tableContainer.parentNode.insertBefore(searchContainer, tableContainer);
            }
            
            globalSearchInput = document.getElementById('globalBarnamehSearch');
        }
        
        if (globalSearchInput) {
            // Debounce برای جستجو
            let searchTimeout;
            globalSearchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.globalSearch = e.target.value.trim();
                    this.currentPage = 1;
                    this.applyFilters();
                }, 500);
            });
            
            // دکمه پاک کردن جستجو
            const clearButton = document.getElementById('clearBarnamehSearch');
            if (clearButton) {
                clearButton.addEventListener('click', () => {
                    globalSearchInput.value = '';
                    this.globalSearch = '';
                    this.currentPage = 1;
                    this.applyFilters();
                });
            }
        }
    }
    
    setupFilterButtons() {
        const filterableHeaders = this.table.querySelectorAll('th[data-column-id]:not([data-column-id="actions"])');
        
        filterableHeaders.forEach(header => {
            const columnId = header.getAttribute('data-column-id');
            const columnType = header.getAttribute('data-column-type') || 'text';
            
            // پاک کردن محتوای قبلی و ایجاد ساختار جدید
            const originalText = header.textContent.trim();
            header.innerHTML = '';
            
            // ایجاد container برای header
            const headerContainer = document.createElement('div');
            headerContainer.className = 'd-flex justify-content-between align-items-center';
            
            // متن header
            const headerText = document.createElement('span');
            headerText.textContent = originalText;
            headerText.className = 'header-text';
            
            // دکمه فیلتر
            const filterBtn = document.createElement('button');
            filterBtn.className = 'btn btn-sm btn-outline-light filter-btn ms-2';
            filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
            filterBtn.title = `فیلتر ${originalText}`;
            filterBtn.style.cssText = `
                padding: 2px 6px;
                font-size: 11px;
                border-radius: 4px;
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                min-width: 24px;
                height: 24px;
            `;
            
            filterBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.showFilterModal(columnId, columnType, header);
            });
            
            headerContainer.appendChild(headerText);
            headerContainer.appendChild(filterBtn);
            header.appendChild(headerContainer);
        });
    }
    
    async showFilterModal(columnId, columnType, headerElement) {
        console.log(`Showing filter modal for column: ${columnId}`);
        
        this.showLoading();
        
        try {
            // دریافت مقادیر از سرور
            const serverValues = await this.getColumnValues(columnId);
            console.log(`Retrieved ${serverValues.length} values for column ${columnId}`);
            
            // ایجاد modal
            this.createFilterModal(columnId, columnType, serverValues, headerElement);
            
        } catch (error) {
            console.error('Error loading filter modal:', error);
            this.showToast('خطا در بارگذاری فیلتر', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    createFilterModal(columnId, columnType, serverValues, headerElement) {
        // حذف modal قبلی
        const existingModal = document.getElementById('barnamehFilterModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // دریافت فیلتر فعلی برای این ستون
        const currentFilter = this.currentFilters[columnId];
        const currentValues = currentFilter ? currentFilter.values : [];
        const currentType = currentFilter ? currentFilter.type : 'include';
        
        // محاسبه آمار
        const totalValues = serverValues.length;
        const selectedValues = currentValues.length;
        
        // ایجاد modal جدید
        const modal = document.createElement('div');
        modal.id = 'barnamehFilterModal';
        modal.className = 'modal fade';
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-hidden', 'true');
        modal.style.zIndex = '9999';
        
        const headerText = headerElement.querySelector('.header-text')?.textContent || headerElement.textContent;
        
        modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-filter me-2"></i>
                            فیلتر ستون: ${headerText}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- آمار فیلتر -->
                        <div class="filter-stats mb-3 p-3 bg-light rounded">
                            <div class="row text-center">
                                <div class="col-4">
                                    <h6 class="mb-1">${totalValues}</h6>
                                    <small class="text-muted">مقادیر موجود</small>
                                </div>
                                <div class="col-4">
                                    <h6 class="mb-1" id="selectedCount">${selectedValues}</h6>
                                    <small class="text-muted">انتخاب شده</small>
                                </div>
                                <div class="col-4">
                                    <h6 class="mb-1">${totalValues - selectedValues}</h6>
                                    <small class="text-muted">انتخاب نشده</small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- نوع فیلتر -->
                        <div class="filter-type mb-3">
                            <label class="form-label fw-bold">نوع فیلتر:</label>
                            <div class="btn-group w-100" role="group">
                                <input type="radio" class="btn-check" name="filterType" id="includeType" value="include" ${currentType === 'include' ? 'checked' : ''}>
                                <label class="btn btn-outline-success" for="includeType">
                                    <i class="fas fa-check me-1"></i>شامل موارد انتخابی
                                </label>
                                
                                <input type="radio" class="btn-check" name="filterType" id="excludeType" value="exclude" ${currentType === 'exclude' ? 'checked' : ''}>
                                <label class="btn btn-outline-danger" for="excludeType">
                                    <i class="fas fa-times me-1"></i>بجز موارد انتخابی
                                </label>
                            </div>
                        </div>
                        
                        <!-- جستجو در مقادیر -->
                        <div class="search-container mb-3">
                            <div class="input-group">
                                <span class="input-group-text">
                                    <i class="fas fa-search"></i>
                                </span>
                                <input type="text" 
                                       class="form-control" 
                                       id="valueSearchInput" 
                                       placeholder="جستجو در مقادیر...">
                                <button class="btn btn-outline-secondary" type="button" id="clearValueSearch">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                        
                        <!-- دکمه‌های کنترل -->
                        <div class="control-buttons mb-3">
                            <div class="btn-group w-100" role="group">
                                <button type="button" class="btn btn-outline-primary" id="selectAllBtn">
                                    <i class="fas fa-check-square me-1"></i>انتخاب همه
                                </button>
                                <button type="button" class="btn btn-outline-secondary" id="deselectAllBtn">
                                    <i class="fas fa-square me-1"></i>لغو همه
                                </button>
                                <button type="button" class="btn btn-outline-info" id="invertSelectionBtn">
                                    <i class="fas fa-exchange-alt me-1"></i>معکوس کردن
                                </button>
                            </div>
                        </div>
                        
                        <!-- لیست مقادیر -->
                        <div class="values-container">
                            <div class="values-list border rounded p-2" 
                                 style="max-height: 300px; overflow-y: auto;" 
                                 id="valuesList">
                                <!-- مقادیر اینجا بارگذاری می‌شوند -->
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="fas fa-times me-1"></i>انصراف
                        </button>
                        <button type="button" class="btn btn-warning" id="clearFilterBtn">
                            <i class="fas fa-eraser me-1"></i>پاک کردن فیلتر
                        </button>
                        <button type="button" class="btn btn-primary" id="applyFilterBtn">
                            <i class="fas fa-check me-1"></i>اعمال فیلتر
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // اضافه کردن به DOM
        document.body.appendChild(modal);
        
        // بارگذاری مقادیر
        const valuesList = modal.querySelector('#valuesList');
        this.loadValuesIntoModal(serverValues, currentValues, valuesList);
        
        // Event handlers
        this.setupModalEventHandlers(modal, columnId);
        
        // نمایش modal
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
        
        // حذف modal هنگام بسته شدن
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    }
    
    setupModalEventHandlers(modal, columnId) {
        const valuesList = modal.querySelector('#valuesList');
        const valueSearchInput = modal.querySelector('#valueSearchInput');
        const selectAllBtn = modal.querySelector('#selectAllBtn');
        const deselectAllBtn = modal.querySelector('#deselectAllBtn');
        const invertSelectionBtn = modal.querySelector('#invertSelectionBtn');
        const clearFilterBtn = modal.querySelector('#clearFilterBtn');
        const applyFilterBtn = modal.querySelector('#applyFilterBtn');
        const clearValueSearch = modal.querySelector('#clearValueSearch');
        
        // Event handlers برای جستجو در مقادیر
        const searchHandler = () => {
            const searchTerm = valueSearchInput.value.toLowerCase();
            const checkboxes = valuesList.querySelectorAll('.form-check');
            
            checkboxes.forEach(checkboxContainer => {
                const label = checkboxContainer.querySelector('.form-check-label');
                const text = label.textContent.toLowerCase();
                
                if (text.includes(searchTerm)) {
                    checkboxContainer.style.display = 'block';
                } else {
                    checkboxContainer.style.display = 'none';
                }
            });
        };
        
        let searchTimeout;
        valueSearchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(searchHandler, 300);
        });
        
        // پاک کردن جستجو
        clearValueSearch.addEventListener('click', () => {
            valueSearchInput.value = '';
            searchHandler();
        });
        
        // دکمه‌های کنترل
        selectAllBtn.addEventListener('click', () => {
            const visibleCheckboxes = valuesList.querySelectorAll('.form-check:not([style*="display: none"]) input[type="checkbox"]');
            visibleCheckboxes.forEach(cb => cb.checked = true);
            this.updateSelectedCount();
        });
        
        deselectAllBtn.addEventListener('click', () => {
            const visibleCheckboxes = valuesList.querySelectorAll('.form-check:not([style*="display: none"]) input[type="checkbox"]');
            visibleCheckboxes.forEach(cb => cb.checked = false);
            this.updateSelectedCount();
        });
        
        invertSelectionBtn.addEventListener('click', () => {
            const visibleCheckboxes = valuesList.querySelectorAll('.form-check:not([style*="display: none"]) input[type="checkbox"]');
            visibleCheckboxes.forEach(cb => cb.checked = !cb.checked);
            this.updateSelectedCount();
        });
        
        // پاک کردن فیلتر
        clearFilterBtn.addEventListener('click', () => {
            delete this.currentFilters[columnId];
            this.applyFilters();
            bootstrap.Modal.getInstance(modal).hide();
        });
        
        // اعمال فیلتر
        applyFilterBtn.addEventListener('click', () => {
            const selectedValues = [];
            const checkedBoxes = valuesList.querySelectorAll('input[type="checkbox"]:checked');
            
            checkedBoxes.forEach(cb => {
                selectedValues.push(cb.value);
            });
            
            const filterType = modal.querySelector('input[name="filterType"]:checked').value;
            
            if (selectedValues.length > 0) {
                this.currentFilters[columnId] = {
                    values: selectedValues,
                    type: filterType
                };
            } else {
                delete this.currentFilters[columnId];
            }
            
            this.currentPage = 1; // بازگشت به صفحه اول
            this.applyFilters();
            bootstrap.Modal.getInstance(modal).hide();
        });
    }
    
    loadValuesIntoModal(serverValues, currentValues, container) {
        container.innerHTML = '';
        
        if (serverValues.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-3">هیچ مقداری یافت نشد</p>';
            return;
        }
        
        serverValues.forEach(valueObj => {
            const value = valueObj.value || valueObj;
            const display = valueObj.display || value;
            const isChecked = currentValues.includes(value);
            
            const checkboxHtml = `
                <div class="form-check mb-2">
                    <input class="form-check-input" type="checkbox" 
                           value="${value}" id="val_${value}" ${isChecked ? 'checked' : ''}>
                    <label class="form-check-label w-100" for="val_${value}" 
                           style="cursor: pointer; padding: 5px 0;">
                        ${display}
                    </label>
                </div>
            `;
            
            container.insertAdjacentHTML('beforeend', checkboxHtml);
        });
        
        // اضافه کردن event listener برای تغییر selection count
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSelectedCount();
            });
        });
        
        this.updateSelectedCount();
    }
    
    updateSelectedCount() {
        const modal = document.getElementById('barnamehFilterModal');
        if (!modal) return;
        
        const checkedBoxes = modal.querySelectorAll('#valuesList input[type="checkbox"]:checked');
        const selectedCountElement = modal.querySelector('#selectedCount');
        
        if (selectedCountElement) {
            selectedCountElement.textContent = checkedBoxes.length;
        }
    }
    
    async getColumnValues(columnId) {
        try {
            const formData = new FormData();
            formData.append('column_id', columnId);
            formData.append('current_filters', JSON.stringify(this.currentFilters));
            formData.append('global_search', this.globalSearch);
            
            // اضافه کردن CSRF token
            const csrfToken = this.getCSRFToken();
            if (csrfToken) {
                formData.append('csrfmiddlewaretoken', csrfToken);
            }
            
            const response = await fetch(this.columnValuesUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                return data.values || [];
            } else {
                throw new Error(data.message || 'خطا در دریافت مقادیر ستون');
            }
            
        } catch (error) {
            console.error('Error fetching column values:', error);
            this.showToast('خطا در دریافت مقادیر ستون', 'error');
            return [];
        }
    }
    
    async applyFilters() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            const formData = new FormData();
            formData.append('filters', JSON.stringify(this.currentFilters));
            formData.append('sort', JSON.stringify(this.currentSort));
            formData.append('page', this.currentPage.toString());
            formData.append('per_page', this.perPage.toString());
            formData.append('global_search', this.globalSearch);
            
            // اضافه کردن CSRF token
            const csrfToken = this.getCSRFToken();
            if (csrfToken) {
                formData.append('csrfmiddlewaretoken', csrfToken);
            }
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateTableContent(data.data, {
                    current_page: data.current_page,
                    total_pages: data.total_pages,
                    count: data.total_count,
                    has_next: data.has_next,
                    has_previous: data.has_previous
                });
                this.updateFilterIndicators();
                this.updateFilterStatusBox();
                
                // به‌روزرسانی اطلاعات pagination
                this.totalPages = data.total_pages;
                this.totalCount = data.total_count;
                
                this.showToast(`${data.data.length} بارنامه یافت شد`, 'success');
            } else {
                throw new Error(data.message || 'خطا در اعمال فیلتر');
            }
            
        } catch (error) {
            console.error('Error applying filters:', error);
            this.showToast('خطا در اعمال فیلتر', 'error');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    updateTableContent(data, pagination) {
        const tbody = this.table.querySelector('tbody');
        if (!tbody) return;
        
        // پاک کردن محتوای فعلی
        tbody.innerHTML = '';
        
        if (data.length === 0) {
            // نمایش پیام عدم وجود داده
            const colCount = this.table.querySelectorAll('thead th').length;
            tbody.innerHTML = `
                <tr>
                    <td colspan="${colCount}" class="text-center py-4">
                        <i class="fas fa-inbox text-muted" style="font-size: 3rem;"></i>
                        <p class="text-muted mt-2">هیچ بارنامه‌ای یافت نشد</p>
                    </td>
                </tr>
            `;
        } else {
            // اضافه کردن ردیف‌های جدید
            data.forEach(barnameh => {
                const row = this.generateTableRow(barnameh, this.getSelectedColumns());
                tbody.appendChild(row);
            });
        }
        
        // به‌روزرسانی pagination
        this.updatePagination(pagination);
        
        // اتصال event listener‌های جدید
        this.connectEventListeners();
    }
    
    generateTableRow(barnameh, visibleColumns) {
        const row = document.createElement('tr');
        row.className = 'align-middle barnameh-row';
        row.setAttribute('data-id', barnameh.id);
        
        // تنظیم data attributes برای سطر
        Object.keys(barnameh).forEach(key => {
            if (barnameh[key] !== null && barnameh[key] !== undefined) {
                row.setAttribute(`data-${key.replace(/_/g, '-')}`, barnameh[key]);
            }
        });
        
        let rowHtml = `
            <td class="text-center">
                <input type="checkbox" class="row-checkbox" data-id="${barnameh.id}" 
                       value="${barnameh.id}"
                       style="width: 18px; height: 18px; cursor: pointer;" 
                       onchange="toggleRowSelection(this)">
            </td>
        `;
        
        visibleColumns.forEach(columnId => {
            if (columnId === 'number') {
                rowHtml += `<td class="column-number">${barnameh.number || "-"}</td>`;
            } else if (columnId === 'serial') {
                rowHtml += `<td class="column-serial">${barnameh.serial || "-"}</td>`;
            } else if (columnId === 'tonnage') {
                rowHtml += `<td class="column-tonnage">${barnameh.tonnage || "-"}</td>`;
            } else if (columnId === 'status') {
                const statusText = barnameh.status_display || barnameh.status || "";
                const statusClass = this.getStatusBadgeClass(statusText);
                rowHtml += `<td class="column-status">
                    <span class="badge rounded-pill ${statusClass}">${statusText}</span>
                </td>`;
            } else if (columnId === 'driver_name') {
                rowHtml += `<td class="column-driver_name">${barnameh.driver_name || "-"}</td>`;
            } else if (columnId === 'driver_phone') {
                rowHtml += `<td class="column-driver_phone">${barnameh.driver_phone || "-"}</td>`;
            } else if (columnId === 'vehicle_plate') {
                rowHtml += `<td class="column-vehicle_plate">${barnameh.vehicle_plate || "-"}</td>`;
            } else if (columnId === 'receiver_name') {
                rowHtml += `<td class="column-receiver_name">${barnameh.receiver_name || "-"}</td>`;
            } else if (columnId === 'destination') {
                rowHtml += `<td class="column-destination">${barnameh.destination || "-"}</td>`;
            } else if (columnId === 'barnameh_date') {
                rowHtml += `<td class="column-barnameh_date">${barnameh.barnameh_date || "-"}</td>`;
            } else if (columnId === 'transport_date') {
                rowHtml += `<td class="column-transport_date">${barnameh.transport_date || "-"}</td>`;
            } else if (columnId === 'purchase_number') {
                rowHtml += `<td class="column-purchase_number">${barnameh.purchase_number || "-"}</td>`;
            } else if (columnId === 'shenase_takhsis_code') {
                rowHtml += `<td class="column-shenase_takhsis_code">${barnameh.shenase_takhsis_code || "-"}</td>`;
            } else if (columnId === 'cargo') {
                rowHtml += `<td class="column-cargo">${barnameh.cargo || "-"}</td>`;
            } else if (columnId === 'company_price') {
                rowHtml += `<td class="column-company_price">${barnameh.company_price || "-"}</td>`;
            } else if (columnId === 'customer_price') {
                rowHtml += `<td class="column-customer_price">${barnameh.customer_price || "-"}</td>`;
            } else if (columnId === 'total_sales_amount') {
                rowHtml += `<td class="column-total_sales_amount">${barnameh.total_sales_amount || "-"}</td>`;
            } else if (columnId === 'buyer_national_code') {
                rowHtml += `<td class="column-buyer_national_code">${barnameh.buyer_national_code || "-"}</td>`;
            } else if (columnId === 'buyer_postal_code') {
                rowHtml += `<td class="column-buyer_postal_code">${barnameh.buyer_postal_code || "-"}</td>`;
            } else if (columnId === 'buyer_address') {
                rowHtml += `<td class="column-buyer_address">${barnameh.buyer_address || "-"}</td>`;
            } else if (columnId === 'demand_amount') {
                rowHtml += `<td class="column-demand_amount">${barnameh.demand_amount || "-"}</td>`;
            } else if (columnId === 'importer') {
                rowHtml += `<td class="column-importer">${barnameh.importer || "-"}</td>`;
            } else if (columnId === 'product_type') {
                rowHtml += `<td class="column-product_type">${barnameh.product_type || "-"}</td>`;
            } else if (columnId === 'successful_send_date') {
                rowHtml += `<td class="column-successful_send_date">${barnameh.successful_send_date || "-"}</td>`;
            } else if (columnId === 'is_sent_to_bki') {
                const isSentToBki = barnameh.is_sent_to_bki;
                rowHtml += `<td class="column-is_sent_to_bki">
                    ${isSentToBki ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'factor_sodoor_season') {
                rowHtml += `<td class="column-factor_sodoor_season">${barnameh.factor_sodoor_season || "-"}</td>`;
            } else if (columnId === 'is_factored') {
                const isFactored = barnameh.is_factored;
                rowHtml += `<td class="column-is_factored">
                    ${isFactored ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'is_created_by_excel') {
                const isCreatedByExcel = barnameh.is_created_by_excel;
                rowHtml += `<td class="column-is_created_by_excel">
                    ${isCreatedByExcel ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'created_at') {
                rowHtml += `<td class="column-created_at">${barnameh.created_at || "-"}</td>`;
            } else if (columnId === 'actions') {
                rowHtml += `<td class="text-center">
                    <div class="btn-group">
                        <a href="/bki_barnameh/detail/${barnameh.id}/" 
                           class="btn btn-info btn-sm rounded-circle" 
                           data-bs-toggle="tooltip" title="مشاهده جزئیات">
                            <i class="fas fa-eye"></i>
                        </a>
                        ${!barnameh.is_sent_to_bki ? `
                            <a href="/bki_barnameh/edit/${barnameh.id}/" 
                               class="btn btn-warning btn-sm rounded-circle ms-1" 
                               data-bs-toggle="tooltip" title="ویرایش">
                                <i class="fas fa-edit"></i>
                            </a>
                            <form action="/bki_barnameh/delete/${barnameh.id}/" method="post" 
                                  class="d-inline" 
                                  onsubmit="return confirm('آیا از حذف این بارنامه اطمینان دارید؟');">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${this.getCSRFToken()}">
                                <button type="submit" class="btn btn-danger btn-sm rounded-circle ms-1" 
                                        data-bs-toggle="tooltip" title="حذف">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </form>
                            ${barnameh.status === 'BARNAMEH_COMPLETE' ? `
                                <form action="/bki_barnameh/send_to_bki/${barnameh.id}/" method="post" class="d-inline">
                                    <input type="hidden" name="csrfmiddlewaretoken" value="${this.getCSRFToken()}">
                                    <button type="submit" class="btn btn-primary btn-sm rounded-circle ms-1" 
                                            data-bs-toggle="tooltip" title="ارسال به بازارگاه">
                                        <i class="fas fa-paper-plane"></i>
                                    </button>
                                </form>
                            ` : ''}
                        ` : `
                            <a href="/bki_barnameh/edit_in_bki/${barnameh.id}/" 
                               class="btn btn-warning btn-sm rounded-circle ms-1" 
                               data-bs-toggle="tooltip" title="ویرایش در بازارگاه">
                                <i class="fas fa-pencil-alt"></i>
                            </a>
                        `}
                        <button type="button" class="btn btn-outline-success btn-sm item-history-btn ms-1" 
                                data-id="${barnameh.id}"
                                data-barnameh-number="${barnameh.number || ''}"
                                data-barnameh-serial="${barnameh.serial || ''}"
                                title="تاریخچه تغییرات ${barnameh.number || ''}/${barnameh.serial || ''}">
                            <i class="fas fa-history"></i>
                        </button>
                    </div>
                </td>`;
            }
        });
        
        row.innerHTML = rowHtml;
        return row;
    }
    
    getStatusBadgeClass(statusText) {
        const statusClasses = {
            'بارنامه ناقص': 'bg-warning text-dark',
            'بارنامه کامل': 'bg-success',
            'ارسال شده به بازارگاه': 'bg-primary',
            'BARNAMEH_INCOMPLETE': 'bg-warning text-dark',
            'BARNAMEH_COMPLETE': 'bg-success',
            'PURCHASE_CLOSED': 'bg-primary'
        };
        
        return statusClasses[statusText] || 'bg-secondary';
    }
    
    connectEventListeners() {
        // اتصال event listener‌ها برای checkbox‌ها و سایر عناصر
        const checkboxes = this.table.querySelectorAll('.row-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                // به‌روزرسانی شمارنده انتخاب شده‌ها
                this.updateSelectionCount();
                // فعال سازی bulk edit controls
                this.updateBulkEditControls();
            });
        });
        
        // اتصال event listener برای select-all checkbox
        const selectAllCheckbox = document.querySelector('.select-all-checkbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', () => {
                const isChecked = selectAllCheckbox.checked;
                const allCheckboxes = this.table.querySelectorAll('.row-checkbox');
                
                allCheckboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                });
                
                this.updateSelectionCount();
                this.updateBulkEditControls();
            });
        }
        
        // اتصال tooltips
        const tooltipElements = this.table.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipElements.forEach(element => {
            new bootstrap.Tooltip(element);
        });
    }
    
    updateBulkEditControls() {
        // به‌روزرسانی کنترل‌های ویرایش گروهی
        const checkedBoxes = this.table.querySelectorAll('.row-checkbox:checked');
        const bulkControls = document.querySelector('.bulk-edit-controls');
        
        if (bulkControls) {
            if (checkedBoxes.length > 0) {
                bulkControls.style.display = 'block';
                
                // به‌روزرسانی شمارنده
                const countElement = bulkControls.querySelector('.count');
                if (countElement) {
                    countElement.textContent = checkedBoxes.length;
                }
            } else {
                bulkControls.style.display = 'none';
            }
        }
    }
    
    updateFilterIndicators() {
        // به‌روزرسانی اندیکاتورهای فیلتر در header
        const headers = this.table.querySelectorAll('th[data-column-id]');
        
        headers.forEach(header => {
            const columnId = header.getAttribute('data-column-id');
            const filterButton = header.querySelector('.filter-btn');
            
            if (filterButton) {
                const hasFilter = this.currentFilters.hasOwnProperty(columnId);
                
                if (hasFilter) {
                    // اضافه کردن اندیکاتور فیلتر فعال
                    filterButton.classList.add('active');
                    filterButton.style.cssText = `
                        padding: 2px 6px;
                        font-size: 11px;
                        border-radius: 4px;
                        background: rgba(255, 193, 7, 0.8);
                        border: 1px solid #ffc107;
                        color: #212529;
                        min-width: 24px;
                        height: 24px;
                    `;
                    
                    const filterCount = this.currentFilters[columnId].values.length;
                    const filterType = this.currentFilters[columnId].type;
                    
                    let icon = filterType === 'include' ? '✓' : '✗';
                    filterButton.innerHTML = `${icon} ${filterCount}`;
                    filterButton.title = `فیلتر فعال: ${filterCount} مورد ${filterType === 'include' ? 'انتخاب شده' : 'حذف شده'}`;
                } else {
                    // حذف اندیکاتور فیلتر
                    filterButton.classList.remove('active');
                    filterButton.style.cssText = `
                        padding: 2px 6px;
                        font-size: 11px;
                        border-radius: 4px;
                        background: rgba(255, 255, 255, 0.2);
                        border: 1px solid rgba(255, 255, 255, 0.3);
                        color: white;
                        min-width: 24px;
                        height: 24px;
                    `;
                    
                    filterButton.innerHTML = '<i class="fas fa-filter"></i>';
                    filterButton.title = `فیلتر ${header.textContent.trim()}`;
                }
            }
        });
    }
    
    updateFilterStatusBox() {
        // ایجاد یا به‌روزرسانی جعبه وضعیت فیلتر
        let statusBox = document.getElementById('filterStatusBox');
        
        const activeFiltersCount = Object.keys(this.currentFilters).length;
        const hasGlobalSearch = this.globalSearch.length > 0;
        
        if (activeFiltersCount === 0 && !hasGlobalSearch) {
            // حذف جعبه اگر فیلتری فعال نیست
            if (statusBox) {
                statusBox.remove();
            }
            return;
        }
        
        if (!statusBox) {
            // ایجاد جعبه جدید
            statusBox = document.createElement('div');
            statusBox.id = 'filterStatusBox';
            statusBox.className = 'alert alert-info d-flex justify-content-between align-items-center mb-3';
            
            // اضافه کردن قبل از جدول
            const tableContainer = this.table.closest('.table-responsive');
            if (tableContainer) {
                tableContainer.parentNode.insertBefore(statusBox, tableContainer);
            }
        }
        
        // ایجاد محتوای جعبه
        let content = '<div class="filter-status-content d-flex align-items-center flex-wrap gap-2">';
        content += '<i class="fas fa-filter text-primary me-2"></i>';
        
        if (hasGlobalSearch) {
            content += `<span class="badge bg-primary me-2">
                <i class="fas fa-search me-1"></i>جستجو: "${this.globalSearch}"
                <button type="button" class="btn-close btn-close-white btn-sm ms-1" 
                        onclick="clearGlobalSearch()" aria-label="پاک کردن جستجو"></button>
            </span>`;
        }
        
        if (activeFiltersCount > 0) {
            content += `<span class="me-2">فیلترهای فعال (${activeFiltersCount}):</span>`;
            
            Object.entries(this.currentFilters).forEach(([columnId, filter]) => {
                const columnName = this.getColumnName(columnId);
                const typeIcon = filter.type === 'include' ? '✓' : '✗';
                const typeText = filter.type === 'include' ? 'شامل' : 'بجز';
                
                content += `<span class="badge bg-secondary me-1">
                    ${columnName}: ${typeIcon} ${filter.values.length} مورد (${typeText})
                    <button type="button" class="btn-close btn-close-white btn-sm ms-1" 
                            onclick="removeFilter('${columnId}')" aria-label="حذف فیلتر"></button>
                </span>`;
            });
        }
        
        content += '</div>';
        
        content += `<div class="filter-status-actions">
            <button type="button" class="btn btn-sm btn-outline-danger" onclick="clearAllFilters()">
                <i class="fas fa-times me-1"></i>پاک کردن همه فیلترها
            </button>
        </div>`;
        
        statusBox.innerHTML = content;
        
        // اتصال event listener‌ها
        this.attachFilterStatusEventListeners(statusBox);
    }
    
    attachFilterStatusEventListeners(container) {
        // تعریف توابع سراسری برای استفاده در onclick
        window.clearGlobalSearch = () => {
            const globalSearchInput = document.getElementById('globalBarnamehSearch');
            if (globalSearchInput) {
                globalSearchInput.value = '';
            }
            this.globalSearch = '';
            this.currentPage = 1;
            this.applyFilters();
        };
        
        window.removeFilter = (columnId) => {
            delete this.currentFilters[columnId];
            this.currentPage = 1;
            this.applyFilters();
        };
        
        window.clearAllFilters = () => {
            this.currentFilters = {};
            this.globalSearch = '';
            const globalSearchInput = document.getElementById('globalBarnamehSearch');
            if (globalSearchInput) {
                globalSearchInput.value = '';
            }
            this.currentPage = 1;
            this.applyFilters();
        };
    }
    
    updatePagination(pagination) {
        const paginationContainer = document.getElementById('barnamehPagination');
        if (!paginationContainer) return;
        
        this.currentPage = pagination.current_page;
        this.totalPages = pagination.total_pages;
        this.totalCount = pagination.count;
        
        // به‌روزرسانی اطلاعات pagination
        this.updatePaginationInfo(paginationContainer, pagination);
        
        // به‌روزرسانی لینک‌های pagination
        const paginationNav = paginationContainer.querySelector('nav');
        if (paginationNav) {
            let paginationHtml = '<ul class="pagination justify-content-center">';
            
            // دکمه صفحه اول
            if (pagination.has_previous) {
                paginationHtml += `
                    <li class="page-item">
                        <a class="page-link" href="#" data-page="1">
                            <i class="fas fa-angle-double-right"></i> اول
                        </a>
                    </li>
                    <li class="page-item">
                        <a class="page-link" href="#" data-page="${pagination.current_page - 1}">
                            <i class="fas fa-angle-right"></i> قبلی
                        </a>
                    </li>
                `;
            }
            
            // شماره صفحات
            const startPage = Math.max(1, pagination.current_page - 2);
            const endPage = Math.min(pagination.total_pages, pagination.current_page + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                const isActive = i === pagination.current_page;
                paginationHtml += `
                    <li class="page-item ${isActive ? 'active' : ''}">
                        <a class="page-link" href="#" data-page="${i}">${i}</a>
                    </li>
                `;
            }
            
            // دکمه صفحه آخر
            if (pagination.has_next) {
                paginationHtml += `
                    <li class="page-item">
                        <a class="page-link" href="#" data-page="${pagination.current_page + 1}">
                            بعدی <i class="fas fa-angle-left"></i>
                        </a>
                    </li>
                    <li class="page-item">
                        <a class="page-link" href="#" data-page="${pagination.total_pages}">
                            آخر <i class="fas fa-angle-double-left"></i>
                        </a>
                    </li>
                `;
            }
            
            paginationHtml += '</ul>';
            paginationNav.innerHTML = paginationHtml;
            
            // اتصال event listener‌ها
            const pageLinks = paginationNav.querySelectorAll('a[data-page]');
            pageLinks.forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const page = parseInt(link.getAttribute('data-page'));
                    if (page && page !== this.currentPage) {
                        this.currentPage = page;
                        this.applyFilters();
                    }
                });
            });
        }
        
        // به‌روزرسانی شمارنده ردیف‌ها
        this.updateRowCounter(pagination);
    }
    
    updatePaginationInfo(paginationContainer, pagination) {
        const infoElement = paginationContainer.querySelector('.pagination-details span');
        if (infoElement) {
            const startIndex = ((pagination.current_page - 1) * this.perPage) + 1;
            const endIndex = Math.min(pagination.current_page * this.perPage, pagination.count);
            infoElement.textContent = `نمایش ${startIndex} تا ${endIndex} از ${pagination.count} بارنامه`;
        }
    }
    
    updateRowCounter(pagination) {
        // به‌روزرسانی شمارنده کل در بالای صفحه
        const counterElements = document.querySelectorAll('.total-count, #totalBarnamehCount');
        counterElements.forEach(element => {
            element.textContent = pagination.count.toLocaleString('fa-IR');
        });
    }
    
    async loadInitialData() {
        await this.applyFilters();
    }
    
    showLoading() {
        // نمایش loading indicator
        const loadingElement = document.getElementById('barnamehTableLoading');
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
    }
    
    hideLoading() {
        // مخفی کردن loading indicator
        const loadingElement = document.getElementById('barnamehTableLoading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
    
    showToast(message, type = 'info') {
        // ایجاد toast notification
        const toastId = 'toast_' + Date.now();
        const toastClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';
        
        const icon = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        }[type] || 'fas fa-info-circle';
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white ${toastClass} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="${icon} me-2"></i>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        // ایجاد container اگر وجود ندارد
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: type === 'error' ? 5000 : 3000
        });
        
        toast.show();
        
        // حذف toast پس از بسته شدن
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
    
    getCSRFToken() {
        // دریافت CSRF token از کوکی یا meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            return csrfInput.value;
        }
        
        return null;
    }
    
    // Helper methods
    getSelectedColumns() {
        // دریافت لیست ستون‌های انتخاب شده از DOM
        const headers = this.table.querySelectorAll('thead th[data-column-id]');
        return Array.from(headers).map(header => header.getAttribute('data-column-id'));
    }
    
    getColumnName(columnId) {
        const columnNames = {
            'number': 'شماره بارنامه',
            'serial': 'سریال',
            'tonnage': 'وزن',
            'status': 'وضعیت',
            'driver_name': 'نام راننده',
            'driver_phone': 'شماره راننده',
            'vehicle_plate': 'پلاک خودرو',
            'receiver_name': 'نام گیرنده',
            'destination': 'مقصد',
            'barnameh_date': 'تاریخ بارنامه',
            'purchase_number': 'شماره خرید',
            'shenase_takhsis_code': 'شناسه تخصیص',
            'cargo': 'کوتاژ'
        };
        
        return columnNames[columnId] || columnId;
    }
    
    getSelectedColumns() {
        // دریافت ستون‌های انتخاب شده از headers جدول
        const headers = this.table.querySelectorAll('th[data-column-id]');
        const selectedColumns = [];
        
        headers.forEach(header => {
            const columnId = header.getAttribute('data-column-id');
            if (columnId) {
                selectedColumns.push(columnId);
            }
        });
        
        return selectedColumns;
    }
    
    updateSelectionCount() {
        // به‌روزرسانی شمارنده انتخاب شده‌های جدول اصلی
        const checkedBoxes = this.table.querySelectorAll('.row-checkbox:checked');
        const allCheckboxes = this.table.querySelectorAll('.row-checkbox');
        const countElements = document.querySelectorAll('#globalSelectionCount, .selected-count .count');
        
        countElements.forEach(element => {
            element.textContent = checkedBoxes.length;
        });
        
        const globalInfo = document.getElementById('globalSelectionInfo');
        if (globalInfo) {
            globalInfo.style.display = checkedBoxes.length > 0 ? 'block' : 'none';
        }
        
        // به‌روزرسانی وضعیت select-all checkbox
        const selectAllCheckbox = document.querySelector('.select-all-checkbox');
        if (selectAllCheckbox) {
            if (checkedBoxes.length === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else if (checkedBoxes.length === allCheckboxes.length) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }
        
        // به‌روزرسانی کنترل‌های ویرایش گروهی
        this.updateBulkEditControls();
    }
}

// راه‌اندازی فیلتر هنگام بارگذاری صفحه
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing Barnameh Server Filter...');
    
    // بررسی وجود جدول بارنامه
    const barnamehTable = document.getElementById('barnamehTable');
    if (barnamehTable) {
        // ایجاد instance فیلتر
        window.barnamehServerFilter = new BarnamehServerFilter('#barnamehTable');
        console.log('Barnameh Server Filter initialized successfully');
    } else {
        console.warn('Barnameh table not found');
    }
});

// توابع کمکی سراسری
function toggleRowSelection(checkbox) {
    // این تابع توسط onclick در template فراخوانی می‌شود
    if (window.barnamehServerFilter) {
        window.barnamehServerFilter.updateSelectionCount();
    }
    
    // اگر BulkEditManager وجود دارد، آن را نیز آپدیت کنیم
    if (window.bulkEditManager) {
        window.bulkEditManager.handleRowSelection(checkbox);
    }
} 