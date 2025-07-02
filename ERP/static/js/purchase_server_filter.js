/**
 * کلاس مدیریت فیلتر سمت سرور برای جداول خریدها
 */
class PurchaseServerFilter {
    constructor(tableSelector) {
        this.tableElement = document.querySelector(tableSelector);
        if (!this.tableElement) {
            console.error('Table not found:', tableSelector);
            return;
        }
        
        this.tableSelector = tableSelector;
        this.tableId = this.tableElement.id;
        this.filterUrl = this.tableElement.dataset.filterUrl;
        this.columnValuesUrl = this.tableElement.dataset.columnValuesUrl;
        
        // تشخیص section از table ID
        if (this.tableId.includes('active')) {
            this.section = 'active';
        } else if (this.tableId.includes('pending')) {
            this.section = 'pending';
        } else if (this.tableId.includes('archived')) {
            this.section = 'archived';
        } else {
            this.section = 'active';
        }
        
        console.log(`🔧 راه‌اندازی فیلتر برای جدول: ${this.tableId}, section: ${this.section}`);
        
        // State جداگانه برای هر جدول
        this.currentFilters = {};
        this.currentSort = {};
        this.currentPage = 1;
        this.perPage = 50;
        this.isLoading = false;
        
        // Cache برای مقادیر ستون‌ها
        this.columnValuesCache = {};
        
        this.init();
    }
    
    init() {
        if (!this.filterUrl || !this.columnValuesUrl) {
            console.error('Filter URLs not found in table dataset');
            return;
        }
        
        this.setupFilterButtons();
        this.loadInitialData();
    }
    
    setupFilterButtons() {
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const columnType = header.dataset.columnType || 'text';
            
            // ایجاد container برای دکمه‌ها
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'filter-buttons-container';
            buttonContainer.style.cssText = 'display: inline-flex; gap: 5px; margin-right: 8px; align-items: center;';
            
            // دکمه فیلتر
            const filterBtn = document.createElement('button');
            filterBtn.type = 'button';
            filterBtn.className = 'filter-btn btn btn-sm';
            filterBtn.innerHTML = '<i class="fas fa-filter"></i>';
            filterBtn.title = 'فیلتر';
            filterBtn.style.cssText = 'padding: 2px 6px; border: 1px solid #ddd; background: white; cursor: pointer;';
            
            filterBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.showFilterModal(columnId, columnType, header);
            });
            
            // دکمه مرتب‌سازی صعودی
            const sortAscBtn = document.createElement('button');
            sortAscBtn.type = 'button';
            sortAscBtn.className = 'sort-btn btn btn-sm';
            sortAscBtn.innerHTML = '<i class="fas fa-sort-up"></i>';
            sortAscBtn.title = 'مرتب‌سازی صعودی';
            sortAscBtn.style.cssText = 'padding: 2px 6px; border: 1px solid #ddd; background: white; cursor: pointer;';
            
            sortAscBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleSort(columnId, 'asc');
            });
            
            // دکمه مرتب‌سازی نزولی
            const sortDescBtn = document.createElement('button');
            sortDescBtn.type = 'button';
            sortDescBtn.className = 'sort-btn btn btn-sm';
            sortDescBtn.innerHTML = '<i class="fas fa-sort-down"></i>';
            sortDescBtn.title = 'مرتب‌سازی نزولی';
            sortDescBtn.style.cssText = 'padding: 2px 6px; border: 1px solid #ddd; background: white; cursor: pointer;';
            
            sortDescBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleSort(columnId, 'desc');
            });
            
            buttonContainer.appendChild(filterBtn);
            buttonContainer.appendChild(sortAscBtn);
            buttonContainer.appendChild(sortDescBtn);
            
            header.appendChild(buttonContainer);
        });
    }
    
    async showFilterModal(columnId, columnType, headerElement) {
        console.log(`📂 نمایش فیلتر برای ستون: ${columnId}`);
        
        try {
            // دریافت مقادیر موجود در جدول فعلی
            const currentValues = await this.getCurrentTableValues(columnId);
            console.log(`📊 مقادیر موجود در جدول: ${currentValues.length}`);
            
            // دریافت همه مقادیر ممکن از سرور
            const allValues = await this.getColumnValues(columnId);
            console.log(`🌐 همه مقادیر از سرور: ${allValues.length}`);
            
            // ایجاد مودال
            this.createFilterModal(columnId, columnType, currentValues, allValues, headerElement);
            
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
        if (this.columnValuesCache[columnId]) {
            return this.columnValuesCache[columnId];
        }
        
        try {
            const formData = new FormData();
            formData.append('column_id', columnId);
            formData.append('section', this.section);
            
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
                this.columnValuesCache[columnId] = data.values;
                return data.values;
            } else {
                throw new Error(data.message || 'خطا در دریافت مقادیر');
            }
            
        } catch (error) {
            console.error('خطا در دریافت مقادیر ستون:', error);
            return [];
        }
    }
    
    createFilterModal(columnId, columnType, currentValues, allValues, headerElement) {
        // حذف مودال قبلی اگر وجود دارد
        const existingModal = document.getElementById('filterModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // ایجاد مودال
        const modal = document.createElement('div');
        modal.id = 'filterModal';
        modal.className = 'filter-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;
        
        const modalContent = document.createElement('div');
        modalContent.className = 'filter-modal-content';
        modalContent.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 20px;
            width: 400px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        `;
        
        // header مودال
        const header = document.createElement('div');
        header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px;';
        
        const title = document.createElement('h5');
        title.textContent = `فیلتر ${headerElement.textContent.replace(/[🔽🔼]/g, '').trim()}`;
        title.style.margin = '0';
        
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.style.cssText = 'background: none; border: none; font-size: 24px; cursor: pointer; padding: 0; width: 30px; height: 30px;';
        closeBtn.onclick = () => modal.remove();
        
        header.appendChild(title);
        header.appendChild(closeBtn);
        
        // نوع فیلتر
        const filterTypeContainer = document.createElement('div');
        filterTypeContainer.style.cssText = 'margin-bottom: 15px;';
        
        const includeRadio = document.createElement('input');
        includeRadio.type = 'radio';
        includeRadio.name = 'filterType';
        includeRadio.value = 'include';
        includeRadio.id = 'includeFilter';
        includeRadio.checked = true;
        
        const includeLabel = document.createElement('label');
        includeLabel.htmlFor = 'includeFilter';
        includeLabel.textContent = ' نمایش موارد انتخاب شده';
        includeLabel.style.marginLeft = '15px';
        
        const excludeRadio = document.createElement('input');
        excludeRadio.type = 'radio';
        excludeRadio.name = 'filterType';
        excludeRadio.value = 'exclude';
        excludeRadio.id = 'excludeFilter';
        
        const excludeLabel = document.createElement('label');
        excludeLabel.htmlFor = 'excludeFilter';
        excludeLabel.textContent = ' مخفی کردن موارد انتخاب شده';
        
        filterTypeContainer.appendChild(includeRadio);
        filterTypeContainer.appendChild(includeLabel);
        filterTypeContainer.appendChild(excludeRadio);
        filterTypeContainer.appendChild(excludeLabel);
        
        // جستجو
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'جستجو...';
        searchInput.className = 'form-control';
        searchInput.style.cssText = 'margin-bottom: 15px; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;';
        
        // لیست مقادیر
        const valuesList = document.createElement('div');
        valuesList.style.cssText = 'max-height: 300px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; padding: 10px;';
        
        // ایجاد چک‌باکس‌ها - ابتدا مقادیر موجود در جدول فعلی، سپس سایر مقادیر
        const displayValues = [...new Set([...currentValues, ...allValues])];
        
        // کنترل انتخاب همه
        const selectAllContainer = document.createElement('div');
        selectAllContainer.style.cssText = 'margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee;';
        
        const selectAllCheckbox = document.createElement('input');
        selectAllCheckbox.type = 'checkbox';
        selectAllCheckbox.id = 'selectAll';
        selectAllCheckbox.checked = true; // همه مقادیر موجود در جدول پیش‌فرض انتخاب شده باشند
        
        const selectAllLabel = document.createElement('label');
        selectAllLabel.htmlFor = 'selectAll';
        selectAllLabel.textContent = ' انتخاب همه';
        selectAllLabel.style.fontWeight = 'bold';
        
        selectAllContainer.appendChild(selectAllCheckbox);
        selectAllContainer.appendChild(selectAllLabel);
        
        valuesList.appendChild(selectAllContainer);
        
        // ایجاد چک‌باکس‌ها
        displayValues.forEach((value, index) => {
            const container = document.createElement('div');
            container.style.cssText = 'margin-bottom: 5px; display: flex; align-items: center;';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = value;
            checkbox.id = `filter_${columnId}_${index}`;
            
            // مقادیر موجود در جدول فعلی پیش‌فرض انتخاب شده باشند
            checkbox.checked = currentValues.includes(value);
            
            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = ` ${value}`;
            label.style.cssText = 'cursor: pointer; margin-right: 8px; flex: 1;';
            
            // اگر مقدار در جدول فعلی وجود دارد، با رنگ متفاوت نمایش داده شود
            if (currentValues.includes(value)) {
                label.style.fontWeight = 'bold';
                label.style.color = '#007bff';
            }
            
            container.appendChild(checkbox);
            container.appendChild(label);
            valuesList.appendChild(container);
        });
        
        // عملکرد انتخاب همه
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = valuesList.querySelectorAll('input[type="checkbox"]:not(#selectAll)');
            checkboxes.forEach(cb => cb.checked = this.checked);
        });
        
        // جستجو
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const containers = valuesList.querySelectorAll('div:not(:first-child)');
            
            containers.forEach(container => {
                const label = container.querySelector('label');
                const text = label.textContent.toLowerCase();
                container.style.display = text.includes(searchTerm) ? 'flex' : 'none';
            });
        });
        
        // دکمه‌های عملیات
        const buttonsContainer = document.createElement('div');
        buttonsContainer.style.cssText = 'margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;';
        
        const applyBtn = document.createElement('button');
        applyBtn.textContent = 'اعمال فیلتر';
        applyBtn.className = 'btn btn-primary';
        applyBtn.style.cssText = 'padding: 8px 16px;';
        
        const clearBtn = document.createElement('button');
        clearBtn.textContent = 'پاک کردن';
        clearBtn.className = 'btn btn-secondary';
        clearBtn.style.cssText = 'padding: 8px 16px;';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'انصراف';
        cancelBtn.className = 'btn btn-light';
        cancelBtn.style.cssText = 'padding: 8px 16px;';
        
        // عملکرد دکمه‌ها
        applyBtn.addEventListener('click', () => {
            const selectedValues = Array.from(valuesList.querySelectorAll('input[type="checkbox"]:not(#selectAll):checked'))
                .map(cb => cb.value);
            
            const filterType = modal.querySelector('input[name="filterType"]:checked').value;
            
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
        
        buttonsContainer.appendChild(cancelBtn);
        buttonsContainer.appendChild(clearBtn);
        buttonsContainer.appendChild(applyBtn);
        
        // ترکیب کردن همه قسمت‌ها
        modalContent.appendChild(header);
        modalContent.appendChild(filterTypeContainer);
        modalContent.appendChild(searchInput);
        modalContent.appendChild(valuesList);
        modalContent.appendChild(buttonsContainer);
        
        modal.appendChild(modalContent);
        
        // اضافه کردن به صفحه
        document.body.appendChild(modal);
        
        // focus روی جستجو
        searchInput.focus();
        
        // بستن با کلیک خارج از مودال
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
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
            console.log(`🔍 اعمال فیلتر برای جدول ${this.tableId}:`, this.currentFilters);
            
            const formData = new FormData();
            formData.append('filters', JSON.stringify(this.currentFilters));
            formData.append('sort', JSON.stringify(this.currentSort));
            formData.append('page', this.currentPage);
            formData.append('per_page', this.perPage);
            formData.append('section', this.section);
            
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
                console.log(`✅ دریافت ${data.data.length} رکورد برای ${this.tableId}`);
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
        if (!tbody) return;
        
        // پاک کردن محتوای قبلی
        tbody.innerHTML = '';
        
        if (data.length === 0) {
            const noDataRow = document.createElement('tr');
            noDataRow.className = 'no-data-row';
            noDataRow.innerHTML = `<td colspan="100%" class="text-center py-4">هیچ رکوردی یافت نشد</td>`;
            tbody.appendChild(noDataRow);
            return;
        }
        
        // اضافه کردن رکوردهای جدید
        data.forEach(purchase => {
            const row = this.createTableRow(purchase);
            tbody.appendChild(row);
        });
        
        // بروزرسانی pagination اگر وجود دارد
        this.updatePagination(pagination);
        
        // بروزرسانی شمارنده
        this.updateRowCounter(pagination);
    }
    
    createTableRow(purchase) {
        const row = document.createElement('tr');
        
        // تشخیص ستون‌های مورد نیاز بر اساس جدول
        const headers = this.tableElement.querySelectorAll('th[data-column-id]');
        
        // checkbox
        const checkboxCell = document.createElement('td');
        checkboxCell.innerHTML = `<input type="checkbox" class="row-checkbox" value="${purchase.id}">`;
        row.appendChild(checkboxCell);
        
        // سایر ستون‌ها
        headers.forEach(header => {
            const columnId = header.dataset.columnId;
            const cell = document.createElement('td');
            
            let cellValue = purchase[columnId] || '-';
            
            // فرمت‌بندی خاص برای انواع مختلف
            if (columnId === 'status') {
                cell.innerHTML = `<span class="badge badge-info">${cellValue}</span>`;
            } else if (['is_factored', 'is_urgent', 'is_canceled', 'is_archived'].includes(columnId)) {
                const icon = cellValue === 'بله' ? '✓' : '✗';
                const colorClass = cellValue === 'بله' ? 'text-success' : 'text-danger';
                cell.innerHTML = `<span class="${colorClass}">${icon}</span>`;
            } else if (['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid'].includes(columnId)) {
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
                    filterBtn.style.background = '#007bff';
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
                    targetBtn.style.background = '#28a745';
                    targetBtn.style.color = 'white';
                }
            }
        });
    }
    
    updatePagination(pagination) {
        // این متد pagination را بروزرسانی می‌کند
        // فعلاً اختیاری است
    }
    
    updateRowCounter(pagination) {
        // بروزرسانی شمارنده رکوردها
        const counter = document.querySelector(`#${this.tableId} + .row-counter, .${this.tableId}-counter`);
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
        // ایجاد Toast notification ساده
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            z-index: 10001;
            font-size: 14px;
            min-width: 200px;
            text-align: center;
        `;
        
        switch(type) {
            case 'success':
                toast.style.backgroundColor = '#28a745';
                break;
            case 'error':
                toast.style.backgroundColor = '#dc3545';
                break;
            default:
                toast.style.backgroundColor = '#17a2b8';
        }
        
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
}

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 راه‌اندازی فیلترهای خرید...');
    
    // راه‌اندازی فیلتر برای هر جدول به صورت جداگانه
    const tables = [
        '#activePurchasesTable',
        '#pendingPurchasesTable', 
        '#archivedPurchasesTable'
    ];
    
    tables.forEach(tableSelector => {
        const tableElement = document.querySelector(tableSelector);
        if (tableElement && tableElement.classList.contains('python-excel-filter')) {
            console.log(`📊 راه‌اندازی فیلتر برای: ${tableSelector}`);
            new PurchaseServerFilter(tableSelector);
        }
    });
}); 