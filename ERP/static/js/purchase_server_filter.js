/**
 * کلاس مدیریت فیلتر سمت سرور برای جداول خریدها
 */
class PurchaseServerFilter {
    constructor(tableSelector) {
        this.tableId = tableSelector;
        this.tableElement = document.querySelector(tableSelector);
        
        if (!this.tableElement) {
            console.error(`❌ جدول یافت نشد: ${tableSelector}`);
            return;
        }
        
        // تشخیص بخش بر اساس نام جدول
        if (tableSelector.includes('pending') || tableSelector.includes('Pending')) {
            this.section = 'pending';
        } else if (tableSelector.includes('archived') || tableSelector.includes('Archived')) {
            this.section = 'archived';
        } else if (tableSelector.includes('active') || tableSelector.includes('Active')) {
            this.section = 'active';
        } else {
            // fallback: تشخیص بر اساس data-section attribute
            this.section = this.tableElement.dataset.section || 'active';
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
        const perPageSelector = document.querySelector(`#${this.section}PerPage`);
        if (perPageSelector && perPageSelector.value) {
            const value = parseInt(perPageSelector.value);
            return value;
        }
        
        return 25; // پیش‌فرض
    }
    
    init() {
        if (!this.filterUrl || !this.columnValuesUrl) {
            console.error('Filter URLs not found in table dataset');
            return;
        }
        
        // غیرفعال کردن traditional pagination برای این جدول
        this.disableTraditionalPagination();
        
        this.setupFilterButtons();
        this.setupPerPageSelector();
        this.setupGlobalSearchHandler();
        this.loadInitialData();
    }
    
    disableTraditionalPagination() {
        // علامت‌گذاری جدول به عنوان دارای server filter
        this.tableElement.setAttribute('data-server-filter-active', 'true');
        
        // غیرفعال کردن traditional pagination links
        const section = this.section;
        const traditionalPaginationContainer = document.querySelector(`#${section}Pagination`);
        
        if (traditionalPaginationContainer) {
            // پنهان کردن pagination links موجود که توسط Django template ایجاد شده‌اند
            const traditionalNavs = traditionalPaginationContainer.querySelectorAll('nav:not([data-server-filter])');
            traditionalNavs.forEach(nav => {
                nav.style.display = 'none';
                nav.setAttribute('data-traditional-pagination', 'disabled');
            });
        }
        
        // غیرفعال کردن traditional per-page selectors
        const traditionalPerPageSelect = document.querySelector(`#${section}PerPage:not([data-server-filter-listener])`);
        if (traditionalPerPageSelect && !traditionalPerPageSelect.hasAttribute('data-server-filter-listener')) {
            traditionalPerPageSelect.style.display = 'none';
        }
    }
    
    setupPerPageSelector() {
        // پیدا کردن per page selector موجود در template
        const existingSelector = document.querySelector(`#${this.section}PerPage`);
        if (existingSelector) {
            // تنظیم مقدار فعلی
            existingSelector.value = this.perPage;
            
            // اضافه کردن event listener اگر قبلاً اضافه نشده
            if (!existingSelector.hasAttribute('data-server-filter-listener')) {
                existingSelector.setAttribute('data-server-filter-listener', 'true');
                existingSelector.addEventListener('change', (e) => {
                    const newPerPage = parseInt(e.target.value);
                    this.perPage = newPerPage;
                    this.currentPage = 1; // بازگشت به صفحه اول
                    this.applyFilters();
                });
            }
            
            return;
        }
        
        // اگر selector موجود نبود، یکی ایجاد کن (fallback)
        const tableContainer = this.tableElement.closest('.table-responsive') || this.tableElement.parentNode;
        
        const perPageContainer = document.createElement('div');
        perPageContainer.className = 'per-page-container mb-3 d-flex align-items-center';
        perPageContainer.innerHTML = `
            <label for="${this.section}PerPageFilter" class="form-label me-2">تعداد در هر صفحه:</label>
            <select id="${this.section}PerPageFilter" class="form-select form-select-sm w-auto">
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
            const newPerPage = parseInt(e.target.value);
            this.perPage = newPerPage;
            this.currentPage = 1; // بازگشت به صفحه اول
            this.applyFilters();
        });
    }
    
    setupGlobalSearchHandler() {
        // پیدا کردن input جستجوی سریع
        const globalSearchInput = document.querySelector('#globalSearch, #global_search, [name="global_search"]');
        
        if (globalSearchInput && !globalSearchInput.hasAttribute('data-server-filter-listener')) {
            globalSearchInput.setAttribute('data-server-filter-listener', 'true');
            
            let searchTimeout;
            
            // event listener برای تایپ در جستجوی سریع
            globalSearchInput.addEventListener('input', (e) => {
                // پاک کردن timeout قبلی
                clearTimeout(searchTimeout);
                
                // تنظیم timeout جدید برای جلوگیری از درخواست‌های زیاد
                searchTimeout = setTimeout(() => {
                    // بازگشت به صفحه اول وقتی جستجو تغییر میکنه
                    this.currentPage = 1;
                    // پاک کردن cache ستون‌ها چون نتایج تغییر کرده
                    this.columnValuesCache = {};
                    // اعمال فیلتر
                    this.applyFilters();
                }, 500); // 500ms تاخیر
            });
            
            // event listener برای کلید Enter
            globalSearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(searchTimeout);
                    this.currentPage = 1;
                    this.columnValuesCache = {};
                    this.applyFilters();
                }
            });
        }
    }
    
    setupFilterButtons() {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const columnType = header.dataset.columnType || 'text';
            
            // بررسی اینکه آیا قبلاً filter button اضافه شده یا نه
            if (header.querySelector('.filter-controls')) {
                return;
            }
            
            // ایجاد container برای کنترل‌های فیلتر
            const controlsContainer = document.createElement('div');
            controlsContainer.className = 'filter-controls d-flex align-items-center justify-content-between';
            
            // متن اصلی header
            const headerText = header.textContent.trim();
            
            // ایجاد span برای متن
            const textSpan = document.createElement('span');
            textSpan.textContent = headerText;
            textSpan.className = 'header-text';
            
            // ایجاد container برای دکمه‌ها
            const buttonsContainer = document.createElement('div');
            buttonsContainer.className = 'filter-buttons d-flex';
            
            // دکمه فیلتر
            const filterBtn = document.createElement('button');
            filterBtn.className = 'btn btn-sm btn-outline-primary filter-btn me-1';
            filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
            filterBtn.title = `فیلتر ${headerText}`;
            filterBtn.setAttribute('data-column-id', columnId);
            filterBtn.setAttribute('data-column-type', columnType);
            
            // اضافه کردن event listeners
            filterBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.showFilterModal(columnId, columnType, header);
            });
            
            // ترکیب کردن عناصر
            buttonsContainer.appendChild(filterBtn);
            
            controlsContainer.appendChild(textSpan);
            controlsContainer.appendChild(buttonsContainer);
            
            // پاک کردن محتوای قبلی header و اضافه کردن controls جدید
            header.innerHTML = '';
            header.appendChild(controlsContainer);
        });
    }
    
    async showFilterModal(columnId, columnType, headerElement) {
        
        try {
            // دریافت همه مقادیر ممکن از سرور (شامل اطلاعات انتخاب)
            const serverValues = await this.getColumnValues(columnId);
            
            // ایجاد مودال با فرمت جدید
            this.createFilterModal(columnId, columnType, serverValues, headerElement);
            
        } catch (error) {
            console.error('خطا در نمایش فیلتر:', error);
            this.showToast('خطا در بارگیری فیلتر', 'error');
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
            if (cell && cell.textContent.trim()) {
                let value = cell.textContent.trim();
                
                // تمیز کردن مقادیر عددی
                if (['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid'].includes(columnId)) {
                    value = value.replace(/,/g, '').replace(/٬/g, '');
                }
                
                values.add(value);
            }
        });
        
        return Array.from(values).filter(v => v && v !== '-' && v !== 'تعیین نشده');
    }
    
    getColumnIndex(columnId) {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        for (let i = 0; i < headers.length; i++) {
            if (headers[i].dataset.columnId === columnId) {
                return i + 1; // +1 برای checkbox column
            }
        }
        return -1;
    }
    
    async getColumnValues(columnId) {
        // برای column values همیشه cache رو نادیده بگیر تا فیلترهای جدید اعمال بشه
        try {
            const formData = new FormData();
            formData.append('column_id', columnId);
            formData.append('section', this.section);
            formData.append('current_filters', JSON.stringify(this.currentFilters));
            
            // دریافت مقدار global_search از input
            const globalSearchInput = document.querySelector('#globalSearch, #global_search, [name="global_search"]');
            const globalSearchValue = globalSearchInput ? globalSearchInput.value.trim() : '';
            if (globalSearchValue) {
                formData.append('global_search', globalSearchValue);
            }
            
            const response = await fetch(this.columnValuesUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                // اطلاعات اضافی برای debugging
                console.log(`📊 Column values for ${columnId}:`, {
                    total: data.total_available,
                    shown: data.count,
                    selected: data.selected_count
                });
                
                return data.values; // حالا هر value شامل {value, selected, display} است
            } else {
                throw new Error(data.message || 'خطا در دریافت مقادیر');
            }
            
        } catch (error) {
            console.error('خطا در دریافت مقادیر ستون:', error);
            return [];
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
        
        const filterTypeLabel = document.createElement('label');
        filterTypeLabel.className = 'form-label fw-bold';
        filterTypeLabel.textContent = 'نوع فیلتر:';
        
        const filterTypeGroup = document.createElement('div');
        filterTypeGroup.className = 'btn-group w-100 mt-2';
        filterTypeGroup.setAttribute('role', 'group');
        
        // تعیین نوع فیلتر فعلی
        const currentFilterType = this.currentFilters[columnId]?.type || 'include';
        
        const includeInput = document.createElement('input');
        includeInput.type = 'radio';
        includeInput.className = 'btn-check';
        includeInput.name = 'filterType';
        includeInput.value = 'include';
        includeInput.id = 'includeFilter';
        includeInput.checked = currentFilterType === 'include';
        
        const includeLabel = document.createElement('label');
        includeLabel.className = 'btn btn-outline-success filter-type-btn';
        includeLabel.htmlFor = 'includeFilter';
        includeLabel.innerHTML = '<i class="fas fa-check me-1"></i>نمایش موارد انتخاب شده';
        
        const excludeInput = document.createElement('input');
        excludeInput.type = 'radio';
        excludeInput.className = 'btn-check';
        excludeInput.name = 'filterType';
        excludeInput.value = 'exclude';
        excludeInput.id = 'excludeFilter';
        excludeInput.checked = currentFilterType === 'exclude';
        
        const excludeLabel = document.createElement('label');
        excludeLabel.className = 'btn btn-outline-danger filter-type-btn';
        excludeLabel.htmlFor = 'excludeFilter';
        excludeLabel.innerHTML = '<i class="fas fa-times me-1"></i>مخفی کردن موارد انتخاب شده';
        
        filterTypeGroup.appendChild(includeInput);
        filterTypeGroup.appendChild(includeLabel);
        filterTypeGroup.appendChild(excludeInput);
        filterTypeGroup.appendChild(excludeLabel);
        
        filterTypeContainer.appendChild(filterTypeLabel);
        filterTypeContainer.appendChild(filterTypeGroup);
        
        // جستجو
        const searchContainer = document.createElement('div');
        searchContainer.className = 'mb-3';
        
        const searchLabel = document.createElement('label');
        searchLabel.className = 'form-label fw-bold';
        searchLabel.textContent = 'جستجو در مقادیر:';
        
        const searchInputGroup = document.createElement('div');
        searchInputGroup.className = 'input-group';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'form-control filter-search';
        searchInput.placeholder = 'جستجو...';
        
        const searchIcon = document.createElement('span');
        searchIcon.className = 'input-group-text';
        searchIcon.innerHTML = '<i class="fas fa-search"></i>';
        
        searchInputGroup.appendChild(searchInput);
        searchInputGroup.appendChild(searchIcon);
        
        // نتایج جستجو
        const searchResults = document.createElement('small');
        searchResults.id = 'filterSearchResults';
        searchResults.className = 'text-muted mt-1';
        
        searchContainer.appendChild(searchLabel);
        searchContainer.appendChild(searchInputGroup);
        searchContainer.appendChild(searchResults);
        
        // بخش مرتب‌سازی
        const sortContainer = document.createElement('div');
        sortContainer.className = 'mb-3';
        
        const sortLabel = document.createElement('label');
        sortLabel.className = 'form-label fw-bold';
        sortLabel.textContent = 'مرتب‌سازی:';
        
        const sortButtonsGroup = document.createElement('div');
        sortButtonsGroup.className = 'btn-group w-100 mt-2';
        sortButtonsGroup.setAttribute('role', 'group');
        
        // دکمه مرتب‌سازی صعودی
        const sortAscBtn = document.createElement('button');
        sortAscBtn.type = 'button';
        sortAscBtn.className = 'btn btn-outline-success sort-asc-btn';
        sortAscBtn.innerHTML = '<i class="fas fa-sort-up me-1"></i>صعودی (الف تا ی)';
        sortAscBtn.setAttribute('data-column-id', columnId);
        sortAscBtn.setAttribute('data-direction', 'asc');
        
        // دکمه مرتب‌سازی نزولی
        const sortDescBtn = document.createElement('button');
        sortDescBtn.type = 'button';
        sortDescBtn.className = 'btn btn-outline-danger sort-desc-btn';
        sortDescBtn.innerHTML = '<i class="fas fa-sort-down me-1"></i>نزولی (ی تا الف)';
        sortDescBtn.setAttribute('data-column-id', columnId);
        sortDescBtn.setAttribute('data-direction', 'desc');
        
        // دکمه حذف مرتب‌سازی
        const sortResetBtn = document.createElement('button');
        sortResetBtn.type = 'button';
        sortResetBtn.className = 'btn btn-outline-secondary sort-reset-btn';
        sortResetBtn.innerHTML = '<i class="fas fa-times me-1"></i>بدون مرتب‌سازی';
        
        // نمایش وضعیت فعلی مرتب‌سازی
        if (this.currentSort.column === columnId) {
            if (this.currentSort.direction === 'asc') {
                sortAscBtn.classList.add('active');
                sortAscBtn.classList.replace('btn-outline-success', 'btn-success');
            } else if (this.currentSort.direction === 'desc') {
                sortDescBtn.classList.add('active');
                sortDescBtn.classList.replace('btn-outline-danger', 'btn-danger');
            }
        } else {
            sortResetBtn.classList.add('active');
            sortResetBtn.classList.replace('btn-outline-secondary', 'btn-secondary');
        }
        
        // Event listeners برای دکمه‌های مرتب‌سازی
        sortAscBtn.addEventListener('click', () => {
            this.toggleSort(columnId, 'asc');
            modal.remove();
        });
        
        sortDescBtn.addEventListener('click', () => {
            this.toggleSort(columnId, 'desc');
            modal.remove();
        });
        
        sortResetBtn.addEventListener('click', () => {
            this.currentSort = { column: null, direction: 'asc' };
            this.currentPage = 1;
            this.applyFilters();
            modal.remove();
        });
        
        sortButtonsGroup.appendChild(sortAscBtn);
        sortButtonsGroup.appendChild(sortDescBtn);
        sortButtonsGroup.appendChild(sortResetBtn);
        
        sortContainer.appendChild(sortLabel);
        sortContainer.appendChild(sortButtonsGroup);
        
        // لیست مقادیر
        const valuesContainer = document.createElement('div');
        valuesContainer.className = 'mb-3';
        
        // بررسی فرمت serverValues - آیا array از objects است یا array ساده
        const isObjectFormat = serverValues.length > 0 && typeof serverValues[0] === 'object' && serverValues[0].hasOwnProperty('value');
        
        const totalCount = serverValues.length;
        // با منطق جدید، همه مقادیر موجود = همه انتخاب شده (تیک خورده)
        const selectedCount = isObjectFormat ? serverValues.filter(item => item.selected).length : totalCount;
        
        const valuesLabel = document.createElement('label');
        valuesLabel.className = 'form-label fw-bold';
        valuesLabel.textContent = `مقادیر موجود (${totalCount} مورد - بر اساس فیلترهای دیگر):`;
        
        const filterHelpText = document.createElement('small');
        filterHelpText.className = 'text-muted d-block mb-2';
        filterHelpText.innerHTML = '<i class="fas fa-info-circle me-1"></i>این مقادیر بر اساس فیلترهای دیگر ستون‌ها نمایش داده می‌شوند. همه به طور پیش‌فرض انتخاب شده‌اند.';
        
        const valuesList = document.createElement('div');
        valuesList.className = 'filter-values-list';
        
        // کنترل انتخاب همه
        const selectAllContainer = document.createElement('div');
        selectAllContainer.className = 'filter-value-item d-flex align-items-center mb-2 p-2 border-bottom';
        
        const selectAllCheckbox = document.createElement('input');
        selectAllCheckbox.type = 'checkbox';
        selectAllCheckbox.className = 'form-check-input me-2';
        selectAllCheckbox.id = 'selectAll';
        // همه موجود = همه انتخاب شده
        selectAllCheckbox.checked = true;
        
        const selectAllLabel = document.createElement('label');
        selectAllLabel.className = 'form-check-label fw-bold flex-grow-1';
        selectAllLabel.htmlFor = 'selectAll';
        selectAllLabel.innerHTML = '<i class="fas fa-check-double me-1"></i>انتخاب همه';
        
        selectAllContainer.appendChild(selectAllCheckbox);
        selectAllContainer.appendChild(selectAllLabel);
        
        valuesList.appendChild(selectAllContainer);
        
        // ایجاد آیتم‌های مقادیر
        serverValues.forEach((valueItem, index) => {
            const container = document.createElement('div');
            container.className = 'filter-value-item d-flex align-items-center';
            
            // استخراج مقدار و حالت انتخاب
            let value, isSelected, displayText;
            
            if (isObjectFormat) {
                value = valueItem.value;
                isSelected = valueItem.selected || false;
                displayText = valueItem.display || value;
            } else {
                // فرمت قدیمی - همه غیر انتخاب شده
                value = valueItem;
                isSelected = false;
                displayText = value;
            }
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input me-2';
            checkbox.value = value;
            checkbox.id = `filter_${columnId}_${index}`;
            checkbox.checked = isSelected;
            
            const label = document.createElement('label');
            label.className = 'form-check-label flex-grow-1';
            label.htmlFor = checkbox.id;
            
            // با منطق جدید، همه مقادیر برگشتی "موجود" هستند پس تیک خورده‌اند
            if (isSelected) {
                label.innerHTML = `<i class="fas fa-check-square text-success me-1"></i><strong>${displayText}</strong>`;
                label.title = 'این مقدار در داده‌های فیلتر شده موجود است';
                container.classList.add('selected');
            } else {
                // این حالت دیگه نباید اتفاق بیفته چون همه selected=true برمیگردن
                label.innerHTML = `<i class="fas fa-square text-muted me-1"></i>${displayText}`;
                label.title = 'این مقدار در داده‌های فیلتر شده موجود است';
            }
            
            container.appendChild(checkbox);
            container.appendChild(label);
            valuesList.appendChild(container);
        });
        
        valuesContainer.appendChild(valuesLabel);
        valuesContainer.appendChild(filterHelpText);
        valuesContainer.appendChild(valuesList);
        
        modalBody.appendChild(filterTypeContainer);
        modalBody.appendChild(searchContainer);
        modalBody.appendChild(sortContainer);
        modalBody.appendChild(valuesContainer);
        
        // Footer مودال
        const modalFooter = document.createElement('div');
        modalFooter.className = 'modal-footer';
        
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'btn btn-secondary';
        clearBtn.innerHTML = '<i class="fas fa-eraser me-1"></i>پاک کردن فیلتر';
        
        const applyBtn = document.createElement('button');
        applyBtn.type = 'button';
        applyBtn.className = 'btn btn-primary';
        applyBtn.innerHTML = '<i class="fas fa-check me-1"></i>اعمال فیلتر';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-light';
        cancelBtn.innerHTML = '<i class="fas fa-times me-1"></i>انصراف';
        
        modalFooter.appendChild(clearBtn);
        modalFooter.appendChild(applyBtn);
        modalFooter.appendChild(cancelBtn);
        
        // ترکیب کردن عناصر
        modalContent.appendChild(modalHeader);
        modalContent.appendChild(modalBody);
        modalContent.appendChild(modalFooter);
        modalDialog.appendChild(modalContent);
        modal.appendChild(modalDialog);
        document.body.appendChild(modal);
        
        // Event listeners
        
        // انتخاب همه (فقط موارد visible)
        selectAllCheckbox.addEventListener('change', function() {
            const visibleCheckboxes = Array.from(valuesList.querySelectorAll('.filter-value-item:not(:first-child)'))
                .filter(container => container.style.display !== 'none')
                .map(container => container.querySelector('input[type="checkbox"]'));
            
            visibleCheckboxes.forEach(cb => {
                cb.checked = this.checked;
                // بروزرسانی ظاهر
                const container = cb.closest('.filter-value-item');
                if (cb.checked) {
                    container.classList.add('selected');
                } else {
                    container.classList.remove('selected');
                }
            });
        });
        
        // تغییر وضعیت چک‌باکس‌های فردی
        valuesList.addEventListener('change', function(e) {
            if (e.target.type === 'checkbox' && e.target.id !== 'selectAll') {
                const container = e.target.closest('.filter-value-item');
                if (e.target.checked) {
                    container.classList.add('selected');
                } else {
                    container.classList.remove('selected');
                }
                
                // بروزرسانی وضعیت انتخاب همه
                const allCheckboxes = valuesList.querySelectorAll('input[type="checkbox"]:not(#selectAll)');
                const checkedCheckboxes = valuesList.querySelectorAll('input[type="checkbox"]:not(#selectAll):checked');
                selectAllCheckbox.checked = allCheckboxes.length === checkedCheckboxes.length;
                selectAllCheckbox.indeterminate = checkedCheckboxes.length > 0 && checkedCheckboxes.length < allCheckboxes.length;
            }
        });
        
        // جستجو
        const searchHandler = function() {
            const searchTerm = this.value.toLowerCase().trim();
            const containers = valuesList.querySelectorAll('.filter-value-item:not(:first-child)');
            let visibleCount = 0;
            let totalCount = containers.length;
            
            containers.forEach(container => {
                const label = container.querySelector('label');
                // استخراج متن خام بدون HTML tags و icons
                const text = label.textContent
                    .replace(/[🔽🔼]/g, '')
                    .replace(/[✓×]/g, '')
                    .replace(/\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                const isVisible = !searchTerm || text.includes(searchTerm);
                
                container.style.display = isVisible ? 'flex' : 'none';
                if (isVisible) visibleCount++;
            });
            
            // بروزرسانی تعداد نتایج
            const resultsLabel = document.querySelector('#filterSearchResults');
            if (resultsLabel) {
                if (searchTerm) {
                    resultsLabel.textContent = `${visibleCount} از ${totalCount} مورد یافت شد`;
                    resultsLabel.style.color = visibleCount > 0 ? '#1e6135' : '#dc3545';
                } else {
                    resultsLabel.textContent = `${totalCount} مورد موجود`;
                    resultsLabel.style.color = '#6c757d';
                }
            }
            
            // بروزرسانی وضعیت select all checkbox بر اساس موارد visible
            const visibleCheckboxes = Array.from(containers)
                .filter(container => container.style.display !== 'none')
                .map(container => container.querySelector('input[type="checkbox"]'));
            
            const checkedVisibleCount = visibleCheckboxes.filter(cb => cb.checked).length;
            
            if (visibleCheckboxes.length > 0) {
                selectAllCheckbox.checked = checkedVisibleCount === visibleCheckboxes.length;
                selectAllCheckbox.indeterminate = checkedVisibleCount > 0 && checkedVisibleCount < visibleCheckboxes.length;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            }
        };
        
        searchInput.addEventListener('input', searchHandler);
        
        // پشتیبانی از کلید Enter برای اعمال فیلتر
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                // اعمال فیلتر با مقادیر فعلی انتخاب شده
                applyBtn.click();
            }
        });
        
        // عملکرد دکمه‌ها
        applyBtn.addEventListener('click', () => {
            // فقط مقادیر visible و checked را در نظر بگیریم
            const visibleCheckedValues = Array.from(valuesList.querySelectorAll('.filter-value-item:not(:first-child)'))
                .filter(item => {
                    const checkbox = item.querySelector('input[type="checkbox"]');
                    const isVisible = item.style.display !== 'none';
                    return isVisible && checkbox && checkbox.checked;
                })
                .map(item => item.querySelector('input[type="checkbox"]').value);
            
            const filterType = modal.querySelector('input[name="filterType"]:checked').value;
            
            if (visibleCheckedValues.length > 0) {
                this.currentFilters[columnId] = {
                    values: visibleCheckedValues,
                    type: filterType
                };
            } else {
                delete this.currentFilters[columnId];
            }
            
            this.currentPage = 1;
            this.applyFilters();
            modal.remove();
        });
        
        clearBtn.addEventListener('click', () => {
            delete this.currentFilters[columnId];
            this.currentPage = 1;
            this.applyFilters();
            modal.remove();
        });
        
        cancelBtn.addEventListener('click', () => {
            modal.remove();
        });
        
        // بستن با کلیک روی backdrop
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
        
        // بستن با ESC
        document.addEventListener('keydown', function escapeHandler(e) {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', escapeHandler);
            }
        });
        
        // اضافه کردن انیمیشن نمایش
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
    }
    
    toggleSort(columnId, direction) {
        this.currentSort = {
            column: columnId,
            direction: direction
        };
        
        this.currentPage = 1;
        this.applyFilters();
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
            formData.append('section', this.section);
            
            // دریافت مقدار global_search از input
            const globalSearchInput = document.querySelector('#globalSearch, #global_search, [name="global_search"]');
            const globalSearchValue = globalSearchInput ? globalSearchInput.value.trim() : '';
            if (globalSearchValue) {
                formData.append('global_search', globalSearchValue);
            }
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateTableContent(data.data, data.pagination);
                this.updateFilterIndicators();
                this.showToast(`${data.data.length} رکورد بارگذاری شد`, 'success');
            } else {
                throw new Error(data.message || 'خطا در اعمال فیلتر');
            }
            
        } catch (error) {
            console.error('خطا در اعمال فیلتر:', error);
            this.showToast(`خطا: ${error.message}`, 'error');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    updateTableContent(data, pagination) {
        const tbody = this.tableElement.querySelector('tbody');
        if (!tbody) {
            console.error('❌ tbody پیدا نشد');
            return;
        }
        
        // پاک کردن محتوای قبلی
        tbody.innerHTML = '';
        
        if (data.length === 0) {
            const noDataRow = document.createElement('tr');
            noDataRow.className = 'no-data-row';
            noDataRow.innerHTML = `<td colspan="100%" class="text-center py-4">هیچ رکوردی یافت نشد</td>`;
            tbody.appendChild(noDataRow);
            
            // پاک کردن pagination
            this.updatePagination(null);
            this.updateRowCounter(null);
            return;
        }
        
        // اضافه کردن فقط رکوردهای صفحه فعلی (که از سرور آمده‌اند)
        data.forEach((purchase, index) => {
            const row = this.createTableRow(purchase);
            tbody.appendChild(row);
        });
        
        // بروزرسانی pagination اگر وجود دارد
        this.updatePagination(pagination);
        
        // بروزرسانی شمارنده
        this.updateRowCounter(pagination);
        
        // اتصال event listenerهای لازم برای آمار تجمعی و ویرایش گروهی
        this.connectEventListeners();
        
        // dispatch custom event برای اطلاع سایر اجزا
        document.dispatchEvent(new CustomEvent('tableFilterApplied', {
            detail: {
                tableId: this.tableId,
                section: this.section,
                filteredCount: pagination ? pagination.count : data.length
            }
        }));
    }
    
    connectEventListeners() {
        // اتصال event listenerهای آمار تجمعی
        if (window.purchaseAggregatedStats) {
            const checkboxes = this.tableElement.querySelectorAll('.row-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', (e) => {
                    window.purchaseAggregatedStats.handleRowSelection(e.target);
                });
            });
            
            // اتصال select all checkbox
            const selectAllCheckbox = this.tableElement.querySelector('.select-all-checkbox, .select-all-checkbox-archived');
            if (selectAllCheckbox) {
                selectAllCheckbox.addEventListener('change', (e) => {
                    if (this.section === 'archived') {
                        window.purchaseAggregatedStats.handleSelectAllArchived(e.target);
                    } else {
                        window.purchaseAggregatedStats.handleSelectAll(e.target);
                    }
                });
            }
        }
        
        // اتصال event listenerهای ویرایش گروهی
        if (window.bulkEditManager) {
            window.bulkEditManager.updateControlPanel();
        }
    }
    
    getStatusBadgeClass(statusText) {
        // نقشه‌برداری وضعیت‌ها به کلاس‌های رنگ Bootstrap
        const statusMap = {
            'آرشیو شده': 'table-status-badge bg-secondary text-white',
            'لغو شده': 'table-status-badge bg-danger text-white',
            'فوری': 'table-status-badge bg-danger text-white',
            'شروع شده': 'table-status-badge bg-light text-dark',
            'پیامک ارسال شده': 'table-status-badge bg-purple text-white',
            'ثبت خرید در بازارگاه': 'table-status-badge bg-warning text-dark',
            'ثبت تخصیص در بازارگاه': 'table-status-badge bg-navy text-white',
            'ارسال آدرس به واردکننده': 'table-status-badge bg-teal text-white',
            'در انتظار بارنامه': 'table-status-badge bg-primary text-white',
            'صدور بارنامه (ناقص)': 'table-status-badge bg-orange text-dark',
            'صدور بارنامه': 'table-status-badge bg-blue text-white',
            'بستن خرید در بازارگاه': 'table-status-badge bg-pink text-white',
            'پرداخت کسری': 'table-status-badge bg-secondary text-white',
            'دریافت سرک': 'table-status-badge bg-danger text-white',
            'پرداخت کسری / دریافت سرک': 'table-status-badge bg-brown text-white',
            'تسویه کامل': 'table-status-badge bg-success text-white',
            'صدور فاکتور': 'table-status-badge bg-indigo text-white'
        };
        
        return statusMap[statusText] || 'table-status-badge bg-light text-dark';
    }
    
    createTableRow(purchase) {
        const row = document.createElement('tr');
        
        // اضافه کردن data attributes لازم برای آمار تجمعی
        row.setAttribute('data-id', purchase.id);
        row.setAttribute('data-order-weight', purchase.raw_order_weight || 0);
        row.setAttribute('data-delivered-weight', purchase.raw_delivered_weight || 0);
        row.setAttribute('data-company-price', purchase.raw_company_price || 0);
        row.setAttribute('data-customer-price', purchase.raw_customer_price || 0);
        row.setAttribute('data-amount-paid', purchase.raw_amount_paid || 0);
        row.setAttribute('data-is-factored', purchase.raw_is_factored ? 'true' : 'false');
        
        // تشخیص ستون‌های مورد نیاز بر اساس جدول
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        
        // checkbox
        const checkboxCell = document.createElement('td');
        checkboxCell.innerHTML = `<input type="checkbox" class="row-checkbox" data-id="${purchase.id}" value="${purchase.id}">`;
        row.appendChild(checkboxCell);
        
        // سایر ستون‌ها
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const cell = document.createElement('td');
            
            let cellValue = purchase[columnId] || '-';
            
            // فرمت‌بندی خاص برای انواع مختلف
            if (columnId === 'status') {
                cell.innerHTML = `<span class="badge ${this.getStatusBadgeClass(cellValue)}">${cellValue}</span>`;
            } else if (columnId === 'details' || columnId === 'جزئیات' || columnId === 'actions' || columnId === 'عملیات') {
                // ستون جزئیات/عملیات با لینک به صفحه purchase_CRUD
                cell.innerHTML = `
                    <div class="btn-group">
                        <a href="/erp/purchase_CRUD/${purchase.id}/" 
                           class="btn btn-sm btn-info" 
                           title="مشاهده جزئیات خرید">
                            <i class="fas fa-eye"></i> مشاهده
                        </a>
                        <button type="button" class="btn btn-outline-success btn-sm item-history-btn" 
                                data-id="${purchase.id}"
                                title="تاریخچه تغییرات">
                            <i class="fas fa-history"></i>
                        </button>
                    </div>
                `;
            } else if (['is_factored', 'is_urgent', 'is_canceled', 'is_archived', 'ready_for_invoice'].includes(columnId)) {
                const icon = cellValue === 'بله' ? '✓' : '✗';
                const colorClass = cellValue === 'بله' ? 'text-success' : 'text-danger';
                cell.innerHTML = `<span class="${colorClass}">${icon}</span>`;
            } else if (['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid', 'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit', 'extelaf_amount'].includes(columnId)) {
                cell.textContent = cellValue;
                cell.style.textAlign = 'left';
                cell.style.direction = 'ltr';
            } else {
                cell.textContent = cellValue;
            }
            
            row.appendChild(cell);
        });
        
        return row;
    }
    
    updateFilterIndicators() {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const filterBtn = header.querySelector('.filter-btn');
            
            if (filterBtn) {
                if (this.currentFilters[columnId]) {
                    filterBtn.style.background = '#1e6135';
                    filterBtn.style.color = 'white';
                    filterBtn.title = `فیلتر فعال: ${this.currentFilters[columnId].values.length} مورد`;
                } else {
                    filterBtn.style.background = 'white';
                    filterBtn.style.color = 'black';
                    filterBtn.title = 'فیلتر';
                }
            }
        });
        
        // نشانگر مرتب‌سازی
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const sortButtons = header.querySelectorAll('.sort-btn');
            
            sortButtons.forEach(btn => {
                btn.style.background = 'white';
                btn.style.color = 'black';
            });
            
            if (this.currentSort.column === columnId) {
                const targetBtn = header.querySelector(this.currentSort.direction === 'asc' ? 
                    '.sort-btn .fa-sort-up' : '.sort-btn .fa-sort-down').closest('.sort-btn');
                if (targetBtn) {
                    targetBtn.style.background = '#1e6135';
                    targetBtn.style.color = 'white';
                }
            }
        });
        
        // بروزرسانی باکس وضعیت فیلتر
        this.updateFilterStatusBox();
    }
    
    updateFilterStatusBox() {
        // پیدا کردن یا ایجاد container برای باکس فیلتر
        let filterStatusContainer = document.querySelector(`#${this.section}FilterStatus`);
        
        if (!filterStatusContainer) {
            filterStatusContainer = document.createElement('div');
            filterStatusContainer.id = `${this.section}FilterStatus`;
            filterStatusContainer.className = 'filter-status-container mb-3';
            
            // قرار دادن قبل از جدول
            const tableContainer = this.tableElement.closest('.table-responsive, .card-body') || this.tableElement.parentNode;
            tableContainer.insertBefore(filterStatusContainer, this.tableElement);
        }
        
        // بررسی وجود فیلتر فعال
        const activeFiltersCount = Object.keys(this.currentFilters).length;
        const hasSort = this.currentSort.column !== null;
        
        if (activeFiltersCount === 0 && !hasSort) {
            filterStatusContainer.style.display = 'none';
            return;
        }
        
        filterStatusContainer.style.display = 'block';
        
        // ایجاد محتوای باکس
        let filtersHTML = '';
        let totalFilteredItems = 0;
        
        // نمایش فیلترهای فعال با جزئیات کامل
        Object.entries(this.currentFilters).forEach(([columnId, filterData]) => {
            const header = this.tableElement.querySelector(`th[data-column-id="${columnId}"]`);
            const columnName = header ? header.textContent.replace(/[🔽🔼]/g, '').trim() : columnId;
            const typeText = filterData.type === 'include' ? 'شامل' : 'حذف';
            const typeIcon = filterData.type === 'include' ? 'fa-check-circle' : 'fa-times-circle';
            const typeClass = filterData.type === 'include' ? 'filter-type-include' : 'filter-type-exclude';
            
            totalFilteredItems += filterData.values.length;
            
            // نمایش تمام مقادیر در tooltip اگر بیش از 3 تا باشند
            const allValuesText = filterData.values.join('، ');
            const displayValuesText = filterData.values.length > 2 
                ? `${filterData.values.slice(0, 2).join('، ')} و ${filterData.values.length - 2} مورد دیگر`
                : filterData.values.join('، ');
            
            filtersHTML += `
                <div class="filter-status-item" data-filter-column="${columnId}">
                    <div class="filter-item-header">
                        <i class="fas fa-filter filter-icon"></i>
                        <span class="filter-column-name">${columnName}</span>
                        <span class="filter-type ${typeClass}">
                            <i class="fas ${typeIcon} me-1"></i>${typeText}
                        </span>
                        <span class="filter-count">(${filterData.values.length})</span>
                    </div>
                    <div class="filter-item-body">
                        <span class="filter-values" title="${allValuesText}">${displayValuesText}</span>
                    </div>
                    <button class="btn btn-sm btn-outline-danger remove-filter-btn" 
                            data-column-id="${columnId}" title="حذف این فیلتر">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
        });
        
        // نمایش مرتب‌سازی فعال با جزئیات
        if (hasSort) {
            const header = this.tableElement.querySelector(`th[data-column-id="${this.currentSort.column}"]`);
            const columnName = header ? header.textContent.replace(/[🔽🔼]/g, '').trim() : this.currentSort.column;
            const sortText = this.currentSort.direction === 'asc' ? 'صعودی' : 'نزولی';
            const sortIcon = this.currentSort.direction === 'asc' ? 'fa-sort-amount-up' : 'fa-sort-amount-down';
            
            filtersHTML += `
                <div class="filter-status-item sort-status-item" data-sort-column="${this.currentSort.column}">
                    <div class="filter-item-header">
                        <i class="fas fa-sort-amount-down filter-icon sort-icon"></i>
                        <span class="filter-column-name">مرتب‌سازی</span>
                        <span class="sort-type">
                            <i class="fas ${sortIcon} me-1"></i>${sortText}
                        </span>
                    </div>
                    <div class="filter-item-body">
                        <span class="sort-column">${columnName}</span>
                    </div>
                    <button class="btn btn-sm btn-outline-warning remove-sort-btn" title="حذف مرتب‌سازی">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
        }
        
        // محاسبه آمار کلی
        const totalActiveItems = activeFiltersCount + (hasSort ? 1 : 0);
        
        filterStatusContainer.innerHTML = `
            <div class="filter-status-box">
                <div class="filter-status-header">
                    <div class="header-left">
                        <h6 class="filter-status-title">
                            <i class="fas fa-sliders-h me-2"></i>
                            فیلترها و تنظیمات فعال
                        </h6>
                        <div class="filter-status-summary">
                            <span class="active-filters-count">${totalActiveItems} مورد فعال</span>
                            ${totalFilteredItems > 0 ? `<span class="filtered-items-count">${totalFilteredItems} گزینه فیلتر</span>` : ''}
                        </div>
                    </div>
                    <div class="header-right">
                        <button class="btn btn-sm btn-outline-secondary clear-all-filters-btn" title="پاک کردن همه فیلترها و تنظیمات">
                            <i class="fas fa-broom me-1"></i>
                            پاک کردن همه
                        </button>
                    </div>
                </div>
                <div class="filter-status-content">
                    ${filtersHTML}
                </div>
            </div>
        `;
        
        // اضافه کردن event listeners
        this.attachFilterStatusEventListeners(filterStatusContainer);
    }
    
    attachFilterStatusEventListeners(container) {
        // حذف فیلتر تکی
        container.querySelectorAll('.remove-filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const columnId = btn.dataset.columnId;
                delete this.currentFilters[columnId];
                this.currentPage = 1;
                this.applyFilters();
            });
        });
        
        // حذف مرتب‌سازی
        const removeSortBtn = container.querySelector('.remove-sort-btn');
        if (removeSortBtn) {
            removeSortBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.currentSort = { column: null, direction: 'asc' };
                this.currentPage = 1;
                this.applyFilters();
            });
        }
        
        // پاک کردن همه
        const clearAllBtn = container.querySelector('.clear-all-filters-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.currentFilters = {};
                this.currentSort = { column: null, direction: 'asc' };
                this.currentPage = 1;
                this.applyFilters();
            });
        }
    }
    
    updatePagination(pagination) {
        // پیدا کردن pagination container موجود در template
        const sectionName = this.section;
        let paginationContainer = document.querySelector(`#${sectionName}Pagination`);
        
        if (!paginationContainer) {
            // fallback: ایجاد container جدید اگر موجود نبود
            paginationContainer = document.createElement('div');
            paginationContainer.id = `${sectionName}Pagination`;
            paginationContainer.className = 'pagination-container mt-3';
            
            // اضافه کردن بعد از جدول
            const tableContainer = this.tableElement.closest('.table-responsive, .card-body') || this.tableElement.parentNode;
            tableContainer.appendChild(paginationContainer);
        }
        
        if (!pagination || pagination.num_pages <= 1) {
            // حذف nav elements موجود که توسط server filter ایجاد شده‌اند
            const serverNavs = paginationContainer.querySelectorAll('nav[data-server-filter]');
            serverNavs.forEach(nav => nav.remove());
            return;
        }
        
        // بروزرسانی pagination info
        this.updatePaginationInfo(paginationContainer, pagination);
        
        // حذف nav elements قبلی که توسط server filter ایجاد شده‌اند
        const existingServerNavs = paginationContainer.querySelectorAll('nav[data-server-filter]');
        existingServerNavs.forEach(nav => nav.remove());
        
        // ایجاد nav element جدید
        const navElement = document.createElement('nav');
        navElement.setAttribute('aria-label', `صفحه‌بندی ${sectionName}`);
        navElement.setAttribute('data-server-filter', 'true'); // علامت‌گذاری برای تشخیص
        
        // ساخت HTML صفحه‌بندی
        let paginationHTML = `<ul class="pagination justify-content-center">`;
        
        // دکمه صفحه قبلی
        if (pagination.has_previous) {
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1" data-section="${this.section}">
                        <i class="fas fa-angle-double-right"></i> اول
                    </a>
                </li>
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${pagination.number - 1}" data-section="${this.section}">
                        <i class="fas fa-angle-right"></i> قبلی
                    </a>
                </li>
            `;
        } else {
            paginationHTML += `
                <li class="page-item disabled">
                    <span class="page-link"><i class="fas fa-angle-double-right"></i> اول</span>
                </li>
                <li class="page-item disabled">
                    <span class="page-link"><i class="fas fa-angle-right"></i> قبلی</span>
                </li>
            `;
        }
        
        // شماره صفحات با الگوی موجود در template
        if (pagination.page_range && Array.isArray(pagination.page_range)) {
            pagination.page_range.forEach(pageNum => {
                if (pageNum === '...' || pageNum === -1) {
                    paginationHTML += `
                        <li class="page-item disabled">
                            <span class="page-link">...</span>
                        </li>
                    `;
                } else {
                    const isActive = pageNum === pagination.number;
                    paginationHTML += `
                        <li class="page-item ${isActive ? 'active' : ''}">
                            <a class="page-link" href="#" data-page="${pageNum}" data-section="${this.section}">${pageNum}</a>
                        </li>
                    `;
                }
            });
        } else {
            // fallback: نمایش صفحات بدون page_range
            const startPage = Math.max(1, pagination.number - 2);
            const endPage = Math.min(pagination.num_pages, pagination.number + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                const isActive = i === pagination.number;
                paginationHTML += `
                    <li class="page-item ${isActive ? 'active' : ''}">
                        <a class="page-link" href="#" data-page="${i}" data-section="${this.section}">${i}</a>
                    </li>
                `;
            }
        }
        
        // دکمه صفحه بعدی
        if (pagination.has_next) {
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${pagination.number + 1}" data-section="${this.section}">
                        بعدی <i class="fas fa-angle-left"></i>
                    </a>
                </li>
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${pagination.num_pages}" data-section="${this.section}">
                        آخر <i class="fas fa-angle-double-left"></i>
                    </a>
                </li>
            `;
        } else {
            paginationHTML += `
                <li class="page-item disabled">
                    <span class="page-link">بعدی <i class="fas fa-angle-left"></i></span>
                </li>
                <li class="page-item disabled">
                    <span class="page-link">آخر <i class="fas fa-angle-double-left"></i></span>
                </li>
            `;
        }
        
        paginationHTML += `</ul>`;
        navElement.innerHTML = paginationHTML;
        
        // اضافه کردن nav به container
        paginationContainer.appendChild(navElement);
        
        // اضافه کردن event listenerها
        navElement.querySelectorAll('.page-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const pageNum = parseInt(link.dataset.page);
                const section = link.dataset.section;
                
                // بررسی اینکه لینک مربوط به همین بخش باشد
                if (section === this.section && pageNum && pageNum !== this.currentPage) {
                    this.currentPage = pageNum;
                    this.applyFilters();
                }
            });
        });
    }
    
    updatePaginationInfo(paginationContainer, pagination) {
        // بروزرسانی pagination-info
        let paginationInfo = paginationContainer.querySelector('.pagination-info');
        if (!paginationInfo) {
            paginationInfo = document.createElement('div');
            paginationInfo.className = 'pagination-info d-flex justify-content-between align-items-center mb-3';
            paginationContainer.insertBefore(paginationInfo, paginationContainer.firstChild);
        }
        
        // محاسبه شاخص‌ها
        const startIndex = ((pagination.number - 1) * this.perPage) + 1;
        const endIndex = Math.min(pagination.number * this.perPage, pagination.count);
        
        // نام بخش برای نمایش
        const sectionNames = {
            'active': 'خرید فعال',
            'pending': 'خرید در انتظار پرداخت', 
            'archived': 'خرید آرشیو شده'
        };
        const sectionName = sectionNames[this.section] || 'خرید';
        
        paginationInfo.innerHTML = `
            <div class="pagination-details">
                <span class="text-muted">نمایش ${startIndex} تا ${endIndex} از ${pagination.count} ${sectionName}</span>
            </div>
            <div class="pagination-per-page">
                <label for="${this.section}PerPageFilter" class="form-label me-2">تعداد در هر صفحه:</label>
                <select id="${this.section}PerPageFilter" class="form-select form-select-sm d-inline-block w-auto">
                    <option value="5" ${this.perPage == 5 ? 'selected' : ''}>5</option>
                    <option value="10" ${this.perPage == 10 ? 'selected' : ''}>10</option>
                    <option value="25" ${this.perPage == 25 ? 'selected' : ''}>25</option>
                    <option value="50" ${this.perPage == 50 ? 'selected' : ''}>50</option>
                    <option value="100" ${this.perPage == 100 ? 'selected' : ''}>100</option>
                    <option value="200" ${this.perPage == 200 ? 'selected' : ''}>200</option>
                </select>
            </div>
        `;
        
        // Event listener برای تغییر per page
        const perPageSelect = paginationInfo.querySelector(`#${this.section}PerPageFilter`);
        if (perPageSelect && !perPageSelect.hasAttribute('data-listener-added')) {
            perPageSelect.setAttribute('data-listener-added', 'true');
            perPageSelect.addEventListener('change', (e) => {
                this.perPage = parseInt(e.target.value);
                this.currentPage = 1; // بازگشت به صفحه اول
                this.applyFilters();
            });
        }
    }
    
    updateRowCounter(pagination) {
        // بروزرسانی شمارنده رکوردها
        const tableId = this.tableId.replace('#', ''); // حذف # اگر وجود دارد
        const counter = document.querySelector(`#${tableId} + .row-counter, .${tableId}-counter`);
        if (counter && pagination) {
            counter.textContent = `نمایش ${pagination.count} رکورد`;
        }
    }
    
    async loadInitialData() {
        // بارگذاری اولیه داده‌ها
        await this.applyFilters();
    }
    
    showLoading() {
        const tbody = this.tableElement.querySelector('tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="100%" class="text-center py-4"><i class="fas fa-spinner fa-spin"></i> در حال بارگذاری...</td></tr>';
        }
    }
    
    hideLoading() {
        // این متد در applyFilters صدا زده می‌شود
    }
    
    showToast(message, type = 'info') {
        // ایجاد Toast notification با انیمیشن و استایل حرفه‌ای
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        
        // اضافه کردن آیکون مناسب
        let icon = '';
        switch(type) {
            case 'success':
                icon = '<i class="fas fa-check-circle me-2"></i>';
                break;
            case 'error':
                icon = '<i class="fas fa-exclamation-circle me-2"></i>';
                break;
            case 'warning':
                icon = '<i class="fas fa-exclamation-triangle me-2"></i>';
                break;
            default:
                icon = '<i class="fas fa-info-circle me-2"></i>';
        }
        
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                ${icon}
                <span>${message}</span>
                <button type="button" class="btn-close btn-close-white ms-auto" aria-label="Close"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Event listener برای دکمه بستن
        const closeBtn = toast.querySelector('.btn-close');
        closeBtn.addEventListener('click', () => {
            toast.style.animation = 'slideOutRight 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        });
        
        // حذف خودکار بعد از 4 ثانیه
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.animation = 'slideOutRight 0.3s ease-in forwards';
                setTimeout(() => toast.remove(), 300);
            }
        }, 4000);
        
        // انیمیشن کلیک برای بستن
        toast.addEventListener('click', () => {
            toast.style.animation = 'slideOutRight 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        });
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
}

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    // راه‌اندازی فیلتر برای هر جدول به صورت جداگانه
    const tables = [
        '#activePurchasesTable',
        '#pendingPurchasesTable', 
        '#archivedPurchasesTable'
    ];
    
    tables.forEach(tableSelector => {
        const tableElement = document.querySelector(tableSelector);
        if (tableElement && tableElement.classList.contains('python-excel-filter')) {
            new PurchaseServerFilter(tableSelector);
        }
    });
}); 