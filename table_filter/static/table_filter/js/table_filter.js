/**
 * Generic Table Filter System
 * Provides sorting, filtering, and searching capabilities for any table
 */

class TableFilter {
    constructor(config = {}) {
        this.config = {
            tableSelector: config.tableSelector || 'table',
            enableToast: config.enableToast === true,
            enableIndicators: config.enableIndicators !== false,
            enableSummary: config.enableSummary !== false,
            enableClearAll: config.enableClearAll !== false,
            columnConfig: config.columnConfig || {},
            autoDetectColumns: config.autoDetectColumns !== false,
            filterButtonClass: config.filterButtonClass || 'filter-dropdown-btn',
            autoInit: config.autoInit !== false,
            ...config
        };
        
        this.activeFilters = {};
        this.originalRows = {};
        this.columnMappings = {};
        this.sortState = {};
        this.tableIds = [];
        
        if (this.config.autoInit) {
            this.init();
        }
    }

    init() {
        this.detectTables();
        this.setupColumnMappings();
        this.storeOriginalRows();
        this.attachEventListeners();
        
        if (this.config.enableClearAll) {
            this.createClearAllButton();
        }
        
        if (this.config.enableSummary) {
            this.createActiveFiltersSummary();
        }
        
        // اضافه کردن قابلیت تنظیم ستون‌ها
        this.setupColumnVisibilityControl();
    }

    detectTables() {
        const tables = document.querySelectorAll(this.config.tableSelector);
        tables.forEach((table, index) => {
            if (!table.id) {
                table.id = `auto-table-${Date.now()}-${index}`;
            }
            if (!this.tableIds.includes(table.id)) {
                this.tableIds.push(table.id);
            }
        });
    }

    setupColumnMappings() {
        this.tableIds.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const headers = table.querySelectorAll('thead th, thead td');
            this.columnMappings[tableId] = {};
            
            headers.forEach((header, index) => {
                // Extraer column-id desde la clase para asegurar vínculo consistente
                let columnClass = Array.from(header.classList).find(cls => cls.startsWith('column-'));
                let columnId;
                
                if (columnClass) {
                    // Extraer ID de columna desde la clase (column-purchase_number -> purchase_number)
                    columnId = columnClass.replace('column-', '');
                } else {
                    // Respaldo: usar el índice o texto si no hay clase column-X
                    columnId = this.getColumnId(header, index, tableId);
                }
                
                let columnName = this.getColumnName(header);
                let columnType = header.getAttribute('data-column-type') || this.detectColumnType(header, tableId, index);
                
                this.columnMappings[tableId][columnId] = {
                    name: columnName,
                    type: columnType,
                    index: index,
                    tableId: tableId,
                    element: header // Almacenar referencia al elemento para uso futuro
                };
                
                // Añadir botón de filtro
                this.addFilterButton(header, columnId, tableId);
            });
        });
    }

    getColumnId(header, index, tableId) {
        // Primero verificar si hay una clase column-X
        let columnClass = Array.from(header.classList).find(cls => cls.startsWith('column-'));
        if (columnClass) {
            return columnClass.replace('column-', '');
        }
        
        // Verificar atributo data-column-id
        if (header.hasAttribute('data-column-id')) {
            return header.getAttribute('data-column-id');
        }
        
        // Verificar configuración específica
        if (this.config.columnConfig && this.config.columnConfig[tableId] && this.config.columnConfig[tableId][index]) {
            return this.config.columnConfig[tableId][index].id;
        }
        
        // Respaldo: generar ID basado en texto del encabezado
        const headerText = header.innerText.trim();
        if (headerText) {
            // Normalizar texto como ID: quitar espacios, convertir a minúscula
            return headerText
                .toLowerCase()
                .replace(/\s+/g, '_')
                .replace(/[^\w\s]/gi, '');
        }
        
        // Último recurso: usar el índice
        return `column_${index}`;
    }

    getColumnName(header) {
        return header.dataset.columnName || header.textContent.trim() || 'ستون';
    }

    detectColumnType(header, tableId, columnIndex) {
        // بررسی تنظیمات سفارشی
        const columnId = this.getColumnId(header, columnIndex, tableId);
        if (this.config.columnConfig[columnId]) {
            return this.config.columnConfig[columnId].type;
        }
        
        // بررسی data attribute
        if (header.dataset.columnType) {
            return header.dataset.columnType;
        }
        
        // تشخیص خودکار بر اساس نمونه داده‌ها
        const table = document.getElementById(tableId);
        const sampleValues = this.getSampleColumnValues(table, columnIndex, 5);
        
        return this.autoDetectTypeFromSamples(sampleValues, header);
    }

    getSampleColumnValues(table, columnIndex, sampleCount = 5) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return [];
        
        const rows = tbody.querySelectorAll('tr');
        const values = [];
        
        for (let i = 0; i < Math.min(rows.length, sampleCount); i++) {
            const cell = rows[i].children[columnIndex];
            if (cell) {
                const value = this.extractRawCellValue(cell).trim();
                if (value && value !== '' && value !== '-' && value !== 'تعیین نشده') {
                    values.push(value);
                }
            }
        }
        
        return values;
    }

    autoDetectTypeFromSamples(values, header) {
        if (values.length === 0) return 'text';
        
        const headerText = header.textContent.trim().toLowerCase();
        
        // بررسی نام ستون
        if (headerText.includes('تاریخ') || headerText.includes('date') || headerText.includes('زمان')) {
            return 'date';
        }
        
        if (headerText.includes('قیمت') || headerText.includes('مبلغ') || headerText.includes('price') || 
            headerText.includes('amount') || headerText.includes('وزن') || headerText.includes('تعداد')) {
            return 'number';
        }
        
        if (headerText.includes('وضعیت') || headerText.includes('status') || headerText.includes('حالت')) {
            return 'status';
        }
        
        // بررسی محتوای نمونه
        let numberCount = 0;
        let dateCount = 0;
        let statusCount = 0;
        let booleanCount = 0;
        
        values.forEach(value => {
            // بررسی عدد
            if (/^[\d\s,.-]+$/.test(value.replace(/[,\s]/g, '')) && !isNaN(parseFloat(value.replace(/[,\s]/g, '')))) {
                numberCount++;
            }
            
            // بررسی تاریخ (قالب‌های مختلف)
            if (/^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(value) || 
                /^\d{1,2}[-/]\d{1,2}[-/]\d{4}/.test(value) ||
                /^\d{4}\/\d{1,2}\/\d{1,2}/.test(value)) {
                dateCount++;
            }
            
            // بررسی وضعیت
            if (value.includes('فعال') || value.includes('غیرفعال') || value.includes('تأیید') || 
                value.includes('رد') || value.includes('pending') || value.includes('active') ||
                value.includes('confirmed') || value.includes('rejected')) {
                statusCount++;
            }
            
            // بررسی بولین
            if (['بله', 'خیر', 'true', 'false', 'yes', 'no', 'فعال', 'غیرفعال'].includes(value.toLowerCase())) {
                booleanCount++;
            }
        });
        
        const total = values.length;
        
        // تصمیم‌گیری بر اساس درصد
        if (dateCount / total > 0.5) return 'date';
        if (numberCount / total > 0.5) return 'number';
        if (statusCount / total > 0.3) return 'status';
        if (booleanCount / total > 0.5) return 'boolean';
        
        return 'text';
    }

    extractRawCellValue(cell) {
        // حذف تگ‌های HTML و برگرداندن متن خالص
        return cell.textContent || cell.innerText || '';
    }

    addFilterButton(header, columnId, tableId) {
        // اگر قبلاً دکمه اضافه شده، دوباره اضافه نکن - بررسی دقیق‌تر
        if (header.querySelector(`.${this.config.filterButtonClass}`) || header.querySelector('.filter-btn')) {
            return;
        }

        const button = document.createElement('button');
        button.className = this.config.filterButtonClass;
        button.type = 'button'; // اضافه کردن type=button برای جلوگیری از ریفرش صفحه
        button.setAttribute('data-column-id', columnId);
        button.innerHTML = '<i class="fas fa-filter"></i>';
        button.title = 'فیلتر';

        header.appendChild(button);

        // اضافه کردن event listener به دکمه
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            const columnId = e.currentTarget.getAttribute('data-column-id');
            this.toggleDropdown(columnId, tableId, header, e.currentTarget);
            
            // جلوگیری از propagation به بالا
            return false;
        });
    }

    storeOriginalRows() {
        this.tableIds.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (table) {
                const tbody = table.querySelector('tbody');
                this.originalRows[tableId] = tbody ? Array.from(tbody.querySelectorAll('tr')) : [];
            }
        });
    }

    attachEventListeners() {
        // بستن dropdown ها با کلیک در هر جای صفحه
        document.addEventListener('click', (e) => {
            // اگر کلیک روی دکمه فیلتر یا خود درپ‌داون انجام شده، اقدامی انجام نده
            if (e.target.closest('.filter-btn') || e.target.closest('.filter-dropdown')) {
                return;
            }
            
            this.closeAllDropdowns();
        });
        
        // جلوگیری از ارسال فرم با فشردن Enter در input های داخل dropdown
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.closest('.filter-dropdown')) {
                e.preventDefault();
                return false;
            }
        });
        
        // کلیک روی هر کجای فیلتر dropdown، event را متوقف کن
        document.addEventListener('click', (e) => {
            if (e.target.closest('.filter-dropdown')) {
                e.stopPropagation();
            }
        });
    }

    toggleDropdown(columnId, tableId, headerElement, buttonElement) {
        // بستن سایر dropdown ها
        this.closeAllDropdowns();
        
        // ایجاد پس‌زمینه overlay
        const overlay = document.createElement('div');
        overlay.className = 'filter-overlay';
        document.body.appendChild(overlay);
        
        setTimeout(() => {
            overlay.classList.add('show');
        }, 10);
        
        // ایجاد dropdown
        const dropdown = this.createModalFilterDropdown(columnId, tableId, headerElement);
        if (!dropdown) return;
        
        // موقعیت‌دهی dropdown به نزدیک ستون
        this.positionDropdownNearColumn(dropdown, headerElement, buttonElement);
        
        // بروزرسانی دکمه
        if (buttonElement) {
            buttonElement.classList.add('active');
        }
        
        // جلوگیری از بستن dropdown با کلیک روی button
        buttonElement.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }, { once: true });
        
        // بستن با کلیک روی overlay
        overlay.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.closeAllDropdowns();
            return false;
        });
        
        dropdown.classList.add('show');
        
        // اضافه کردن event listener به dropdown برای جلوگیری از propagation
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        // استفاده از یک تایمر کوتاه برای مطمئن شدن از باز ماندن dropdown
        setTimeout(() => {
            if (dropdown && !dropdown.classList.contains('show')) {
                dropdown.classList.add('show');
            }
        }, 50);
    }

    // تابع برای موقعیت دادن به dropdown نزدیک ستون
    positionDropdownNearColumn(dropdown, headerElement, buttonElement) {
        // محاسبه موقعیت برای نمایش نزدیک به ستون
        const headerRect = headerElement.getBoundingClientRect();
        const buttonRect = buttonElement ? buttonElement.getBoundingClientRect() : headerRect;
        
        // تنظیم موقعیت بر اساس مکان دکمه یا ستون - نزدیک‌تر به دکمه
        const left = Math.max(10, buttonRect.left - 150); // پنجره بیشتر به سمت راست و در کنار دکمه
        const top = buttonRect.top + window.scrollY; // دقیقاً در ارتفاع دکمه
        
        // تنظیم موقعیت dropdown
        dropdown.style.position = 'absolute';
        dropdown.style.top = `${top}px`;
        dropdown.style.left = `${left}px`;
        dropdown.style.transform = 'none'; // حذف transform پیش‌فرض
        dropdown.style.maxHeight = '80vh'; // محدود کردن ارتفاع به 80% ارتفاع صفحه
        dropdown.style.overflow = 'auto'; // اضافه کردن اسکرول در صورت نیاز
    }

    createModalFilterDropdown(columnId, tableId, headerElement) {
        // ایجاد dropdown element
        const dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        dropdown.setAttribute('data-column-id', columnId);
        dropdown.setAttribute('data-table-id', tableId);
        
        // جلوگیری از ریفرش صفحه با متوقف کردن رویدادها
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        // ایجاد عنوان modal
        const modalTitle = document.createElement('div');
        modalTitle.className = 'filter-modal-title';
        
        const columnData = this.columnMappings[tableId][columnId];
        modalTitle.innerHTML = `
            <span>${this.getColumnName(headerElement)}</span>
            <button class="close-btn" type="button"><i class="fas fa-times"></i></button>
        `;
        
        // اضافه کردن دکمه بستن
        const closeBtn = modalTitle.querySelector('.close-btn');
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.closeAllDropdowns();
            return false;
        });
        
        dropdown.appendChild(modalTitle);
        
        // ایجاد محتوای dropdown
        const dropdownContent = document.createElement('div');
        dropdownContent.className = 'filter-dropdown-content';
        dropdown.appendChild(dropdownContent);
        
        // اضافه کردن HTML مناسب بر اساس نوع ستون
        const html = this.getDropdownHTML(columnId, tableId, columnData);
        dropdownContent.innerHTML = html;
        
        // ثبت event listeners
        this.attachDropdownEvents(dropdown, columnId, tableId);
        
        // اضافه کردن به DOM
        document.body.appendChild(dropdown);
        
        return dropdown;
    }

    getDropdownHTML(columnId, tableId, columnData) {
        let html = '';
        
        // بخش مرتب‌سازی
        html += `
        <div class="filter-section">
            <div class="filter-section-title">
                <i class="fas fa-sort-amount-down"></i>
                مرتب‌سازی
            </div>
            <div class="sort-option" data-direction="asc">
                <i class="fas fa-sort-alpha-down"></i>
                <span>صعودی</span>
            </div>
            <div class="sort-option" data-direction="desc">
                <i class="fas fa-sort-alpha-down-alt"></i>
                <span>نزولی</span>
            </div>
        </div>`;
        
        // بخش فیلتر
        html += `
        <div class="filter-section">
            <div class="filter-section-title">
                <i class="fas fa-filter"></i>
                فیلتر
            </div>
            <input type="text" class="filter-search" placeholder="جستجو...">
            <div class="select-all-filters">
                <input type="checkbox" id="select-all-${columnId}" checked>
                <label for="select-all-${columnId}">انتخاب همه</label>
            </div>
            <div class="filter-values-container">
                <div class="filter-loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    در حال بارگذاری...
                </div>
            </div>
        </div>`;
        
        // دکمه‌های اکشن
        html += `
        <div class="filter-actions">
            <button type="button" class="filter-action-btn btn-outline-secondary" data-action="clear">
                <span>پاک کردن</span>
            </button>
            <button type="button" class="filter-action-btn btn-primary" data-action="apply">
                <span>اعمال فیلتر</span>
            </button>
        </div>`;
        
        return html;
    }

    attachDropdownEvents(dropdown, columnId, tableId) {
        // ابتدا گزینه‌های مرتب سازی
        const sortOptions = dropdown.querySelectorAll('.sort-option');
        sortOptions.forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const direction = option.getAttribute('data-direction');
                this.applySorting(columnId, tableId, direction);
                this.updateSortVisuals(dropdown, option);
                
                return false;
            });
        });
        
        // سپس بارگذاری مقادیر
        this.loadColumnValues(columnId, tableId, dropdown);
        
        // انتخاب همه
        const selectAllBtn = dropdown.querySelector('.select-all-filters');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleSelectAll(dropdown);
                return false;
            });
        }
        
        // جستجو در مقادیر
        const searchInput = dropdown.querySelector('.filter-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                e.stopPropagation();
                this.filterValues(dropdown, e.target.value);
            });
            
            // جلوگیری از submit شدن فرم در صورت فشردن Enter
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    return false;
                }
            });
        }
        
        // دکمه‌های اکشن
        const actionBtns = dropdown.querySelectorAll('.filter-action-btn');
        actionBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const action = btn.getAttribute('data-action');
                if (action === 'apply') {
                    this.applyColumnFilter(columnId, tableId, dropdown);
                } else if (action === 'clear') {
                    this.clearColumnFilter(columnId, tableId, dropdown);
                }
                
                return false;
            });
        });
    }

    loadColumnValues(columnId, tableId, dropdown) {
        try {
            const values = this.getUniqueColumnValues(columnId, tableId);
            this.renderFilterValues(dropdown, values, columnId, tableId);
        } catch (error) {
            console.error('Error loading column values:', error);
            const container = dropdown.querySelector('.filter-values-container');
            if (container) {
                container.innerHTML = '<div class="no-filter-values">خطا در بارگذاری مقادیر</div>';
            }
        }
    }

    getUniqueColumnValues(columnId, tableId) {
        const table = document.getElementById(tableId);
        if (!table) return [];
        
        const values = new Set();
        
        // همیشه از originalRows استفاده کن تا همه مقادیر نمایش داده شوند
        // حتی اگر در حال حاضر با فیلتر مخفی شده باشند
        const rowsToCheck = this.originalRows[tableId] || table.querySelectorAll('tbody tr');
        
        rowsToCheck.forEach(row => {
            // فقط ردیف‌های خالی یا colspan دار را رد کن
            // ردیف‌های مخفی شده با فیلتر را رد نکن
            if (row.querySelector('td[colspan]')) {
                return;
            }
            
            // استفاده از کلاس column-X به جای ایندکس
            const cell = row.querySelector(`.column-${columnId}`);
            if (!cell) return;

            let value = this.extractCellValue(cell, columnId);
            
            // پردازش بیشتر برای مقادیر خاص
            if (value && value.trim() !== '') {
                // تقسیم مقادیر جداشده با کاما
                if (value.includes(',')) {
                    value.split(',').forEach(v => {
                        const trimmedValue = v.trim();
                        if (trimmedValue) {
                            values.add(trimmedValue);
                        }
                    });
                } else {
                    values.add(value.trim());
                }
            }
        });
        
        // تبدیل Set به Array و مرتب‌سازی
        const sortedValues = Array.from(values).sort((a, b) => {
            // مرتب‌سازی بر اساس نوع ستون
            const columnType = this.getColumnTypeFromId(columnId);
            
            if (columnType === 'number' || columnId.includes('weight') || columnId.includes('price') || columnId.includes('amount')) {
                // برای اعداد، تبدیل به عدد و مقایسه
                const numA = parseFloat(a.replace(/[^\d\.,\-]/g, '').replace(',', '')) || 0;
                const numB = parseFloat(b.replace(/[^\d\.,\-]/g, '').replace(',', '')) || 0;
                return numA - numB;
            } else if (columnType === 'boolean') {
                // برای boolean، بله قبل خیر
                if (a === 'بله' && b === 'خیر') return -1;
                if (a === 'خیر' && b === 'بله') return 1;
                return 0;
            } else {
                // برای متن، مرتب‌سازی الفبایی
                return a.localeCompare(b, 'fa', { numeric: true });
            }
        });
        
        console.log(`Unique values for column ${columnId}:`, sortedValues);
        return sortedValues;
    }

    extractCellValue(cell, columnId) {
        let value = '';
        
        try {
            // برای ستون‌های boolean مانند علاقه‌مندی
            if (this.getColumnTypeFromId(columnId) === 'boolean') {
                // چک کردن آیکون ستاره برای علاقه‌مندی
                const favoriteIcon = cell.querySelector('.favorite-icon');
                if (favoriteIcon) {
                    const isFavorite = favoriteIcon.getAttribute('data-is-favorite');
                    return isFavorite === 'true' ? 'بله' : 'خیر';
                }
                
                // چک کردن چک‌باکس‌ها
                const checkbox = cell.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    return checkbox.checked ? 'بله' : 'خیر';
                }
                
                // بررسی آیکون‌های مختلف برای boolean
                const starIcon = cell.querySelector('.fas.fa-star');
                if (starIcon) {
                    return 'بله';
                }
                const emptyStarIcon = cell.querySelector('.far.fa-star');
                if (emptyStarIcon) {
                    return 'خیر';
                }
            }
            
            // اگر سلول دارای data-value است، از آن استفاده کن
            if (cell.hasAttribute('data-value')) {
                value = cell.getAttribute('data-value');
                if (value !== null && value !== '') {
                    return value;
                }
            }
            
            // استخراج متن از span های تگ‌دار
            const tagSpans = cell.querySelectorAll('.tag');
            if (tagSpans.length > 0) {
                value = Array.from(tagSpans).map(span => span.textContent.trim()).join(', ');
                return value;
            }
            
            // استخراج متن از لینک‌ها
            const links = cell.querySelectorAll('a');
            if (links.length > 0) {
                value = Array.from(links).map(link => link.textContent.trim()).join(', ');
                return value;
            }
            
            // استخراج متن از span های رنگی (برای اعداد)
            const colorSpans = cell.querySelectorAll('span[class*="bg-"]');
            if (colorSpans.length > 0) {
                value = Array.from(colorSpans).map(span => span.textContent.trim()).join(', ');
                return value;
            }
            
            // استخراج متن خام از سلول
            value = cell.textContent || cell.innerText || '';
            value = value.trim();
            
            // پاک کردن کاراکترهای اضافی
            value = value.replace(/\s+/g, ' ');
            value = value.replace(/[\n\r\t]/g, ' ');
            
            // اگر این یک ستون عددی است (مخصوصاً ستون‌های وزن)، پردازش ویژه
            if (this.getColumnTypeFromId(columnId) === 'number' || 
                columnId.includes('weight') || 
                columnId.includes('price') || 
                columnId.includes('amount')) {
                
                // حذف کاراکترهای غیرعددی جز اعداد، کاما، نقطه و منها
                let numericValue = value.replace(/[^\d\u06F0-\u06F9\u06F4\u06F5\u06F6،,.\-\+]/g, '');
                
                // تبدیل اعداد فارسی به انگلیسی
                numericValue = numericValue.replace(/[۰-۹]/g, function(w) {
                    const persian = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
                    const english = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
                    return english[persian.indexOf(w)];
                });
                
                // حذف کاماها و تبدیل به عدد
                numericValue = numericValue.replace(/[,،]/g, '');
                
                // اگر مقدار عددی معتبر است، آن را برگردان
                if (numericValue && !isNaN(parseFloat(numericValue))) {
                    return numericValue;
                }
            }
            
            // تبدیل اعداد فارسی به انگلیسی
            value = value.replace(/[۰-۹]/g, function(w) {
                const persian = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
                const english = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
                return english[persian.indexOf(w)];
            });
            
        } catch (error) {
            console.warn('خطا در استخراج مقدار سلول:', error);
            value = cell.textContent || '';
        }
        
        return value.trim();
    }

    getColumnTypeFromId(columnId) {
        // جستجو در همه جداول برای یافتن نوع ستون
        for (const tableId of this.tableIds) {
            if (this.columnMappings[tableId][columnId]) {
                return this.columnMappings[tableId][columnId].type;
            }
        }
        return 'text';
    }

    renderFilterValues(dropdown, values, columnId, tableId) {
        const container = dropdown.querySelector('.filter-values-container');
        
        if (values.length === 0) {
            container.innerHTML = '<div class="no-filter-values">هیچ مقداری یافت نشد</div>';
            return;
        }

        const filterKey = `${tableId}-${columnId}`;
        const currentFilters = this.activeFilters[filterKey]?.values || [];
        
        let html = '';
        values.forEach(value => {
            const isChecked = currentFilters.length === 0 || currentFilters.includes(value);
            html += `
                <div class="filter-value-item">
                    <input type="checkbox" id="filter-${tableId}-${columnId}-${this.sanitizeId(value)}" 
                           ${isChecked ? 'checked' : ''} value="${this.escapeHtml(value)}">
                    <label for="filter-${tableId}-${columnId}-${this.sanitizeId(value)}">${this.escapeHtml(value)}</label>
                </div>
            `;
        });

        container.innerHTML = html;

        container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSelectAllState(dropdown);
            });
        });
        
        this.updateSelectAllState(dropdown);
    }

    sanitizeId(value) {
        return value.toString().replace(/[^a-zA-Z0-9\u0600-\u06FF]/g, '_');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    filterValues(dropdown, searchTerm) {
        const items = dropdown.querySelectorAll('.filter-value-item');
        items.forEach(item => {
            const label = item.querySelector('label').textContent.toLowerCase();
            if (label.includes(searchTerm)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }

    toggleSelectAll(dropdown) {
        const checkboxes = dropdown.querySelectorAll('.filter-values-container input[type="checkbox"]');
        const visibleCheckboxes = Array.from(checkboxes).filter(cb => 
            cb.closest('.filter-value-item').style.display !== 'none'
        );
        
        const allChecked = visibleCheckboxes.every(cb => cb.checked);
        
        visibleCheckboxes.forEach(checkbox => {
            checkbox.checked = !allChecked;
        });

        this.updateSelectAllState(dropdown);
    }

    updateSelectAllState(dropdown) {
        const selectAllText = dropdown.querySelector('.select-all-filters');
        const checkboxes = dropdown.querySelectorAll('.filter-values-container input[type="checkbox"]');
        const visibleCheckboxes = Array.from(checkboxes).filter(cb => 
            cb.closest('.filter-value-item').style.display !== 'none'
        );
        
        const checkedCount = visibleCheckboxes.filter(cb => cb.checked).length;
        const totalVisible = visibleCheckboxes.length;

        if (checkedCount === totalVisible) {
            selectAllText.innerHTML = '✗ لغو انتخاب همه';
        } else {
            selectAllText.innerHTML = '✓ انتخاب همه';
        }
    }

    applySorting(columnId, tableId, direction) {
        const sortKey = `${tableId}-${columnId}`;
        this.sortState[sortKey] = direction;
        
        const columnIndex = this.columnMappings[tableId][columnId]?.index;
        if (columnIndex === -1 || columnIndex === undefined) return;

        this.sortTableByColumn(tableId, columnIndex, direction, columnId);

        if (this.config.enableToast) {
            const columnName = this.columnMappings[tableId][columnId].name;
            this.showToast(`ستون "${columnName}" ${direction === 'asc' ? 'صعودی' : 'نزولی'} مرتب شد`);
        }
    }

    sortTableByColumn(tableId, columnIndex, direction, columnId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            // استفاده از کلاس column-X به جای ایندکس
            const cellA = a.querySelector(`.column-${columnId}`);
            const cellB = b.querySelector(`.column-${columnId}`);
            
            if (!cellA || !cellB) return 0;

            let valueA = this.extractCellValue(cellA, columnId);
            let valueB = this.extractCellValue(cellB, columnId);

            const columnType = this.getColumnTypeFromId(columnId);
            
            if (columnType === 'number' || columnId.includes('weight') || columnId.includes('price') || columnId.includes('amount')) {
                valueA = parseFloat(valueA.replace(/[,\s]/g, '')) || 0;
                valueB = parseFloat(valueB.replace(/[,\s]/g, '')) || 0;
            } else if (columnType === 'date') {
                valueA = new Date(valueA.split('/').reverse().join('-')).getTime() || 0;
                valueB = new Date(valueB.split('/').reverse().join('-')).getTime() || 0;
            }

            if (direction === 'asc') {
                return valueA > valueB ? 1 : -1;
            } else {
                return valueA < valueB ? 1 : -1;
            }
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    updateSortVisuals(dropdown, activeOption) {
        dropdown.querySelectorAll('.sort-option').forEach(option => {
            option.classList.remove('active');
        });
        activeOption.classList.add('active');
    }

    applyColumnFilter(columnId, tableId, dropdown) {
        const selectedValues = [];
        const checkboxes = dropdown.querySelectorAll('.filter-values-container input[type="checkbox"]:checked');
        
        checkboxes.forEach(checkbox => {
            selectedValues.push(checkbox.value);
        });

        const filterKey = `${tableId}-${columnId}`;
        
        if (selectedValues.length > 0) {
            this.activeFilters[filterKey] = {
                values: selectedValues,
                type: 'include',
                columnId: columnId,
                tableId: tableId
            };
        } else {
            delete this.activeFilters[filterKey];
        }

        this.applyAllFilters();
        
        if (this.config.enableIndicators) {
            this.updateFilterIndicators();
        }
        
        if (this.config.enableSummary) {
            this.updateActiveFiltersSummary();
        }
        
        if (this.config.enableClearAll) {
            this.updateClearAllButton();
        }
        
        this.closeAllDropdowns();
        
        // ارسال event برای اطلاع سایر کامپوننت‌ها
        document.dispatchEvent(new CustomEvent('tableFilterApplied', {
            detail: {
                tableId: tableId,
                columnId: columnId,
                selectedValues: selectedValues,
                activeFilters: this.activeFilters
            }
        }));
        
        if (this.config.enableToast) {
            this.showToast('فیلتر اعمال شد');
        }
    }

    clearColumnFilter(columnId, tableId, dropdown) {
        const filterKey = `${tableId}-${columnId}`;
        const sortKey = `${tableId}-${columnId}`;
        
        delete this.activeFilters[filterKey];
        delete this.sortState[sortKey];
        
        // تغییر: بعد از پاک کردن فیلتر، مقادیر را دوباره بارگذاری کن
        // تا همه گزینه‌ها نمایش داده شوند
        this.loadColumnValues(columnId, tableId, dropdown);
        
        dropdown.querySelectorAll('.sort-option').forEach(option => {
            option.classList.remove('active');
        });
        
        this.applyAllFilters();
        
        if (this.config.enableIndicators) {
            this.updateFilterIndicators();
        }
        
        if (this.config.enableSummary) {
            this.updateActiveFiltersSummary();
        }
        
        if (this.config.enableClearAll) {
            this.updateClearAllButton();
        }
        
        // ارسال event برای اطلاع سایر کامپوننت‌ها
        document.dispatchEvent(new CustomEvent('tableFilterCleared', {
            detail: {
                tableId: tableId,
                columnId: columnId,
                activeFilters: this.activeFilters
            }
        }));
        
        if (this.config.enableToast) {
            const columnName = this.columnMappings[tableId][columnId]?.name;
            this.showToast(`فیلتر ستون "${columnName}" پاک شد`);
        }
    }

    applyAllFilters() {
        this.restoreAllRows();
        
        if (Object.keys(this.activeFilters).length === 0) {
            return;
        }

        this.tableIds.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const tbody = table.querySelector('tbody');
            const rows = tbody ? tbody.querySelectorAll('tr') : [];
            
            rows.forEach(row => {
                let shouldShow = true;
                
                Object.keys(this.activeFilters).forEach(filterKey => {
                    const filter = this.activeFilters[filterKey];
                    
                    if (filter.tableId !== tableId) return;
                    
                    // همیشه از کلاس column-X استفاده کن
                    let cell = row.querySelector(`.column-${filter.columnId}`);
                    
                    if (cell) {
                        const cellValue = this.extractCellValue(cell, filter.columnId);
                        
                        if (filter.type === 'include' && !filter.values.includes(cellValue)) {
                            shouldShow = false;
                        }
                    } else {
                        console.warn(`Could not find cell for column ${filter.columnId} in row`, row);
                        // اگر سلول با کلاس پیدا نشد، این ردیف را مخفی کن تا مشکلی ایجاد نشود
                        shouldShow = false;
                    }
                });
                
                row.style.display = shouldShow ? '' : 'none';
            });
        });
    }

    restoreAllRows() {
        this.tableIds.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const tbody = table.querySelector('tbody');
            const rows = tbody ? tbody.querySelectorAll('tr') : [];
            
            rows.forEach(row => {
                row.style.display = '';
            });
        });
    }

    updateFilterIndicators() {
        this.tableIds.forEach(tableId => {
            Object.keys(this.columnMappings[tableId]).forEach(columnId => {
                const header = document.querySelector(`.column-${columnId}`);
                if (!header) return;
                
                const button = header.querySelector(`.${this.config.filterButtonClass}`);
                if (!button) return;
                
                const filterKey = `${tableId}-${columnId}`;
                const sortKey = `${tableId}-${columnId}`;
                
                if (this.activeFilters[filterKey] || this.sortState[sortKey]) {
                    button.classList.add('has-filters');
                } else {
                    button.classList.remove('has-filters');
                }
            });
        });
    }

    createActiveFiltersSummary() {
        if (document.querySelector('.active-filters-summary')) {
            return; // قبلاً ایجاد شده
        }
        
        const summary = document.createElement('div');
        summary.className = 'active-filters-summary';
        summary.innerHTML = `
            <div class="active-filters-title">فیلترهای فعال:</div>
            <div class="active-filters-content"></div>
        `;
        
        // جستجو برای مکان مناسب
        const tableContainer = document.querySelector('.table-responsive, .table-container');
        if (tableContainer) {
            tableContainer.parentNode.insertBefore(summary, tableContainer);
        } else {
            const firstTable = document.querySelector(this.config.tableSelector);
            if (firstTable) {
                firstTable.parentNode.insertBefore(summary, firstTable);
            }
        }
    }

    updateActiveFiltersSummary() {
        const summary = document.querySelector('.active-filters-summary');
        const content = summary?.querySelector('.active-filters-content');
        
        if (!summary || !content) return;
        
        const totalActiveFilters = Object.keys(this.activeFilters).length + Object.keys(this.sortState).length;
        
        if (totalActiveFilters === 0) {
            summary.classList.remove('show');
            return;
        }
        
        let html = '';
        
        Object.keys(this.activeFilters).forEach(filterKey => {
            const filter = this.activeFilters[filterKey];
            const columnName = this.columnMappings[filter.tableId][filter.columnId]?.name;
            html += `
                <span class="active-filter-tag" data-filter-key="${filterKey}" data-type="filter">
                    <i class="fas fa-filter"></i>
                    ${columnName}: ${filter.values.length} مورد
                    <button type="button" class="remove-filter-btn" data-filter-key="${filterKey}">
                        <i class="fas fa-times"></i>
                    </button>
                </span>
            `;
        });
        
        Object.keys(this.sortState).forEach(sortKey => {
            const [tableId, columnId] = sortKey.split('-');
            const columnName = this.columnMappings[tableId][columnId]?.name;
            const direction = this.sortState[sortKey];
            html += `
                <span class="active-filter-tag" data-sort-key="${sortKey}" data-type="sort">
                    <i class="fas fa-sort"></i>
                    ${columnName}: ${direction === 'asc' ? 'صعودی' : 'نزولی'}
                    <button type="button" class="remove-filter-btn" data-sort-key="${sortKey}">
                        <i class="fas fa-times"></i>
                    </button>
                </span>
            `;
        });
        
        content.innerHTML = html;
        
        const titleElement = summary.querySelector('.active-filters-title');
        if (titleElement) {
            titleElement.innerHTML = `
                فیلترهای فعال:
                <span class="active-filters-count">${totalActiveFilters}</span>
            `;
        }
        
        summary.classList.add('show');
        
        // Event listeners برای حذف فیلترهای جداگانه
        content.querySelectorAll('.remove-filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const filterKey = btn.getAttribute('data-filter-key');
                const sortKey = btn.getAttribute('data-sort-key');
                
                if (filterKey) {
                    const filter = this.activeFilters[filterKey];
                    delete this.activeFilters[filterKey];
                    
                    // اگر dropdown باز است، مقادیر را دوباره بارگذاری کن
                    const openDropdown = document.querySelector(`.filter-dropdown[data-column-id="${filter.columnId}"][data-table-id="${filter.tableId}"]`);
                    if (openDropdown) {
                        this.loadColumnValues(filter.columnId, filter.tableId, openDropdown);
                    }
                } else if (sortKey) {
                    delete this.sortState[sortKey];
                }
                
                this.applyAllFilters();
                this.updateFilterIndicators();
                this.updateActiveFiltersSummary();
                this.updateClearAllButton();
                
                // ارسال event
                document.dispatchEvent(new CustomEvent('tableFilterRemoved', {
                    detail: {
                        filterKey: filterKey,
                        sortKey: sortKey,
                        activeFilters: this.activeFilters
                    }
                }));
            });
        });
        
        // حذف event listener قدیمی که کل tag را کلیک می‌کرد
        content.querySelectorAll('.active-filter-tag').forEach(tag => {
            tag.addEventListener('click', (e) => {
                // فقط اگر روی دکمه حذف کلیک نشده باشد
                if (!e.target.closest('.remove-filter-btn')) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
        });
    }

    createClearAllButton() {
        if (document.querySelector('.clear-all-filters')) {
            return; // قبلاً ایجاد شده
        }
        
        const button = document.createElement('button');
        button.className = 'clear-all-filters';
        button.innerHTML = '<i class="fas fa-times-circle"></i> پاک کردن همه فیلترها';
        
        button.addEventListener('click', () => {
            this.clearAllFilters();
        });
        
        document.body.appendChild(button);
    }

    clearAllFilters() {
        this.activeFilters = {};
        this.sortState = {};
        
        this.restoreAllRows();
        
        if (this.config.enableIndicators) {
            this.updateFilterIndicators();
        }
        
        if (this.config.enableSummary) {
            this.updateActiveFiltersSummary();
        }
        
        if (this.config.enableClearAll) {
            this.updateClearAllButton();
        }
        
        // بعد از پاک کردن همه فیلترها، اگر dropdown باز است، مقادیر را دوباره بارگذاری کن
        document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
            const columnId = dropdown.getAttribute('data-column-id');
            const tableId = dropdown.getAttribute('data-table-id');
            
            if (columnId && tableId) {
                this.loadColumnValues(columnId, tableId, dropdown);
            }
            
            dropdown.querySelectorAll('.sort-option').forEach(option => {
                option.classList.remove('active');
            });
        });
        
        // ارسال event برای اطلاع سایر کامپوننت‌ها
        document.dispatchEvent(new CustomEvent('tableFiltersCleared', {
            detail: {
                activeFilters: this.activeFilters
            }
        }));
        
        if (this.config.enableToast) {
            this.showToast('همه فیلترها پاک شدند');
        }
    }

    updateClearAllButton() {
        const button = document.querySelector('.clear-all-filters');
        if (!button) return;
        
        const hasActiveFilters = Object.keys(this.activeFilters).length > 0 || Object.keys(this.sortState).length > 0;
        
        if (hasActiveFilters) {
            button.classList.add('show');
        } else {
            button.classList.remove('show');
        }
    }

    closeAllDropdowns() {
        const dropdowns = document.querySelectorAll('.filter-dropdown.show');
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
            setTimeout(() => {
                dropdown.remove();
            }, 300);
        });
        
        const overlays = document.querySelectorAll('.filter-overlay.show');
        overlays.forEach(overlay => {
            overlay.classList.remove('show');
            setTimeout(() => {
                overlay.remove();
            }, 300);
        });
        
        // ریست تمام دکمه‌های فیلتر فعال
        document.querySelectorAll(`.${this.config.filterButtonClass}.active, .filter-btn.active`).forEach(button => {
            button.classList.remove('active');
        });
        
        // بستن dropdown تنظیم ستون‌ها
        const columnVisibilityDropdown = document.querySelector('.column-visibility-dropdown');
        if (columnVisibilityDropdown) {
            columnVisibilityDropdown.remove();
        }
    }

    showToast(message) {
        // پیام‌های Toast را غیرفعال کردیم
        return;
        
        if (!this.config.enableToast) return;
        
        // بررسی وجود Bootstrap Toast
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = document.createElement('div');
            toast.className = 'position-fixed bottom-0 end-0 p-3';
            toast.style.zIndex = 1100;
            
            toast.innerHTML = `
                <div class="toast align-items-center text-white bg-success border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas fa-check-circle me-2"></i> ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(toast);
            
            const toastElement = toast.querySelector('.toast');
            const bsToast = new bootstrap.Toast(toastElement, {
                animation: true,
                autohide: true,
                delay: 3000
            });
            
            bsToast.show();
            
            toastElement.addEventListener('hidden.bs.toast', () => {
                document.body.removeChild(toast);
            });
        } else {
            // Toast ساده
            const toast = document.createElement('div');
            toast.className = 'simple-toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                padding: 12px 20px;
                border-radius: 6px;
                z-index: 1100;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                opacity: 0;
                transition: opacity 0.3s ease;
            `;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '1';
            }, 10);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => {
                    document.body.removeChild(toast);
                }, 300);
            }, 3000);
        }
    }

    // متدهای عمومی برای کنترل خارجی
    addTable(tableSelector) {
        const table = document.querySelector(tableSelector);
        if (table && !table.id) {
            table.id = `auto-table-${this.tableIds.length}`;
        }
        if (table && !this.tableIds.includes(table.id)) {
            this.tableIds.push(table.id);
            this.setupColumnMappings();
            this.storeOriginalRows();
        }
    }

    removeTable(tableId) {
        const index = this.tableIds.indexOf(tableId);
        if (index > -1) {
            this.tableIds.splice(index, 1);
            delete this.columnMappings[tableId];
            delete this.originalRows[tableId];
            
            // پاک کردن فیلترهای مربوط به این جدول
            Object.keys(this.activeFilters).forEach(key => {
                if (key.startsWith(tableId + '-')) {
                    delete this.activeFilters[key];
                }
            });
            
            Object.keys(this.sortState).forEach(key => {
                if (key.startsWith(tableId + '-')) {
                    delete this.sortState[key];
                }
            });
        }
    }

    getFilteredRowCount(tableId = null) {
        if (tableId) {
            const table = document.getElementById(tableId);
            if (!table) return 0;
            
            const tbody = table.querySelector('tbody');
            const rows = tbody ? tbody.querySelectorAll('tr') : [];
            
            return Array.from(rows).filter(row => row.style.display !== 'none').length;
        } else {
            let total = 0;
            this.tableIds.forEach(id => {
                total += this.getFilteredRowCount(id);
            });
            return total;
        }
    }

    // متد جدید برای اضافه کردن فیلتر به جدول موجود
    enableFilterForTable(tableSelector) {
        const table = document.querySelector(tableSelector);
        if (!table) {
            console.warn(`Table with selector "${tableSelector}" not found`);
            return false;
        }
        
        if (!table.id) {
            table.id = `auto-table-${Date.now()}`;
        }
        
        if (!this.tableIds.includes(table.id)) {
            this.tableIds.push(table.id);
            
            // تنظیم mapping برای این جدول
            const headers = table.querySelectorAll('thead th, thead td');
            this.columnMappings[table.id] = {};
            
            headers.forEach((header, index) => {
                let columnId = this.getColumnId(header, index, table.id);
                let columnName = this.getColumnName(header);
                let columnType = this.detectColumnType(header, table.id, index);
                
                this.columnMappings[table.id][columnId] = {
                    name: columnName,
                    type: columnType,
                    index: index,
                    tableId: table.id
                };
                
                this.addFilterButton(header, columnId, table.id);
            });
            
            // ذخیره ردیف‌های اصلی
            const tbody = table.querySelector('tbody');
            this.originalRows[table.id] = tbody ? Array.from(tbody.querySelectorAll('tr')) : [];
            
            if (this.config.enableToast) {
                this.showToast(`فیلتر برای جدول فعال شد`);
            }
            
            return true;
        }
        
        return false;
    }

    // متد کمکی برای فعال‌سازی آسان
    static enableForAll(tableSelector = 'table', config = {}) {
        const mergedConfig = {
            tableSelector: tableSelector,
            autoInit: true,
            ...config
        };
        
        return new TableFilter(mergedConfig);
    }

    setupColumnVisibilityControl() {
        this.tableIds.forEach(tableId => {
            this.createColumnVisibilityButton(tableId);
        });
    }

    createColumnVisibilityButton(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        // جستجوی دکمه موجود
        let existingButton = table.parentElement.querySelector('.column-visibility-btn');
        if (existingButton) return;

        // ایجاد دکمه تنظیم ستون‌ها
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'table-filter-controls';
        buttonContainer.style.cssText = `
            display: flex;
            justify-content: flex-end;
            margin-bottom: 10px;
            gap: 10px;
        `;

        const columnVisibilityBtn = document.createElement('button');
        columnVisibilityBtn.className = 'column-visibility-btn';
        columnVisibilityBtn.innerHTML = `
            <i class="fas fa-columns"></i>
            تنظیم ستون‌ها
        `;
        columnVisibilityBtn.style.cssText = `
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.3s ease;
        `;

        columnVisibilityBtn.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#e9ecef';
        });

        columnVisibilityBtn.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '#f8f9fa';
        });

        columnVisibilityBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleColumnVisibilityDropdown(tableId, columnVisibilityBtn);
        });

        buttonContainer.appendChild(columnVisibilityBtn);
        table.parentElement.insertBefore(buttonContainer, table);
    }

    toggleColumnVisibilityDropdown(tableId, buttonElement) {
        // بستن سایر dropdown ها
        this.closeAllDropdowns();
        
        // بررسی وجود dropdown موجود
        let existingDropdown = document.querySelector('.column-visibility-dropdown');
        if (existingDropdown) {
            existingDropdown.remove();
            return;
        }

        const dropdown = this.createColumnVisibilityDropdown(tableId);
        document.body.appendChild(dropdown);

        // موقعیت‌یابی dropdown - موقعیت بهتر، نزدیک به دکمه
        const rect = buttonElement.getBoundingClientRect();
        dropdown.style.position = 'absolute';
        dropdown.style.top = `${rect.top + window.scrollY}px`;
        dropdown.style.left = `${rect.left - dropdown.offsetWidth + rect.width}px`;
        dropdown.style.zIndex = '9999';
        dropdown.style.maxHeight = '80vh';
        dropdown.style.overflow = 'auto';

        // بستن dropdown با کلیک خارج از آن
        setTimeout(() => {
            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target) && !buttonElement.contains(e.target)) {
                    dropdown.remove();
                }
            }, { once: true });
        }, 100);
    }

    createColumnVisibilityDropdown(tableId) {
        const table = document.getElementById(tableId);
        const dropdown = document.createElement('div');
        dropdown.className = 'column-visibility-dropdown';
        dropdown.style.cssText = `
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            padding: 10px;
            min-width: 250px;
            max-height: 400px;
            overflow-y: auto;
            direction: rtl;
        `;

        const title = document.createElement('div');
        title.innerHTML = '<strong>انتخاب ستون‌های قابل نمایش</strong>';
        title.style.cssText = `
            padding: 5px 0 10px 0;
            border-bottom: 1px solid #eee;
            margin-bottom: 10px;
            text-align: center;
        `;
        dropdown.appendChild(title);

        // دکمه‌های انتخاب همه / هیچکدام
        const controlButtons = document.createElement('div');
        controlButtons.style.cssText = `
            display: flex;
            gap: 5px;
            margin-bottom: 10px;
        `;

        const selectAllBtn = document.createElement('button');
        selectAllBtn.textContent = 'انتخاب همه';
        selectAllBtn.style.cssText = `
            flex: 1;
            padding: 5px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        `;
        selectAllBtn.addEventListener('click', () => this.toggleAllColumns(tableId, true));

        const deselectAllBtn = document.createElement('button');
        deselectAllBtn.textContent = 'حذف همه';
        deselectAllBtn.style.cssText = `
            flex: 1;
            padding: 5px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        `;
        deselectAllBtn.addEventListener('click', () => this.toggleAllColumns(tableId, false));

        // اضافه کردن دکمه بازگشت به ترتیب پیش‌فرض
        const resetOrderBtn = document.createElement('button');
        resetOrderBtn.textContent = 'بازگشت به ترتیب اولیه';
        resetOrderBtn.style.cssText = `
            width: 100%;
            padding: 8px;
            margin-top: 5px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            font-weight: bold;
            display: block;
        `;
        resetOrderBtn.addEventListener('click', () => this.resetColumnOrder(tableId));

        controlButtons.appendChild(selectAllBtn);
        controlButtons.appendChild(deselectAllBtn);
        
        dropdown.appendChild(controlButtons);
        
        // اضافه کردن دکمه بازگشت به حالت اولیه در div جدید
        const resetContainer = document.createElement('div');
        resetContainer.style.cssText = `
            margin-bottom: 10px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        `;
        resetContainer.appendChild(resetOrderBtn);
        dropdown.appendChild(resetContainer);

        // لیست ستون‌ها
        const columnsList = document.createElement('div');
        const headers = table.querySelectorAll('thead th, thead td');
        
        headers.forEach((header, index) => {
            // حذف ستون چک‌باکس انتخاب (فقط ستون اول که معمولاً چک‌باکس است)
            if (index === 0 && header.querySelector('input[type="checkbox"]')) {
                return;
            }

            const columnItem = document.createElement('div');
            columnItem.style.cssText = `
                display: flex;
                align-items: center;
                padding: 5px 0;
                cursor: pointer;
                transition: background-color 0.2s;
            `;

            columnItem.addEventListener('mouseenter', function() {
                this.style.backgroundColor = '#f8f9fa';
            });

            columnItem.addEventListener('mouseleave', function() {
                this.style.backgroundColor = 'transparent';
            });

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = header.style.display !== 'none';
            checkbox.style.marginLeft = '8px';
            checkbox.dataset.columnIndex = index; // ذخیره index واقعی
            checkbox.addEventListener('change', () => {
                this.toggleColumnVisibility(tableId, index, checkbox.checked);
            });

            const label = document.createElement('label');
            label.textContent = header.textContent.trim() || `ستون ${index + 1}`;
            label.style.cursor = 'pointer';
            label.addEventListener('click', () => {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
            });

            columnItem.appendChild(checkbox);
            columnItem.appendChild(label);
            columnsList.appendChild(columnItem);
        });

        dropdown.appendChild(columnsList);
        return dropdown;
    }

    toggleColumnVisibility(tableId, columnIndex, isVisible) {
        const table = document.getElementById(tableId);
        if (!table) return;

        console.log(`Toggle visibility of column ${columnIndex} to ${isVisible ? 'visible' : 'hidden'}`);

        // تغییر نمایش در header
        const headerCells = table.querySelectorAll('thead th, thead td');
        if (headerCells[columnIndex]) {
            headerCells[columnIndex].style.display = isVisible ? '' : 'none';
            
            // بدست آوردن کلاس column-X از هدر برای استفاده در سلول‌های بدنه
            const columnClass = Array.from(headerCells[columnIndex].classList)
                .find(cls => cls.startsWith('column-'));
            
            // اگر کلاس column-X را یافتیم، از آن برای یافتن سلول‌های مرتبط استفاده کنیم
            if (columnClass) {
                // تغییر نمایش سلول‌هایی که دارای کلاس مشابه هستند (روش دقیق‌تر)
                const bodyCells = table.querySelectorAll(`tbody td.${columnClass}`);
                bodyCells.forEach(cell => {
                    cell.style.display = isVisible ? '' : 'none';
                });
                console.log(`Found ${bodyCells.length} cells with class ${columnClass}`);
            } else {
                // تغییر نمایش در تمام ردیف‌ها با استفاده از ایندکس (روش پشتیبان)
                console.log(`No column class found for column index ${columnIndex}, using index-based method`);
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td, th');
                    if (cells[columnIndex]) {
                        cells[columnIndex].style.display = isVisible ? '' : 'none';
                    }
                });
            }
        } else {
            console.warn(`Header cell at index ${columnIndex} not found`);
        }
    }

    toggleAllColumns(tableId, isVisible) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const dropdown = document.querySelector('.column-visibility-dropdown');
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
        
        checkboxes.forEach((checkbox) => {
            if (checkbox.checked !== isVisible) {
                checkbox.checked = isVisible;
                // استفاده از index ذخیره شده
                const columnIndex = parseInt(checkbox.dataset.columnIndex);
                if (!isNaN(columnIndex)) {
                    this.toggleColumnVisibility(tableId, columnIndex, isVisible);
                }
            }
        });
    }

    // حذف دکمه‌های سورت مثلثی موجود که با سیستم فیلتر ما تداخل دارند
    removeTriangleSorters(headers) {
        headers.forEach(header => {
            // حذف المان‌های مثلثی سورت که ممکن است از قبل وجود داشته باشند
            const triangles = header.querySelectorAll('.sorting, .sorting_asc, .sorting_desc');
            triangles.forEach(triangle => {
                triangle.classList.remove('sorting', 'sorting_asc', 'sorting_desc');
                triangle.style.backgroundImage = 'none';
            });
        });
    }

    // اضافه کردن متد جدید برای بازگشت به ترتیب اولیه ستون‌ها
    resetColumnOrder(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;
        
        // نمایش پیام بارگیری
        this.showToast('در حال بازگردانی ترتیب پیش‌فرض ستون‌ها...');
        
        // ارسال درخواست به سرور برای بازگشت به ترتیب پیش‌فرض
        fetch('/purchase/reset_column_order/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                table_id: tableId
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server response was not OK');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // بازخوانی صفحه برای اعمال تغییرات
                window.location.reload();
            } else {
                this.showToast('خطا در بازگردانی ترتیب ستون‌ها: ' + (data.error || 'خطای نامشخص'));
            }
        })
        .catch(error => {
            console.error('Error resetting column order:', error);
            this.showToast('خطا در ارتباط با سرور');
        });
    }
    
    // متد کمکی برای دریافت CSRF توکن
    getCsrfToken() {
        // تلاش برای یافتن از طریق input
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        
        // تلاش برای یافتن در meta tag
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            return csrfMeta.content;
        }
        
        // روش جایگزین: دریافت از کوکی
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
            
        return cookieValue || '';
    }
}

// تابع راحت برای ایجاد فیلتر
window.createTableFilter = function(config = {}) {
    return new TableFilter(config);
};

// تابع ساده برای فعال‌سازی فیلتر روی همه جداول
window.enableTableFilters = function(selector = 'table', config = {}) {
    return TableFilter.enableForAll(selector, config);
};

// نسخه سازگار با jQuery
if (typeof jQuery !== 'undefined') {
    jQuery.fn.tableFilter = function(config = {}) {
        const selector = this.selector || this.get(0)?.tagName?.toLowerCase();
        config.tableSelector = selector;
        return new TableFilter(config);
    };
}

// فعال‌سازی خودکار اگر کلاس مشخصی وجود داشته باشد
document.addEventListener('DOMContentLoaded', function() {
    const autoTables = document.querySelectorAll('.enable-filter, .table-filterable');
    if (autoTables.length > 0) {
        autoTables.forEach(table => {
            if (!table.id) {
                table.id = `auto-filter-table-${Date.now()}`;
            }
            new TableFilter({
                tableSelector: `#${table.id}`,
                autoInit: true
            });
        });
    }
});