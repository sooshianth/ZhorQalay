/**
 * کلاس مدیریت فیلتر سمت سرور برای جدول شناسه‌های تخصیص
 */
class ShenaseTakhsisServerFilter {
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
        this.perPage = 20;
        
        this.isLoading = false;
        
        // Cache برای مقادیر ستون‌ها
        this.columnValuesCache = {};
        
        this.init();
    }
    
    init() {
        console.log('ShenaseTakhsisServerFilter: init() called');
        console.log('ShenaseTakhsisServerFilter: filterUrl =', this.filterUrl);
        console.log('ShenaseTakhsisServerFilter: columnValuesUrl =', this.columnValuesUrl);
        
        if (!this.filterUrl || !this.columnValuesUrl) {
            console.warn('URL های فیلتر تنظیم نشده‌اند');
            return;
        }
        
        this.setupFilterButtons();
        this.setupGlobalSearchHandler();
        this.setupPerPageSelector();
        
        // بارگذاری اولیه داده‌ها 
        setTimeout(() => {
            this.loadInitialData();
        }, 100);
        
        console.log('ShenaseTakhsisServerFilter: init() completed');
    }
    
    setupPerPageSelector() {
        const perPageSelect = document.querySelector('#perPageSelect');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                this.perPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.applyFilters();
            });
        }
    }
    
    setupGlobalSearchHandler() {
        console.log('ShenaseTakhsisServerFilter: Setting up global search handler...');
        
        // پیدا کردن input جستجوی سریع
        const globalSearchInput = document.querySelector('#real-time-search, #global-search');
        
        console.log('ShenaseTakhsisServerFilter: Global search input found:', globalSearchInput);
        
        if (!globalSearchInput) {
            console.warn('ShenaseTakhsisServerFilter: Global search input not found');
            return;
        }
        
        // حذف event listener قبلی
        globalSearchInput.removeEventListener('input', globalSearchInput._searchHandler);
        globalSearchInput.removeEventListener('keyup', globalSearchInput._searchHandler);
        
        console.log('ShenaseTakhsisServerFilter: Adding new search listener');
        
        let searchTimeout;
        
        // تعریف handler جدید
        const searchHandler = (e) => {
            const searchValue = e.target.value.trim();
            console.log('ShenaseTakhsisServerFilter: Search input changed to:', searchValue);
            
            // لغو timeout قبلی
            clearTimeout(searchTimeout);
            
            // نمایش loading indicator
            const loadingIndicator = document.querySelector('#search-loading');
            if (loadingIndicator) {
                loadingIndicator.classList.remove('d-none');
                console.log('ShenaseTakhsisServerFilter: Showing loading indicator');
            }
            
            // تنظیم timeout جدید برای جستجو
            searchTimeout = setTimeout(() => {
                console.log('ShenaseTakhsisServerFilter: Executing search for:', searchValue);
                
                // تنظیم مجدد صفحه به 1
                this.currentPage = 1;
                
                // اعمال فیلترها
                this.applyFilters().then(() => {
                    // مخفی کردن loading indicator
                    if (loadingIndicator) {
                        loadingIndicator.classList.add('d-none');
                        console.log('ShenaseTakhsisServerFilter: Hiding loading indicator');
                    }
                }).catch((error) => {
                    console.error('ShenaseTakhsisServerFilter: Search error:', error);
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
    
    async getColumnValues(columnId) {
        try {
            const formData = new FormData();
            formData.append('column_id', columnId);
            formData.append('current_filters', JSON.stringify(this.currentFilters));
            
            const globalSearchInput = document.querySelector('#real-time-search, #global-search');
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
        valuesContainer.className = 'values-container mb-3';
        
        // عنوان لیست مقادیر
        const valuesLabel = document.createElement('label');
        valuesLabel.className = 'form-label fw-bold mb-2';
        valuesLabel.innerHTML = '<i class="fas fa-list me-2"></i>مقادیر موجود:';
        
        // container اصلی لیست
        const valuesListContainer = document.createElement('div');
        valuesListContainer.className = 'values-list-wrapper';
        valuesListContainer.style.maxHeight = '300px';
        valuesListContainer.style.overflowY = 'auto';
        
        // ایجاد لیست checkbox ها
        const createValuesList = (values) => {
            valuesListContainer.innerHTML = '';
            
            if (!values || values.length === 0) {
                valuesListContainer.innerHTML = '<div class="text-muted text-center py-3"><i class="fas fa-inbox me-2"></i>مقدار موجود نیست</div>';
                return;
            }
            
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'form-check mb-3 p-3 border-bottom pb-3';
            selectAllContainer.style.backgroundColor = '#f0fdf4';
            selectAllContainer.innerHTML = `
                <input class="form-check-input" type="checkbox" id="selectAllFilter" checked>
                <label class="form-check-label fw-bold" for="selectAllFilter" style="margin-right: 8px;">
                    <i class="fas fa-check-square me-1"></i>
                    انتخاب همه (${values.length} مورد)
                </label>
            `;
            valuesListContainer.appendChild(selectAllContainer);
            
            const selectAllCheckbox = selectAllContainer.querySelector('#selectAllFilter');
            
            values.forEach((value, index) => {
                const valueContainer = document.createElement('div');
                valueContainer.className = 'form-check';
                
                const checkboxId = `filterValue_${index}_${Date.now()}`;
                const escapedValue = String(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                
                valueContainer.innerHTML = `
                    <input class="form-check-input value-checkbox" type="checkbox" id="${checkboxId}" value="${escapedValue}" checked>
                    <label class="form-check-label" for="${checkboxId}" style="margin-right: 8px;">
                        ${value}
                    </label>
                `;
                
                valuesListContainer.appendChild(valueContainer);
            });
            
            // مدیریت انتخاب همه
            selectAllCheckbox.addEventListener('change', function() {
                const valueCheckboxes = valuesListContainer.querySelectorAll('.value-checkbox');
                valueCheckboxes.forEach(cb => cb.checked = this.checked);
            });
            
            // مدیریت تغییر checkbox های جزئی
            valuesListContainer.addEventListener('change', function(e) {
                if (e.target.classList.contains('value-checkbox')) {
                    const allCheckboxes = valuesListContainer.querySelectorAll('.value-checkbox');
                    const checkedCheckboxes = valuesListContainer.querySelectorAll('.value-checkbox:checked');
                    
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
        
        // اضافه کردن label و list به container اصلی
        valuesContainer.appendChild(valuesLabel);
        valuesContainer.appendChild(valuesListContainer);
        
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
            const selectedValues = Array.from(valuesListContainer.querySelectorAll('.value-checkbox:checked'))
                .map(cb => cb.value);
            
            const filterType = modalBody.querySelector('input[name="filterType"]:checked').value;
            
            console.log('ShenaseTakhsisServerFilter: Applying filter with', selectedValues.length, 'values');
            
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
            
            // تنظیم مقادیر انتخاب شده - با تاخیر کوتاه برای اطمینان از render شدن DOM
            setTimeout(() => {
                const checkboxes = valuesListContainer.querySelectorAll('.value-checkbox');
                console.log('ShenaseTakhsisServerFilter: Setting filter values, total checkboxes:', checkboxes.length);
                console.log('ShenaseTakhsisServerFilter: Current filter values:', currentFilter.values);
                
                // ابتدا همه را uncheck کن
                checkboxes.forEach(cb => {
                    cb.checked = false;
                });
                
                // سپس فقط مقادیر فیلتر فعلی را check کن
                checkboxes.forEach(cb => {
                    if (currentFilter.values.includes(cb.value)) {
                        cb.checked = true;
                    }
                });
                
                // بروزرسانی انتخاب همه
                const selectAllCb = valuesListContainer.querySelector('#selectAllFilter');
                const checkedCount = valuesListContainer.querySelectorAll('.value-checkbox:checked').length;
                const totalCount = checkboxes.length;
                
                console.log('ShenaseTakhsisServerFilter: Checked count:', checkedCount, '/', totalCount);
                
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
            }, 150);
        }
    }
    
    toggleSort(columnId, direction) {
        this.currentSort = { column: columnId, direction: direction };
        this.currentPage = 1;
        this.applyFilters();
    }
    
    async applyFilters() {
        if (this.isLoading) return;
        
        console.log('ShenaseTakhsisServerFilter: applyFilters() called');
        this.isLoading = true;
        this.showLoading();
        
        try {
            const formData = new FormData();
            formData.append('filters', JSON.stringify(this.currentFilters));
            formData.append('sort', JSON.stringify(this.currentSort));
            formData.append('page', this.currentPage.toString());
            formData.append('per_page', this.perPage.toString());
            
            // دریافت مقدار جستجوی عمومی
            const globalSearchInput = document.querySelector('#real-time-search, #global-search');
            const searchValue = globalSearchInput ? globalSearchInput.value.trim() : '';
            
            if (searchValue) {
                formData.append('global_search', searchValue);
                console.log('ShenaseTakhsisServerFilter: Adding global search:', searchValue);
            }
            
            formData.append('csrfmiddlewaretoken', this.getCSRFToken());
            
            console.log('ShenaseTakhsisServerFilter: Sending request to', this.filterUrl);
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData
            });
            
            console.log('ShenaseTakhsisServerFilter: Response received', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('ShenaseTakhsisServerFilter: Response data:', data);
            
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
    
    updateTableContent(shenaseList, pagination) {
        console.log('ShenaseTakhsisServerFilter: updateTableContent called with:', shenaseList);
        const tbody = this.tableElement.querySelector('tbody');
        if (!tbody) return;
        
        // پاک کردن محتوای فعلی
        tbody.innerHTML = '';
        
        if (!shenaseList || shenaseList.length === 0) {
            tbody.innerHTML = `
                <tr class="no-data-row">
                    <td colspan="100%" class="text-center py-4">
                        <i class="fas fa-search text-muted fa-2x mb-2"></i>
                        <p class="text-muted">هیچ شناسه تخصیصی یافت نشد</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        // اضافه کردن ردیف‌های جدید
        shenaseList.forEach((shenase, index) => {
            console.log(`ShenaseTakhsisServerFilter: Creating row ${index} for shenase:`, shenase);
            const row = this.createTableRow(shenase);
            tbody.appendChild(row);
        });
        
        // اتصال event listener ها برای bulk edit
        this.connectBulkEditListeners();
        
        // بروزرسانی شمارنده
        this.updateRowCounter(pagination);
    }
    
    createTableRow(shenase) {
        console.log('ShenaseTakhsisServerFilter: createTableRow called with shenase:', shenase);
        const row = document.createElement('tr');
        row.className = 'animate-fade-in selectable-row';
        row.dataset.id = shenase.id;
        
        // دریافت ترتیب ستون‌ها از DOM
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        let cellsHtml = '';
        
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const isVisible = window.getComputedStyle(header).display !== 'none';
            const cellStyle = isVisible ? '' : ' style="display: none;"';
            
            switch(columnId) {
                case 'select':
                    const selectStyle = isVisible ? ' style="text-align: center; padding: 8px;"' : cellStyle;
                    cellsHtml += `
                        <td${selectStyle}>
                            <input type="checkbox" class="row-checkbox" data-id="${shenase.id}" style="cursor: pointer; width: 18px; height: 18px;">
                        </td>
                    `;
                    break;
                    
                case 'code':
                    cellsHtml += `
                        <td${cellStyle}>
                            <span class="badge badge-primary">${shenase.code || '—'}</span>
                        </td>
                    `;
                    break;
                    
                case 'purchase_number':
                    cellsHtml += `
                        <td${cellStyle}>
                            <span class="badge ${shenase.purchase_number ? 'badge-info' : 'badge-warning'}">${shenase.purchase_number || '—'}</span>
                        </td>
                    `;
                    break;
                    
                case 'invoice_id':
                    cellsHtml += `<td${cellStyle}>${shenase.invoice_id || '—'}</td>`;
                    break;
                    
                case 'customer':
                    cellsHtml += `<td${cellStyle}><strong>${shenase.customer || '—'}</strong></td>`;
                    break;
                    
                case 'weight':
                    cellsHtml += `
                        <td${cellStyle}>
                            ${shenase.weight ? `<span class="badge badge-success">${shenase.weight.toLocaleString()}</span>` : '—'}
                        </td>
                    `;
                    break;
                    
                case 'code_melli_tahvil':
                    cellsHtml += `<td${cellStyle}>${shenase.code_melli_tahvil || '—'}</td>`;
                    break;
                    
                case 'tahvil_phone_number':
                    cellsHtml += `<td${cellStyle}>${shenase.tahvil_phone_number || '—'}</td>`;
                    break;
                    
                case 'delivery_receiver_name':
                    cellsHtml += `<td${cellStyle}>${shenase.delivery_receiver_name || '—'}</td>`;
                    break;
                    
                case 'delivery_address':
                    cellsHtml += `<td${cellStyle}>${shenase.delivery_address || '—'}</td>`;
                    break;
                    
                case 'delivery_postal_code':
                    cellsHtml += `<td${cellStyle}>${shenase.delivery_postal_code || '—'}</td>`;
                    break;
                    
                case 'created_at':
                    cellsHtml += `<td${cellStyle}>${shenase.created_at || '—'}</td>`;
                    break;
                    
                case 'actions':
                    cellsHtml += `
                        <td${cellStyle}>
                            ${shenase.purchase_id ? `<a href="/erp/purchase_CRUD/${shenase.purchase_id}/" class="btn-view"><i class="fas fa-eye"></i> مشاهده خرید</a>` : (shenase.purchase_number ? `<span class="text-muted">خرید یافت نشد</span>` : '—')}
                        </td>
                    `;
                    break;
                    
                default:
                    cellsHtml += `<td${cellStyle}>—</td>`;
                    break;
            }
        });
        
        row.innerHTML = cellsHtml;
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
        let filterStatusContainer = document.querySelector('#shenase-filter-status');
        
        if (!filterStatusContainer) {
            filterStatusContainer = document.createElement('div');
            filterStatusContainer.id = 'shenase-filter-status';
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
        const clearAllBtn = filterStatusContainer.querySelector('#clear-all-filters');
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
        let paginationContainer = document.querySelector('#shenase-server-pagination');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'shenase-server-pagination';
            paginationContainer.className = 'pagination-container mt-4';
            
            const tableContainer = this.tableElement.closest('.table-container') || this.tableElement.parentNode;
            tableContainer.insertAdjacentElement('afterend', paginationContainer);
        }
        
        this.updatePaginationInfo(paginationContainer, pagination);
    }
    
    updatePaginationInfo(paginationContainer, pagination) {
        let paginationHtml = '';
        
        paginationHtml += `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <p class="text-muted mb-0">
                        نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} شناسه تخصیص
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
        console.log('ShenaseTakhsisServerFilter: Connecting bulk edit listeners...');
        
        // اتصال به bulk edit manager اگر موجود است
        if (window.bulkEditManager) {
            console.log('ShenaseTakhsisServerFilter: BulkEditManager found, triggering update...');
            
            document.dispatchEvent(new CustomEvent('tableContentUpdated', {
                detail: { tableId: this.tableId }
            }));
            
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
        console.log('ShenaseTakhsisServerFilter: Setting up fallback bulk edit...');
        
        // مدیریت checkbox های ردیف
        const rowCheckboxes = this.tableElement.querySelectorAll('.row-checkbox');
        console.log('ShenaseTakhsisServerFilter: Found', rowCheckboxes.length, 'row checkboxes');
        
        rowCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                console.log('ShenaseTakhsisServerFilter: Row checkbox changed');
                
                // بروزرسانی کلاس selected برای ردیف
                const row = checkbox.closest('tr');
                if (row) {
                    if (checkbox.checked) {
                        row.classList.add('selected', 'bulk-selected');
                    } else {
                        row.classList.remove('selected', 'bulk-selected');
                    }
                }
                
                this.updateBulkEditPanel();
            });
        });
        
        // مدیریت select all checkbox
        const selectAllCheckbox = this.tableElement.querySelector('#select-all-checkbox');
        if (selectAllCheckbox) {
            // حذف listener قبلی اگر وجود دارد
            selectAllCheckbox.removeEventListener('change', selectAllCheckbox._changeHandler);
            
            selectAllCheckbox._changeHandler = () => {
                console.log('ShenaseTakhsisServerFilter: Select all checkbox changed to:', selectAllCheckbox.checked);
                
                const rowCheckboxes = this.tableElement.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(cb => {
                    cb.checked = selectAllCheckbox.checked;
                    
                    // بروزرسانی کلاس selected
                    const row = cb.closest('tr');
                    if (row) {
                        if (selectAllCheckbox.checked) {
                            row.classList.add('selected', 'bulk-selected');
                        } else {
                            row.classList.remove('selected', 'bulk-selected');
                        }
                    }
                });
                
                this.updateBulkEditPanel();
            };
            
            selectAllCheckbox.addEventListener('change', selectAllCheckbox._changeHandler);
        }
    }
    
    updateBulkEditPanel() {
        console.log('ShenaseTakhsisServerFilter: updateBulkEditPanel called');
        
        const selectedCheckboxes = this.tableElement.querySelectorAll('.row-checkbox:checked');
        const selectedCount = selectedCheckboxes.length;
        
        console.log('ShenaseTakhsisServerFilter: Selected count:', selectedCount);
        
        // پیدا کردن پنل
        const bulkEditPanel = document.querySelector('.bulk-edit-controls-top');
        const countElement = bulkEditPanel ? bulkEditPanel.querySelector('.count') : null;
        
        if (bulkEditPanel && countElement) {
            // بروزرسانی شمارنده
            countElement.textContent = selectedCount;
            
            // نمایش/مخفی کردن پنل
            if (selectedCount > 0) {
                bulkEditPanel.style.display = 'block';
                console.log('ShenaseTakhsisServerFilter: Showing bulk edit panel');
            } else {
                bulkEditPanel.style.display = 'none';
                console.log('ShenaseTakhsisServerFilter: Hiding bulk edit panel');
            }
        }
        
        // بروزرسانی دکمه export در header
        const exportBtnHeader = document.querySelector('.export-selected-excel-btn-header');
        const selectedCountSpan = exportBtnHeader ? exportBtnHeader.querySelector('.selected-count') : null;
        if (exportBtnHeader) {
            exportBtnHeader.style.display = selectedCount > 0 ? 'inline-block' : 'none';
            if (selectedCountSpan) {
                selectedCountSpan.textContent = selectedCount;
            }
        }
        
        // بروزرسانی وضعیت select all checkbox
        const selectAllCheckbox = this.tableElement.querySelector('#select-all-checkbox');
        const allRowCheckboxes = this.tableElement.querySelectorAll('.row-checkbox');
        
        if (selectAllCheckbox && allRowCheckboxes.length > 0) {
            if (selectedCount === allRowCheckboxes.length) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else if (selectedCount === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }
    }
    
    updateRowCounter(pagination) {
        let counterElement = document.querySelector('#shenase-row-counter');
        
        if (!counterElement) {
            counterElement = document.createElement('div');
            counterElement.id = 'shenase-row-counter';
            counterElement.className = 'row-counter text-muted small mb-2';
            
            const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
            tableContainer.insertBefore(counterElement, tableContainer.firstChild);
        }
        
        counterElement.innerHTML = `
            <i class="fas fa-list me-1"></i>
            نمایش ${pagination.start_index} تا ${pagination.end_index} از ${pagination.total_count} شناسه تخصیص
        `;
    }
    
    async loadInitialData() {
        await this.applyFilters();
    }
    
    showLoading() {
        let loadingElement = document.querySelector('#shenase-table-loading');
        
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.id = 'shenase-table-loading';
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
        const loadingElement = document.querySelector('#shenase-table-loading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
    
    showToast(message, type = 'info') {
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
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
    
    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }
}

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    console.log('Shenase Takhsis Server Filter: DOM loaded');
    
    const shenaseTable = document.querySelector('#shenaseTakhsisTable');
    if (shenaseTable) {
        console.log('Shenase Takhsis Server Filter: Table found, initializing...');
        window.shenaseTakhsisServerFilter = new ShenaseTakhsisServerFilter('#shenaseTakhsisTable');
        console.log('Shenase Takhsis Server Filter: Initialized successfully');
    } else {
        console.warn('Shenase Takhsis Server Filter: Table #shenaseTakhsisTable not found');
    }
});

