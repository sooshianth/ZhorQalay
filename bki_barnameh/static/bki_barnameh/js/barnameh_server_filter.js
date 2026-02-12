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
        this.perPage = 100;
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
            return parseInt(selectedValue) || 100;
        }
        return 100;
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
                    this.perPage = parseInt(selectedValue) || 100;
                }
                this.currentPage = 1; // بازگشت به صفحه اول
                this.applyFilters();
            });
        }
    }
    
    setupGlobalSearchHandler() {
        const globalSearchInput = document.getElementById('globalBarnamehSearch');
        
        if (globalSearchInput) {
            let searchTimeout;
            
            const triggerServerSearch = () => {
                const searchValue = globalSearchInput.value.trim();
                
                // اگر مقدار جستجو با مقدار قبلی تفاوتی نداشت، کاری نکن
                if (searchValue === this.globalSearch) {
                    return;
                }
                
                this.globalSearch = searchValue; // مقدار جستجو را در پراپرتی کلاس ذخیره کن
                this.currentPage = 1; // همیشه به صفحه اول برگرد
                this.applyFilters(); // <<< تابع اصلی برای ارسال درخواست به سرور
            };
    
            globalSearchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                // با یک تأخیر کوتاه درخواست را ارسال می‌کنیم تا برای هر حرف تایپ شده، درخواست ارسال نشود
                searchTimeout = setTimeout(triggerServerSearch, 400); 
            });
    
            // دکمه پاک کردن جستجو
            const clearButton = document.getElementById('clearBarnamehSearch');
            if (clearButton) {
                clearButton.addEventListener('click', () => {
                    globalSearchInput.value = '';
                    triggerServerSearch(); // جستجوی خالی را به سرور بفرست تا همه نتایج برگردد
                });
            }
            
            // اضافه کردن event listener برای Enter key
            globalSearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(searchTimeout); // تایمر را متوقف کن چون کاربر Enter زده
                    triggerServerSearch();
                }
            });
            
            console.log('Global search handler setup completed with SERVER-SIDE search');
        } else {
            console.warn('Global search input not found');
        }
    }
        
    performClientSideSearch(searchTerm) {
        console.log('Performing client-side search for:', searchTerm);
        
        const tbody = this.table.querySelector('tbody');
        if (!tbody) return;
        
        const rows = tbody.querySelectorAll('tr.barnameh-row');
        let visibleCount = 0;
        
        // تبدیل اعداد فارسی به انگلیسی برای جستجو بهتر
        const normalizeSearchTerm = (text) => {
            return text
                .replace(/۰/g, '0')
                .replace(/۱/g, '1')
                .replace(/۲/g, '2')
                .replace(/۳/g, '3')
                .replace(/۴/g, '4')
                .replace(/۵/g, '5')
                .replace(/۶/g, '6')
                .replace(/۷/g, '7')
                .replace(/۸/g, '8')
                .replace(/۹/g, '9')
                .toLowerCase();
        };
        
        const normalizedSearchTerm = normalizeSearchTerm(searchTerm);
        
        // اگر جستجو خالی است، همه ردیف‌ها را نمایش بده و highlight را حذف کن
        if (!searchTerm) {
            rows.forEach(row => {
                row.style.display = '';
                row.classList.remove('search-highlight'); // حذف highlight
                visibleCount++;
            });
            console.log(`Showing all ${rows.length} rows`);
            return;
        }
        
        // جستجو در ردیف‌ها
        rows.forEach(row => {
            // جستجو در فیلدهای مختلف - گسترش یافته
            const number = row.getAttribute('data-number') || '';
            const serial = row.getAttribute('data-serial') || '';
            const tonnage = row.getAttribute('data-tonnage') || '';
            const status = row.getAttribute('data-status') || '';
            const driverName = row.getAttribute('data-driver-name') || '';
            const driverPhone = row.getAttribute('data-driver-phone') || '';
            const vehiclePlate = row.getAttribute('data-vehicle-plate') || '';
            const receiverName = row.getAttribute('data-receiver-name') || '';
            const destination = row.getAttribute('data-destination') || '';
            const barnamehDate = row.getAttribute('data-barnameh-date') || '';
            const purchaseNumber = row.getAttribute('data-purchase-number') || '';
            const shenaseCode = row.getAttribute('data-shenase-takhsis-code') || '';
            const factorSeason = row.getAttribute('data-factor-sodoor-season') || '';
            
            // تبدیل وضعیت به فارسی برای جستجو
            let statusText = '';
            if (status === 'NOT_SENT_TO_BKI') {
                statusText = 'ارسال نشده به بازارگاه';
            } else if (status === 'SENT_TO_BKI') {
                statusText = 'ارسال شده به بازارگاه';
            }
            
            const searchFields = [
                number, serial, tonnage, statusText, driverName, driverPhone, vehiclePlate,
                receiverName, destination, barnamehDate, purchaseNumber, shenaseCode, factorSeason
            ].join(' ').toLowerCase();
            
            // جستجو در محتوای سلول‌های جدول نیز
            const cellTexts = [];
            const cells = row.querySelectorAll('td');
            cells.forEach(cell => {
                const cellText = cell.textContent.trim();
                if (cellText && cellText !== '-') {
                    cellTexts.push(cellText);
                }
            });
            
            const allSearchableText = searchFields + ' ' + cellTexts.join(' ').toLowerCase();
            const normalizedSearchableText = normalizeSearchTerm(allSearchableText);
            
            // جستجوی جزئی - اگر کلمه جستجو در هر بخشی از متن باشد
            const searchWords = normalizedSearchTerm.split(/\s+/).filter(word => word.length > 0);
            const isVisible = searchWords.every(word => normalizedSearchableText.includes(word));
            
            if (isVisible) {
                row.style.display = '';
                visibleCount++;
                // اضافه کردن highlight به ردیف‌های یافت شده
                row.classList.add('search-highlight');
            } else {
                row.style.display = 'none';
                row.classList.remove('search-highlight');
            }
        });
        
        // نمایش پیام نتیجه
        if (searchTerm) {
            this.showToast(`${visibleCount} بارنامه برای "${searchTerm}" یافت شد`, 'success');
        }
        
        console.log(`Search completed: ${visibleCount} results found for "${searchTerm}"`);
    }
    
    setupFilterButtons() {
        const filterableHeaders = this.table.querySelectorAll('th[data-column-id]:not([data-column-id="actions"]):not([data-column-id="select"])');
        
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
        
        // نمایش یک loading indicator کوچک بدون تغییر جدول
        const loadingToast = this.showToast('در حال بارگذاری مقادیر فیلتر...', 'info');
        
        try {
            // دریافت مقادیر از سرور
            const serverValues = await this.getColumnValues(columnId);
            console.log(`Retrieved ${serverValues.length} values for column ${columnId}`);
            
            // ایجاد modal
            this.createFilterModal(columnId, columnType, serverValues, headerElement);
            
        } catch (error) {
            console.error('Error loading filter modal:', error);
            this.showToast('خطا در بارگذاری فیلتر', 'error');
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
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-filter me-2"></i>
                            فیلتر ${headerText}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <!-- نوع فیلتر -->
                        <div class="mb-3">
                            <label class="form-label">نوع فیلتر:</label>
                            <div class="btn-group w-100" role="group">
                                <input type="radio" class="btn-check" name="filterType" id="includeType" value="include" ${currentType === 'include' ? 'checked' : ''}>
                                <label class="btn btn-outline-success" for="includeType">شامل</label>
                                
                                <input type="radio" class="btn-check" name="filterType" id="excludeType" value="exclude" ${currentType === 'exclude' ? 'checked' : ''}>
                                <label class="btn btn-outline-danger" for="excludeType">حذف</label>
                            </div>
                        </div>
                        
                        <!-- جستجو در مقادیر -->
                        <div class="mb-3">
                            <label for="filterSearch" class="form-label">جستجو در مقادیر:</label>
                            <input type="text" id="valueSearchInput" class="form-control" placeholder="تایپ کنید...">
                        </div>
                        
                        <!-- دکمه‌های مرتب‌سازی -->
                        <div class="mb-3">
                            <label class="form-label">مرتب‌سازی:</label>
                            <div class="btn-group w-100" role="group">
                                <button type="button" class="btn btn-outline-primary sort-btn" data-direction="asc" id="sortAscBtn">
                                    <i class="fas fa-sort-amount-up me-2"></i>صعودی
                                </button>
                                <button type="button" class="btn btn-outline-primary sort-btn" data-direction="desc" id="sortDescBtn">
                                    <i class="fas fa-sort-amount-down me-2"></i>نزولی
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
                            <i class="fas fa-times me-1"></i>لغو
                        </button>
                        <button type="button" class="btn btn-warning" id="clearFilterBtn">
                            <i class="fas fa-times me-1"></i>حذف فیلتر
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
        const sortAscBtn = modal.querySelector('#sortAscBtn');
        const sortDescBtn = modal.querySelector('#sortDescBtn');
        const clearFilterBtn = modal.querySelector('#clearFilterBtn');
        const applyFilterBtn = modal.querySelector('#applyFilterBtn');
        
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
        
        // دکمه‌های مرتب‌سازی
        sortAscBtn.addEventListener('click', () => {
            this.currentSort = { column: columnId, direction: 'asc' };
            this.currentPage = 1;
            this.applyFilters();
            bootstrap.Modal.getInstance(modal).hide();
        });
        
        sortDescBtn.addEventListener('click', () => {
            this.currentSort = { column: columnId, direction: 'desc' };
            this.currentPage = 1;
            this.applyFilters();
            bootstrap.Modal.getInstance(modal).hide();
        });
        
        // پاک کردن فیلتر
        clearFilterBtn.addEventListener('click', () => {
            delete this.currentFilters[columnId];
            this.currentPage = 1;
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
        
        // اضافه کردن انتخاب همه در ابتدا
        const selectAllHtml = `
            <div class="form-check mb-2 border-bottom pb-2">
                <input class="form-check-input" type="checkbox" id="selectAll" checked>
                <label class="form-check-label fw-bold" for="selectAll">
                    انتخاب همه (${serverValues.length})
                </label>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', selectAllHtml);
        
        serverValues.forEach(valueObj => {
            const value = valueObj.value || valueObj;
            const display = valueObj.display || value;
            // همه موارد در ابتدا انتخاب شده باشند (اگر فیلتر قبلی نداشته باشیم)
            const isChecked = currentValues.length === 0 ? true : currentValues.includes(value);
            
            const checkboxHtml = `
                <div class="form-check mb-2">
                    <input class="form-check-input value-checkbox" type="checkbox" 
                           value="${value}" id="val_${value}" ${isChecked ? 'checked' : ''}>
                    <label class="form-check-label w-100" for="val_${value}" 
                           style="cursor: pointer; padding: 5px 0;">
                        ${display}
                    </label>
                </div>
            `;
            
            container.insertAdjacentHTML('beforeend', checkboxHtml);
        });
        
        // مدیریت انتخاب همه
        const selectAllCheckbox = container.querySelector('#selectAll');
        selectAllCheckbox.addEventListener('change', function() {
            const valueCheckboxes = container.querySelectorAll('.value-checkbox');
            valueCheckboxes.forEach(cb => cb.checked = this.checked);
        });
        
        // مدیریت تغییر checkbox های جزئی
        container.addEventListener('change', function(e) {
            if (e.target.classList.contains('value-checkbox')) {
                const allCheckboxes = container.querySelectorAll('.value-checkbox');
                const checkedCheckboxes = container.querySelectorAll('.value-checkbox:checked');
                
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
            console.log('Applying filters with global search:', this.globalSearch);
            
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
            
            console.log('Sending request to:', this.filterUrl);
            console.log('Form data:', {
                filters: this.currentFilters,
                sort: this.currentSort,
                page: this.currentPage,
                per_page: this.perPage,
                global_search: this.globalSearch
            });
            
            const response = await fetch(this.filterUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const responseText = await response.text();
            console.log('Response text:', responseText);
            
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (parseError) {
                console.error('JSON parse error:', parseError);
                throw new Error('Invalid JSON response from server');
            }
            
            console.log('Filter response:', data);
            
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
                
                // نمایش پیام موفقیت فقط اگر جستجو انجام شده باشد
                if (this.globalSearch) {
                    this.showToast(`${data.data.length} بارنامه برای "${this.globalSearch}" یافت شد`, 'success');
                } else if (Object.keys(this.currentFilters).length > 0) {
                    this.showToast(`${data.data.length} بارنامه یافت شد`, 'success');
                }
            } else {
                throw new Error(data.message || 'خطا در اعمال فیلتر');
            }
            
        } catch (error) {
            console.error('Error applying filters:', error);
            this.showToast('خطا در اعمال فیلتر: ' + error.message, 'error');
            
            // در صورت خطا، جدول را به حالت عادی برگردان
            this.hideLoading();
            const tbody = this.table.querySelector('tbody');
            if (tbody) {
                const colCount = this.table.querySelectorAll('thead th').length;
                tbody.innerHTML = `
                    <tr>
                        <td colspan="${colCount}" class="text-center py-4">
                            <i class="fas fa-exclamation-triangle text-danger" style="font-size: 2rem;"></i>
                            <p class="text-danger mt-2">خطا در بارگذاری داده‌ها</p>
                            <small class="text-muted">${error.message}</small>
                        </td>
                    </tr>
                `;
            }
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
            <td class="text-center" data-column="select">
                <input type="checkbox" class="row-checkbox" data-id="${barnameh.id}" 
                       value="${barnameh.id}"
                       style="width: 18px; height: 18px; cursor: pointer;" 
                       onchange="toggleRowSelection(this)">
            </td>
        `;
        
        visibleColumns.forEach(columnId => {
            if (columnId === 'select') {
                // قبلاً اضافه شده
                return;
            } else if (columnId === 'number') {
                const factorBadge = barnameh.factor_exported_at ? '<span class="badge bg-secondary ms-1" title="خروجی فاکتور گرفته شده"><i class="fas fa-file-invoice"></i></span>' : '';
                rowHtml += `<td class="column-number" data-column="number">${barnameh.number || "-"}${factorBadge}</td>`;
            } else if (columnId === 'serial') {
                rowHtml += `<td class="column-serial" data-column="serial">${barnameh.serial || "-"}</td>`;
            } else if (columnId === 'tonnage') {
                rowHtml += `<td class="column-tonnage" data-column="tonnage">${barnameh.tonnage || "-"}</td>`;
            } else if (columnId === 'status') {
                const statusText = barnameh.status_display || barnameh.status || "";
                const statusClass = this.getStatusBadgeClass(statusText);
                rowHtml += `<td class="column-status" data-column="status">
                    <span class="badge rounded-pill ${statusClass}">${statusText}</span>
                </td>`;
            } else if (columnId === 'driver_name') {
                rowHtml += `<td class="column-driver_name" data-column="driver_name">${barnameh.driver_name || "-"}</td>`;
            } else if (columnId === 'driver_phone') {
                rowHtml += `<td class="column-driver_phone" data-column="driver_phone">${barnameh.driver_phone || "-"}</td>`;
            } else if (columnId === 'vehicle_plate') {
                rowHtml += `<td class="column-vehicle_plate" data-column="vehicle_plate">${barnameh.vehicle_plate || "-"}</td>`;
            } else if (columnId === 'receiver_name') {
                rowHtml += `<td class="column-receiver_name" data-column="receiver_name">${barnameh.receiver_name || "-"}</td>`;
            } else if (columnId === 'destination') {
                rowHtml += `<td class="column-destination" data-column="destination">${barnameh.destination || "-"}</td>`;
            } else if (columnId === 'barnameh_date') {
                rowHtml += `<td class="column-barnameh_date" data-column="barnameh_date">${barnameh.barnameh_date || "-"}</td>`;
            } else if (columnId === 'transport_date') {
                rowHtml += `<td class="column-transport_date" data-column="transport_date">${barnameh.transport_date || "-"}</td>`;
            } else if (columnId === 'purchase_number') {
                rowHtml += `<td class="column-purchase_number" data-column="purchase_number">${barnameh.purchase_number || "-"}</td>`;
            } else if (columnId === 'shenase_takhsis_code') {
                rowHtml += `<td class="column-shenase_takhsis_code" data-column="shenase_takhsis_code">${barnameh.shenase_takhsis_code || "-"}</td>`;
            } else if (columnId === 'cargo') {
                rowHtml += `<td class="column-cargo" data-column="cargo">${barnameh.cargo || "-"}</td>`;
            } else if (columnId === 'company_price') {
                rowHtml += `<td class="column-company_price" data-column="company_price">${barnameh.company_price || "-"}</td>`;
            } else if (columnId === 'customer_price') {
                rowHtml += `<td class="column-customer_price" data-column="customer_price">${barnameh.customer_price || "-"}</td>`;
            } else if (columnId === 'total_sales_amount') {
                rowHtml += `<td class="column-total_sales_amount" data-column="total_sales_amount">${barnameh.total_sales_amount || "-"}</td>`;
            } else if (columnId === 'total_purchase_amount') {
                rowHtml += `<td class="column-total_purchase_amount" data-column="total_purchase_amount">${barnameh.total_purchase_amount || "-"}</td>`;
            } else if (columnId === 'buyer_name') {
                rowHtml += `<td class="column-buyer_name" data-column="buyer_name">${barnameh.buyer_name || "-"}</td>`;
            } else if (columnId === 'buyer_national_code') {
                rowHtml += `<td class="column-buyer_national_code" data-column="buyer_national_code">${barnameh.buyer_national_code || "-"}</td>`;
            } else if (columnId === 'buyer_postal_code') {
                rowHtml += `<td class="column-buyer_postal_code" data-column="buyer_postal_code">${barnameh.buyer_postal_code || "-"}</td>`;
            } else if (columnId === 'buyer_address') {
                rowHtml += `<td class="column-buyer_address" data-column="buyer_address">${barnameh.buyer_address || "-"}</td>`;
            } else if (columnId === 'demand_amount') {
                rowHtml += `<td class="column-demand_amount" data-column="demand_amount">${barnameh.demand_amount || "-"}</td>`;
            } else if (columnId === 'importer') {
                rowHtml += `<td class="column-importer" data-column="importer">${barnameh.importer || "-"}</td>`;
            } else if (columnId === 'product_type') {
                rowHtml += `<td class="column-product_type" data-column="product_type">${barnameh.product_type || "-"}</td>`;
            } else if (columnId === 'product_country') {
                rowHtml += `<td class="column-product_country" data-column="product_country">${barnameh.product_country || "-"}</td>`;
            } else if (columnId === 'successful_send_date') {
                rowHtml += `<td class="column-successful_send_date" data-column="successful_send_date">${barnameh.successful_send_date || "-"}</td>`;
            } else if (columnId === 'is_sent_to_bki') {
                const isSentToBki = barnameh.is_sent_to_bki;
                rowHtml += `<td class="column-is_sent_to_bki" data-column="is_sent_to_bki">
                    ${isSentToBki ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'factor_sodoor_season') {
                rowHtml += `<td class="column-factor_sodoor_season" data-column="factor_sodoor_season">${barnameh.factor_sodoor_season || "-"}</td>`;
            } else if (columnId === 'is_factored') {
                const isFactored = barnameh.is_factored;
                rowHtml += `<td class="column-is_factored" data-column="is_factored">
                    ${isFactored ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'is_created_by_excel') {
                const isCreatedByExcel = barnameh.is_created_by_excel;
                rowHtml += `<td class="column-is_created_by_excel" data-column="is_created_by_excel">
                    ${isCreatedByExcel ? '<span class="badge bg-success">بله</span>' : '<span class="badge bg-secondary">خیر</span>'}
                </td>`;
            } else if (columnId === 'factor_date') {
                rowHtml += `<td class="column-factor_date" data-column="factor_date">${barnameh.factor_date || "-"}</td>`;
            } else if (columnId === 'created_at') {
                rowHtml += `<td class="column-created_at" data-column="created_at">${barnameh.created_at || "-"}</td>`;
            } else if (columnId === 'actions') {
                rowHtml += `<td class="text-center" data-column="actions">
                    <div class="btn-group">
                        <a href="/bki/barnameh/detail/${barnameh.id}/" 
                           class="btn btn-info btn-sm rounded-circle" 
                           data-bs-toggle="tooltip" title="مشاهده جزئیات">
                            <i class="fas fa-eye"></i>
                        </a>
                        ${!barnameh.is_sent_to_bki ? `
                            <a href="/bki/barnameh/edit/${barnameh.id}/" 
                               class="btn btn-warning btn-sm rounded-circle ms-1" 
                               data-bs-toggle="tooltip" title="ویرایش">
                                <i class="fas fa-edit"></i>
                            </a>
                            <form action="/bki/barnameh/delete/${barnameh.id}/" method="post" 
                                  class="d-inline" 
                                  onsubmit="return confirm('آیا از حذف این بارنامه اطمینان دارید؟');">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${this.getCSRFToken()}">
                                <button type="submit" class="btn btn-danger btn-sm rounded-circle ms-1" 
                                        data-bs-toggle="tooltip" title="حذف">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </form>
                            <form action="/bki/barnameh/send-to-bki/${barnameh.id}/" method="post" class="d-inline">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${this.getCSRFToken()}">
                                <button type="submit" class="btn btn-primary btn-sm rounded-circle ms-1" 
                                        data-bs-toggle="tooltip" title="ارسال به بازارگاه">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </form>
                        ` : `
                            <a href="/bki/barnameh/edit-in-bki/${barnameh.id}/" 
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
            'ارسال نشده به بازارگاه': 'bg-warning text-dark',
            'ارسال شده به بازارگاه': 'bg-success',
            'NOT_SENT_TO_BKI': 'bg-warning text-dark',
            'SENT_TO_BKI': 'bg-success'
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
            const headerContainer = header.querySelector('.d-flex');
            
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
            
            // اضافه کردن اندیکاتور مرتب‌سازی
            if (headerContainer) {
                // حذف اندیکاتور قبلی
                const existingSortIcon = headerContainer.querySelector('.sort-indicator');
                if (existingSortIcon) {
                    existingSortIcon.remove();
                }
                
                // اضافه کردن اندیکاتور جدید اگر این ستون مرتب شده باشد
                if (this.currentSort.column === columnId) {
                    const sortIcon = document.createElement('span');
                    sortIcon.className = 'sort-indicator ms-1';
                    sortIcon.style.cssText = 'color: #ffc107; font-size: 12px;';
                    
                    if (this.currentSort.direction === 'asc') {
                        sortIcon.innerHTML = '<i class="fas fa-sort-up"></i>';
                        sortIcon.title = 'مرتب‌سازی صعودی';
                    } else {
                        sortIcon.innerHTML = '<i class="fas fa-sort-down"></i>';
                        sortIcon.title = 'مرتب‌سازی نزولی';
                    }
                    
                    headerContainer.appendChild(sortIcon);
                }
            }
        });
    }
    
    updateFilterStatusBox() {
        // ایجاد یا به‌روزرسانی جعبه وضعیت فیلتر
        let statusBox = document.getElementById('filterStatusBox');
        
        const activeFiltersCount = Object.keys(this.currentFilters).length;
        const hasGlobalSearch = this.globalSearch.length > 0;
        const hasSort = this.currentSort.column !== null;
        
        if (activeFiltersCount === 0 && !hasGlobalSearch && !hasSort) {
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
        
        // اضافه کردن اطلاعات مرتب‌سازی
        if (hasSort) {
            const columnName = this.getColumnName(this.currentSort.column);
            const sortDirection = this.currentSort.direction === 'asc' ? 'صعودی' : 'نزولی';
            const sortIcon = this.currentSort.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down';
            
            content += `<span class="badge bg-info me-1">
                <i class="fas ${sortIcon} me-1"></i>مرتب‌سازی: ${columnName} (${sortDirection})
                <button type="button" class="btn-close btn-close-white btn-sm ms-1" 
                        onclick="clearSort()" aria-label="حذف مرتب‌سازی"></button>
            </span>`;
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
        
        // تابع سراسری برای پاک کردن جستجو
        window.clearBarnamehSearch = () => {
            const globalSearchInput = document.getElementById('globalBarnamehSearch');
            if (globalSearchInput) {
                globalSearchInput.value = '';
            }
            if (this) {
                this.globalSearch = '';
                this.currentPage = 1;
                this.applyFilters();
            }
        };
        
        window.removeFilter = (columnId) => {
            delete this.currentFilters[columnId];
            this.currentPage = 1;
            this.applyFilters();
        };
        
        window.clearSort = () => {
            this.currentSort = { column: null, direction: null };
            this.currentPage = 1;
            this.applyFilters();
        };
        
        window.clearAllFilters = () => {
            this.currentFilters = {};
            this.globalSearch = '';
            this.currentSort = { column: null, direction: null };
            const globalSearchInput = document.getElementById('globalBarnamehSearch');
            if (globalSearchInput) {
                globalSearchInput.value = '';
            }
            this.currentPage = 1;
            this.applyFilters();
        };
    }
    
    updatePagination(pagination) {
        // پیدا کردن یا ایجاد container pagination
        let paginationContainer = document.querySelector('#barnameh-server-pagination');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'barnameh-server-pagination';
            paginationContainer.className = 'pagination-container mt-4';
            
            // اضافه کردن بعد از جدول
            const tableContainer = this.table.closest('.table-container') || this.table.parentNode;
            tableContainer.insertAdjacentElement('afterend', paginationContainer);
        }
        
        this.currentPage = pagination.current_page;
        this.totalPages = pagination.total_pages;
        this.totalCount = pagination.count;
        
        // بروزرسانی اطلاعات pagination
        this.updatePaginationInfo(paginationContainer, pagination);
    }
    
    updatePaginationInfo(paginationContainer, pagination) {
        let paginationHtml = '';
        
        const startIndex = ((pagination.current_page - 1) * this.perPage) + 1;
        const endIndex = Math.min(pagination.current_page * this.perPage, pagination.count);
        
        // اطلاعات pagination
        paginationHtml += `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <p class="text-muted mb-0">
                        نمایش ${startIndex} تا ${endIndex} از ${pagination.count} بارنامه
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
        // به‌روزرسانی شمارنده کل در بالای صفحه
        const counterElements = document.querySelectorAll('.total-count, #totalBarnamehCount');
        counterElements.forEach(element => {
            element.textContent = pagination.count.toLocaleString('fa-IR');
        });
    }
    
    async loadInitialData() {
        // بررسی اینکه آیا جدول از قبل داده دارد یا خیر
        const tbody = this.table.querySelector('tbody');
        const existingRows = tbody ? tbody.querySelectorAll('tr.barnameh-row') : [];
        
        // اگر جدول از قبل داده دارد، فقط pagination را اماده کن و فیلتر نزن
        if (existingRows.length > 0) {
            console.log('Table has existing data, skipping initial filter');
            // فقط یک pagination ساده بساز
            const paginationInfo = {
                current_page: 1,
                total_pages: 1,
                count: existingRows.length,
                has_next: false,
                has_previous: false
            };
            this.updatePagination(paginationInfo);
            this.connectEventListeners();
            return;
        }
        
        // اگر جدول خالی است، داده‌ها را از سرور بارگذاری کن
        console.log('Table is empty, loading initial data from server');
        await this.applyFilters();
    }
    
    showLoading() {
        // نمایش loading indicator در جدول
        const tbody = this.table.querySelector('tbody');
        if (tbody) {
            const colCount = this.table.querySelectorAll('thead th').length;
            tbody.innerHTML = `
                <tr>
                    <td colspan="${colCount}" class="text-center py-5">
                        <div class="d-flex justify-content-center align-items-center">
                            <div class="spinner-border text-primary me-3" role="status">
                                <span class="visually-hidden">در حال بارگذاری...</span>
                            </div>
                            <span class="text-muted">در حال جستجو و بارگذاری نتایج...</span>
                        </div>
                    </td>
                </tr>
            `;
        }
        
        // نمایش loading در input جستجو
        const searchInput = document.getElementById('globalBarnamehSearch');
        if (searchInput) {
            searchInput.style.backgroundImage = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'20\' height=\'20\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2338a169\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E%3Cpath d=\'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z\'/%3E%3C/svg%3E")';
            searchInput.style.backgroundRepeat = 'no-repeat';
            searchInput.style.backgroundPosition = 'right 10px center';
            searchInput.style.backgroundSize = '20px';
        }
    }
    
    hideLoading() {
        // مخفی کردن loading indicator
        const loadingElement = document.getElementById('barnamehTableLoading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // حذف loading از input جستجو
        const searchInput = document.getElementById('globalBarnamehSearch');
        if (searchInput) {
            searchInput.style.backgroundImage = 'none';
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
            'transport_date': 'تاریخ حمل',
            'purchase_number': 'شماره خرید',
            'shenase_takhsis_code': 'شناسه تخصیص',
            'cargo': 'کوتاژ',
            'company_price': 'فی خرید',
            'customer_price': 'فی فروش',
            'total_sales_amount': 'مبلغ کل فروش',
            'buyer_name': 'نام خریدار',
            'buyer_national_code': 'شماره ملی خریدار',
            'buyer_postal_code': 'کدپستی خریدار',
            'buyer_address': 'آدرس خریدار',
            'demand_amount': 'میزان تقاضا',
            'importer': 'واردکننده',
            'product_type': 'محصول',
            'successful_send_date': 'تاریخ ارسال موفق',
            'is_sent_to_bki': 'ارسال به بازارگاه',
            'factor_sodoor_season': 'زمان صدور فاکتور فصل',
            'is_factored': 'فاکتور صادر شده',
            'is_created_by_excel': 'ایجاد توسط اکسل',
            'factor_date': 'تاریخ ثبت فاکتور در سامانه مؤدیان',
            'created_at': 'تاریخ ایجاد'
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