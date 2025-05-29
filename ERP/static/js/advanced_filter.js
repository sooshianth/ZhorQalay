/**
 * Advanced Filter System for Purchase List
 * Provides sorting, filtering, and searching capabilities for table columns
 */

class AdvancedFilter {
    constructor() {
        this.activeFilters = {};
        this.originalRows = [];
        this.columnMappings = {};
        this.sortState = {};
        this.init();
    }

    init() {
        this.setupColumnMappings();
        this.storeOriginalRows();
        this.attachEventListeners();
        this.createClearAllButton();
        this.createActiveFiltersSummary();
    }

    setupColumnMappings() {
        // نقشه‌برداری ستون‌ها با شناسه‌ها و نام‌های نمایشی
        this.columnMappings = {
            'date': {
                name: 'تاریخ',
                type: 'date',
                index: this.getColumnIndex('date')
            },
            'customer': {
                name: 'مشتری',
                type: 'text',
                index: this.getColumnIndex('customer')
            },
            'invoice_id': {
                name: 'کد درون سازمانی',
                type: 'text',
                index: this.getColumnIndex('invoice_id')
            },
            'sales_agent': {
                name: 'نماینده فروش',
                type: 'text',
                index: this.getColumnIndex('sales_agent')
            },
            'purchase_number': {
                name: 'شماره خرید',
                type: 'text',
                index: this.getColumnIndex('purchase_number')
            },
            'weight': {
                name: 'وزن',
                type: 'number',
                index: this.getColumnIndex('weight')
            },
            'cargo': {
                name: 'کوتاژ',
                type: 'text',
                index: this.getColumnIndex('cargo')
            },
            'status': {
                name: 'وضعیت',
                type: 'text',
                index: this.getColumnIndex('status')
            },
            'address': {
                name: 'آدرس',
                type: 'text',
                index: this.getColumnIndex('address')
            },
            'description': {
                name: 'توضیحات',
                type: 'text',
                index: this.getColumnIndex('description')
            },
            'company_price': {
                name: 'فی خرید',
                type: 'number',
                index: this.getColumnIndex('company_price')
            },
            'customer_price': {
                name: 'فی فروش',
                type: 'number',
                index: this.getColumnIndex('customer_price')
            },
            'factor_code': {
                name: 'فاکتور کد',
                type: 'text',
                index: this.getColumnIndex('factor_code')
            },
            'tracking_number': {
                name: 'شماره پیگیری',
                type: 'text',
                index: this.getColumnIndex('tracking_number')
            },
            'shenase_takhsis': {
                name: 'شناسه تخصیص',
                type: 'text',
                index: this.getColumnIndex('shenase_takhsis')
            },
            'code_melli_tahvil': {
                name: 'کد ملی تحویل',
                type: 'text',
                index: this.getColumnIndex('code_melli_tahvil')
            },
            'bazaargah_phone_number': {
                name: 'شماره تلفن بازارگاه',
                type: 'text',
                index: this.getColumnIndex('bazaargah_phone_number')
            },
            'buyer_name': {
                name: 'نام خریدار',
                type: 'text',
                index: this.getColumnIndex('buyer_name')
            },
            'tahvil_phone_number': {
                name: 'شماره تلفن تحویل',
                type: 'text',
                index: this.getColumnIndex('tahvil_phone_number')
            },
            'send_cottage_sms': {
                name: 'ارسال پیامک کوتاژ',
                type: 'boolean',
                index: this.getColumnIndex('send_cottage_sms')
            },
            'total_weight': {
                name: 'وزن کل',
                type: 'number',
                index: this.getColumnIndex('total_weight')
            },
            'delivered_weight': {
                name: 'وزن بارنامه شده',
                type: 'number',
                index: this.getColumnIndex('delivered_weight')
            },
            'type': {
                name: 'نوع خرید',
                type: 'text',
                index: this.getColumnIndex('type')
            },
            'amount_paid': {
                name: 'مبلغ پرداختی',
                type: 'number',
                index: this.getColumnIndex('amount_paid')
            },
            'payment_method': {
                name: 'شیوه پرداخت',
                type: 'text',
                index: this.getColumnIndex('payment_method')
            },
            'updated_at': {
                name: 'تاریخ بروزرسانی',
                type: 'date',
                index: this.getColumnIndex('updated_at')
            },
            'is_weight_costed': {
                name: 'کسر از وزن موجود',
                type: 'boolean',
                index: this.getColumnIndex('is_weight_costed')
            },
            'is_ap_af': {
                name: 'اتوکامپلیت شده',
                type: 'boolean',
                index: this.getColumnIndex('is_ap_af')
            },
            'extelaf_type': {
                name: 'نوع اختلاف',
                type: 'text',
                index: this.getColumnIndex('extelaf_type')
            },
            'extelaf_weight': {
                name: 'وزن اختلاف',
                type: 'number',
                index: this.getColumnIndex('extelaf_weight')
            },
            'extelaf_amount': {
                name: 'مبلغ اختلاف',
                type: 'number',
                index: this.getColumnIndex('extelaf_amount')
            },
            'is_urgent': {
                name: 'فوری',
                type: 'boolean',
                index: this.getColumnIndex('is_urgent')
            },
            'is_canceled': {
                name: 'لغو شده',
                type: 'boolean',
                index: this.getColumnIndex('is_canceled')
            },
            'is_archived': {
                name: 'آرشیو شده',
                type: 'boolean',
                index: this.getColumnIndex('is_archived')
            },
            'is_fully_tasvied': {
                name: 'تسویه کامل',
                type: 'boolean',
                index: this.getColumnIndex('is_fully_tasvied')
            },
            'is_factored': {
                name: 'ثبت فاکتور',
                type: 'boolean',
                index: this.getColumnIndex('is_factored')
            },
            'priority': {
                name: 'اولویت',
                type: 'text',
                index: this.getColumnIndex('priority')
            },
            'priority_reason': {
                name: 'دلیل اولویت',
                type: 'text',
                index: this.getColumnIndex('priority_reason')
            },
            'actions': {
                name: 'جزئیات',
                type: 'text',
                index: this.getColumnIndex('actions')
            }
        };
    }

    getColumnIndex(columnId) {
        const headers = document.querySelectorAll('table thead th');
        for (let i = 0; i < headers.length; i++) {
            if (headers[i].classList.contains(`column-${columnId}`)) {
                return i;
            }
        }
        return -1;
    }

    storeOriginalRows() {
        // ذخیره ردیف‌های اصلی برای بازگردانی
        const activeTable = document.getElementById('activePurchasesTable');
        const archivedTable = document.getElementById('archivedPurchasesTable');
        
        this.originalRows = {
            active: activeTable ? Array.from(activeTable.querySelectorAll('tr')) : [],
            archived: archivedTable ? Array.from(archivedTable.querySelectorAll('tr')) : []
        };
    }

    attachEventListeners() {
        // کلیک خارج از dropdown برای بستن
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.filter-dropdown') && !e.target.closest('.filter-dropdown-btn')) {
                this.closeAllDropdowns();
            }
        });

        // رویدادهای کیبورد
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllDropdowns();
            }
        });
    }

    createFilterDropdown(columnId, headerElement) {
        const columnData = this.columnMappings[columnId];
        if (!columnData) return null;

        // ایجاد dropdown جدید
        const dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        dropdown.innerHTML = this.getDropdownHTML(columnId, columnData);

        // اضافه کردن به header
        headerElement.style.position = 'relative';
        headerElement.appendChild(dropdown);

        // بارگذاری مقادیر ستون
        this.loadColumnValues(columnId, dropdown);

        // اضافه کردن رویدادها
        this.attachDropdownEvents(dropdown, columnId);
        
        // اطمینان از وجود دکمه‌های اعمال فیلتر در انتهای dropdown
        const applyBtn = dropdown.querySelector('[data-action="apply"]');
        if (!applyBtn) {
            console.error('Apply button not found, recreating actions section');
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'filter-actions';
            actionsDiv.innerHTML = `
                <button class="filter-action-btn btn-primary" data-action="apply">
                    اعمال فیلتر
                </button>
                <button class="filter-action-btn btn-outline-secondary" data-action="clear">
                    پاک کردن
                </button>
            `;
            
            dropdown.appendChild(actionsDiv);
            this.attachActionEvents(actionsDiv, columnId, dropdown);
        }

        return dropdown;
    }

    getDropdownHTML(columnId, columnData) {
        return `
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-sort"></i>
                    مرتب‌سازی
                </div>
                <div class="sort-option" data-sort="asc" data-column="${columnId}">
                    <i class="fas fa-sort-alpha-down"></i>
                    مرتب‌سازی A تا Z
                </div>
                <div class="sort-option" data-sort="desc" data-column="${columnId}">
                    <i class="fas fa-sort-alpha-up"></i>
                    مرتب‌سازی Z تا A
                </div>
            </div>
            
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-search"></i>
                    جستجو
                </div>
                <input type="text" class="filter-search" placeholder="جستجو در ${columnData.name}...">
            </div>
            
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-filter"></i>
                    فیلتر بر اساس مقادیر
                </div>
                <div class="select-all-filters" data-action="select-all">
                    ✓ انتخاب همه
                </div>
                <div class="filter-values-container">
                    <div class="filter-loading">
                        <i class="fas fa-spinner fa-spin"></i>
                        در حال بارگذاری...
                    </div>
                </div>
            </div>
            
            <div class="filter-actions">
                <button class="filter-action-btn btn-primary" data-action="apply">
                    اعمال فیلتر
                </button>
                <button class="filter-action-btn btn-outline-secondary" data-action="clear">
                    پاک کردن
                </button>
            </div>
        `;
    }

    attachDropdownEvents(dropdown, columnId) {
        console.log('Attaching events for column:', columnId);
        
        // رویدادهای مرتب‌سازی
        dropdown.querySelectorAll('.sort-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const sortDirection = option.getAttribute('data-sort');
                this.applySorting(columnId, sortDirection);
                this.updateSortVisuals(dropdown, option);
            });
        });

        // رویداد جستجو
        const searchInput = dropdown.querySelector('.filter-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterValues(dropdown, e.target.value.toLowerCase());
            });
        }

        // رویداد انتخاب همه
        const selectAllElement = dropdown.querySelector('.select-all-filters');
        if (selectAllElement) {
            selectAllElement.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleSelectAll(dropdown);
            });
        }

        // رویدادهای دکمه‌ها
        const applyBtn = dropdown.querySelector('[data-action="apply"]');
        const clearBtn = dropdown.querySelector('[data-action="clear"]');
        
        console.log('Apply button found:', !!applyBtn);
        console.log('Clear button found:', !!clearBtn);
        
        if (applyBtn) {
            applyBtn.addEventListener('click', (e) => {
                console.log('Apply button clicked for column:', columnId);
                e.stopPropagation();
                this.applyColumnFilter(columnId, dropdown);
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                console.log('Clear button clicked for column:', columnId);
                e.stopPropagation();
                this.clearColumnFilter(columnId, dropdown);
            });
        }

        // جلوگیری از بسته شدن dropdown هنگام کلیک داخل آن
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        console.log('All events attached for column:', columnId);
    }

    async loadColumnValues(columnId, dropdown) {
        try {
            const values = this.getUniqueColumnValues(columnId);
            this.renderFilterValues(dropdown, values, columnId);
            
            // اطمینان از ظاهر شدن دکمه‌های اعمال و پاک کردن فیلتر
            const filterActionsSection = dropdown.querySelector('.filter-actions');
            if (filterActionsSection) {
                filterActionsSection.style.display = 'flex';
            }
        } catch (error) {
            console.error('Error loading column values:', error);
            const container = dropdown.querySelector('.filter-values-container');
            if (container) {
                container.innerHTML = '<div class="no-filter-values">خطا در بارگذاری مقادیر</div>';
            }
        }
    }

    getUniqueColumnValues(columnId) {
        const columnIndex = this.columnMappings[columnId]?.index;
        if (columnIndex === -1) return [];

        const values = new Set();
        
        // دریافت مقادیر از جدول فعال - فقط ردیف‌های قابل مشاهده
        const activeRows = document.querySelectorAll('#activePurchasesTable tr');
        activeRows.forEach(row => {
            // فقط ردیف‌هایی که نمایش داده می‌شوند (فیلتر نشده‌اند)
            if (row.style.display !== 'none') {
                const cell = row.children[columnIndex];
                if (cell) {
                    let value = this.extractCellValue(cell, columnId);
                    if (value && value.trim() !== '' && value !== 'تعیین نشده') {
                        values.add(value.trim());
                    }
                }
            }
        });

        // دریافت مقادیر از جدول آرشیو (اگر نمایان باشد) - فقط ردیف‌های قابل مشاهده
        const archivedContent = document.getElementById('archivedContent');
        if (archivedContent && archivedContent.style.display !== 'none') {
            const archivedRows = document.querySelectorAll('#archivedPurchasesTable tr');
            archivedRows.forEach(row => {
                // فقط ردیف‌هایی که نمایش داده می‌شوند (فیلتر نشده‌اند)
                if (row.style.display !== 'none') {
                    const cell = row.children[columnIndex];
                    if (cell) {
                        let value = this.extractCellValue(cell, columnId);
                        if (value && value.trim() !== '' && value !== 'تعیین نشده') {
                            values.add(value.trim());
                        }
                    }
                }
            });
        }

        return Array.from(values).sort();
    }

    extractCellValue(cell, columnId) {
        // استخراج متن از انواع مختلف سلول‌ها
        if (columnId === 'status') {
            // برای ستون وضعیت، متن badge را استخراج کن
            const badge = cell.querySelector('.table-status-badge');
            return badge ? badge.textContent.trim() : cell.textContent.trim();
        } else if (['weight', 'total_weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid', 'extelaf_weight', 'extelaf_amount'].includes(columnId)) {
            // برای ستون‌های عددی، عدد خالص را برگردان
            const text = cell.textContent.trim().replace(/[,\s]/g, '');
            return text;
        } else if (['send_cottage_sms', 'is_weight_costed', 'is_ap_af', 'is_urgent', 'is_canceled', 'is_archived', 'is_fully_tasvied', 'is_factored'].includes(columnId)) {
            // برای ستون‌های boolean
            const text = cell.textContent.trim();
            return text === 'بله' ? 'بله' : 'خیر';
        } else if (['date', 'updated_at'].includes(columnId)) {
            // برای ستون‌های تاریخ
            return cell.textContent.trim();
        } else {
            return cell.textContent.trim();
        }
    }

    renderFilterValues(dropdown, values, columnId) {
        const container = dropdown.querySelector('.filter-values-container');
        
        if (values.length === 0) {
            container.innerHTML = '<div class="no-filter-values">هیچ مقداری یافت نشد</div>';
            return;
        }

        const currentFilters = this.activeFilters[columnId]?.values || [];
        
        let html = '';
        values.forEach(value => {
            // اگر فیلتری برای این ستون وجود دارد، فقط مقادیر انتخاب شده را علامت بزن
            // اگر فیلتری وجود ندارد، همه را علامت بزن
            const isChecked = currentFilters.length === 0 || currentFilters.includes(value);
            html += `
                <div class="filter-value-item">
                    <input type="checkbox" id="filter-${columnId}-${this.sanitizeId(value)}" 
                           ${isChecked ? 'checked' : ''} value="${this.escapeHtml(value)}">
                    <label for="filter-${columnId}-${this.sanitizeId(value)}">${this.escapeHtml(value)}</label>
                </div>
            `;
        });

        container.innerHTML = html;

        // اضافه کردن رویداد تغییر چک‌باکس‌ها
        container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSelectAllState(dropdown);
            });
        });
        
        // به‌روزرسانی حالت انتخاب همه
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

    applySorting(columnId, direction) {
        this.sortState[columnId] = direction;
        
        const columnIndex = this.columnMappings[columnId]?.index;
        if (columnIndex === -1) return;

        // مرتب‌سازی جدول فعال
        this.sortTableByColumn('activePurchasesTable', columnIndex, direction, columnId);
        
        // مرتب‌سازی جدول آرشیو (اگر نمایان باشد)
        const archivedContent = document.getElementById('archivedContent');
        if (archivedContent && archivedContent.style.display !== 'none') {
            this.sortTableByColumn('archivedPurchasesTable', columnIndex, direction, columnId);
        }

        this.showToast(`ستون "${this.columnMappings[columnId].name}" ${direction === 'asc' ? 'صعودی' : 'نزولی'} مرتب شد`);
    }

    sortTableByColumn(tableId, columnIndex, direction, columnId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const rows = Array.from(table.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const cellA = a.children[columnIndex];
            const cellB = b.children[columnIndex];
            
            if (!cellA || !cellB) return 0;

            let valueA = this.extractCellValue(cellA, columnId);
            let valueB = this.extractCellValue(cellB, columnId);

            // تشخیص نوع داده و مرتب‌سازی
            const columnType = this.columnMappings[columnId]?.type;
            
            if (columnType === 'number') {
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

        // بازسازی جدول
        rows.forEach(row => table.appendChild(row));
    }

    updateSortVisuals(dropdown, activeOption) {
        dropdown.querySelectorAll('.sort-option').forEach(option => {
            option.classList.remove('active');
        });
        activeOption.classList.add('active');
    }

    applyColumnFilter(columnId, dropdown) {
        const selectedValues = [];
        const checkboxes = dropdown.querySelectorAll('.filter-values-container input[type="checkbox"]:checked');
        
        checkboxes.forEach(checkbox => {
            selectedValues.push(checkbox.value);
        });

        if (selectedValues.length > 0) {
            this.activeFilters[columnId] = {
                values: selectedValues,
                type: 'include'
            };
        } else {
            delete this.activeFilters[columnId];
        }

        this.applyAllFilters();
        this.updateFilterIndicators();
        this.updateActiveFiltersSummary();
        this.updateClearAllButton();
        this.closeAllDropdowns();
        
        this.showToast('فیلتر اعمال شد');
    }

    clearColumnFilter(columnId, dropdown) {
        delete this.activeFilters[columnId];
        delete this.sortState[columnId];
        
        // بازنشانی چک‌باکس‌ها
        dropdown.querySelectorAll('.filter-values-container input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = true;
        });
        
        // پاک کردن نمای مرتب‌سازی
        dropdown.querySelectorAll('.sort-option').forEach(option => {
            option.classList.remove('active');
        });
        
        this.applyAllFilters();
        this.updateFilterIndicators();
        this.updateActiveFiltersSummary();
        this.updateClearAllButton();
        
        this.showToast(`فیلتر ستون "${this.columnMappings[columnId]?.name}" پاک شد`);
    }

    applyAllFilters() {
        // بازگردانی همه ردیف‌ها
        this.restoreAllRows();
        
        if (Object.keys(this.activeFilters).length === 0) {
            // نمایش تعداد کل ردیف‌ها
            this.showRowCountToast();
            return;
        }

        // اعمال فیلترها
        const tables = ['activePurchasesTable', 'archivedPurchasesTable'];
        
        tables.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const rows = table.querySelectorAll('tr');
            
            rows.forEach(row => {
                let shouldShow = true;
                
                Object.keys(this.activeFilters).forEach(columnId => {
                    const columnIndex = this.columnMappings[columnId]?.index;
                    const filter = this.activeFilters[columnId];
                    
                    if (columnIndex !== -1 && row.children[columnIndex]) {
                        const cellValue = this.extractCellValue(row.children[columnIndex], columnId);
                        
                        if (filter.type === 'include' && !filter.values.includes(cellValue)) {
                            shouldShow = false;
                        }
                    }
                });
                
                row.style.display = shouldShow ? '' : 'none';
            });
        });
        
        // نمایش تعداد ردیف‌های فیلتر شده
        this.showRowCountToast();
    }

    showRowCountToast() {
        const activeRows = document.querySelectorAll('#activePurchasesTable tr');
        const archivedRows = document.querySelectorAll('#archivedPurchasesTable tr');
        
        let visibleActiveCount = 0;
        let totalActiveCount = activeRows.length;
        
        activeRows.forEach(row => {
            if (row.style.display !== 'none') {
                visibleActiveCount++;
            }
        });
        
        let visibleArchivedCount = 0;
        let totalArchivedCount = archivedRows.length;
        
        const archivedContent = document.getElementById('archivedContent');
        if (archivedContent && archivedContent.style.display !== 'none') {
            archivedRows.forEach(row => {
                if (row.style.display !== 'none') {
                    visibleArchivedCount++;
                }
            });
        } else {
            totalArchivedCount = 0;
        }
        
        const totalVisible = visibleActiveCount + visibleArchivedCount;
        const totalCount = totalActiveCount + totalArchivedCount;
        
        if (Object.keys(this.activeFilters).length > 0) {
            this.showToast(`${totalVisible} از ${totalCount} خرید نمایش داده شده`);
        }
    }

    restoreAllRows() {
        const tables = ['activePurchasesTable', 'archivedPurchasesTable'];
        
        tables.forEach(tableId => {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            table.querySelectorAll('tr').forEach(row => {
                row.style.display = '';
            });
        });
    }

    updateFilterIndicators() {
        Object.keys(this.columnMappings).forEach(columnId => {
            const header = document.querySelector(`.column-${columnId}`);
            if (!header) return;
            
            const button = header.querySelector('.filter-dropdown-btn');
            if (!button) return;
            
            if (this.activeFilters[columnId] || this.sortState[columnId]) {
                button.classList.add('has-filters');
            } else {
                button.classList.remove('has-filters');
            }
        });
    }

    createActiveFiltersSummary() {
        const summary = document.createElement('div');
        summary.className = 'active-filters-summary';
        summary.innerHTML = `
            <div class="active-filters-title">فیلترهای فعال:</div>
            <div class="active-filters-content"></div>
        `;
        
        // قرار دادن خلاصه فیلترها دقیقا قبل از عنوان جدول خریدهای فعال
        const activeTableHeader = document.querySelector('h3.mb-4.fw-bold.text-primary');
        if (activeTableHeader) {
            activeTableHeader.parentNode.insertBefore(summary, activeTableHeader);
        }
    }

    updateActiveFiltersSummary() {
        const summary = document.querySelector('.active-filters-summary');
        const content = summary?.querySelector('.active-filters-content');
        
        if (!summary || !content) return;
        
        const totalActiveFilters = Object.keys(this.activeFilters).length + Object.keys(this.sortState).length;
        
        if (totalActiveFilters === 0) {
            summary.classList.remove('show');
            this.updateClearAllButton();
            return;
        }
        
        let html = '';
        
        // فیلترهای مقدار
        Object.keys(this.activeFilters).forEach(columnId => {
            const columnName = this.columnMappings[columnId]?.name;
            const filter = this.activeFilters[columnId];
            html += `
                <span class="active-filter-tag" data-column="${columnId}" data-type="filter">
                    <i class="fas fa-filter"></i>
                    ${columnName}: ${filter.values.length} مورد
                </span>
            `;
        });
        
        // مرتب‌سازی‌ها
        Object.keys(this.sortState).forEach(columnId => {
            const columnName = this.columnMappings[columnId]?.name;
            const direction = this.sortState[columnId];
            html += `
                <span class="active-filter-tag" data-column="${columnId}" data-type="sort">
                    <i class="fas fa-sort"></i>
                    ${columnName}: ${direction === 'asc' ? 'صعودی' : 'نزولی'}
                </span>
            `;
        });
        
        content.innerHTML = html;
        
        // به‌روزرسانی عنوان با تعداد فیلترهای فعال
        const titleElement = summary.querySelector('.active-filters-title');
        if (titleElement) {
            titleElement.innerHTML = `
                فیلترهای فعال:
                <span class="active-filters-count">${totalActiveFilters}</span>
            `;
        }
        
        summary.classList.add('show');
        
        // اضافه کردن رویداد کلیک برای حذف تگ‌ها
        content.querySelectorAll('.active-filter-tag').forEach(tag => {
            tag.addEventListener('click', () => {
                const columnId = tag.getAttribute('data-column');
                const type = tag.getAttribute('data-type');
                
                if (type === 'filter') {
                    delete this.activeFilters[columnId];
                } else if (type === 'sort') {
                    delete this.sortState[columnId];
                }
                
                this.applyAllFilters();
                this.updateFilterIndicators();
                this.updateActiveFiltersSummary();
            });
        });
        
        // بروزرسانی دکمه پاک کردن همه فیلترها
        this.updateClearAllButton();
    }

    createClearAllButton() {
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
        this.updateFilterIndicators();
        this.updateActiveFiltersSummary();
        this.updateClearAllButton();
        
        // بازنشانی همه dropdown ها
        document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
            dropdown.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.checked = true;
            });
            dropdown.querySelectorAll('.sort-option').forEach(option => {
                option.classList.remove('active');
            });
        });
        
        this.showToast('همه فیلترها پاک شدند');
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

    toggleDropdown(columnId, headerElement) {
        // بستن سایر dropdown ها
        this.closeAllDropdowns();
        
        // بررسی وجود dropdown قبلی در کل صفحه
        const existingDropdown = document.querySelector('.filter-dropdown.show');
        if (existingDropdown) {
            existingDropdown.remove();
            
            // حذف پس‌زمینه overlay
            const overlay = document.querySelector('.filter-overlay');
            if (overlay) {
                overlay.remove();
            }
            
            // اگر کلیک روی همان فیلتر فعال بود، فقط آن را ببند
            const activeButton = document.querySelector('.filter-dropdown-btn.active');
            if (activeButton) {
                activeButton.classList.remove('active');
                return;
            }
        }
        
        // ایجاد پس‌زمینه overlay
        const overlay = document.createElement('div');
        overlay.className = 'filter-overlay';
        document.body.appendChild(overlay);
        
        // نمایش overlay
        setTimeout(() => {
            overlay.classList.add('show');
        }, 10);
        
        // ایجاد dropdown به صورت modal
        const dropdown = this.createModalFilterDropdown(columnId, headerElement);
        if (!dropdown) return;
        
        // بروزرسانی دکمه
        const button = headerElement.querySelector('.filter-dropdown-btn');
        if (button) {
            button.classList.add('active');
        }
        
        // بستن با کلیک روی overlay
        overlay.addEventListener('click', () => {
            this.closeAllDropdowns();
        });
        
        // نمایش dropdown - وسط صفحه باقی بماند
        dropdown.classList.add('show');
    }
    
    // تابع جدید برای ایجاد dropdown به صورت modal
    createModalFilterDropdown(columnId, headerElement) {
        const columnData = this.columnMappings[columnId];
        if (!columnData) return null;

        // ایجاد dropdown جدید
        const dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        
        // ایجاد container برای محتوا
        const contentContainer = document.createElement('div');
        contentContainer.className = 'filter-dropdown-content';
        
        // افزودن عنوان به dropdown
        const titleHTML = `
            <div class="filter-modal-title">
                <span>فیلتر بر اساس ${columnData.name}</span>
                <button class="close-btn">&times;</button>
            </div>
        `;
        
        // محتوای dropdown
        contentContainer.innerHTML = titleHTML + this.getDropdownHTML(columnId, columnData);
        
        // ایجاد بخش دکمه‌های عملیات
        const actionsSection = document.createElement('div');
        actionsSection.className = 'filter-actions';
        actionsSection.innerHTML = `
            <button class="filter-action-btn btn-outline-secondary" data-action="clear">
                پاک کردن
            </button>
            <button class="filter-action-btn btn-primary" data-action="apply">
                اعمال فیلتر
            </button>
        `;
        
        // اضافه کردن محتوا و دکمه‌ها به dropdown
        dropdown.appendChild(contentContainer);
        dropdown.appendChild(actionsSection);
        
        // افزودن به body
        document.body.appendChild(dropdown);
        
        // دکمه بستن
        const closeBtn = dropdown.querySelector('.close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.closeAllDropdowns();
            });
        }
        
        // بارگذاری مقادیر ستون
        this.loadColumnValues(columnId, dropdown);
        
        // اضافه کردن رویدادها
        this.attachDropdownEvents(dropdown, columnId);
        
        return dropdown;
    }

    getDropdownHTML(columnId, columnData) {
        return `
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-sort"></i>
                    مرتب‌سازی
                </div>
                <div class="sort-option" data-sort="asc" data-column="${columnId}">
                    <i class="fas fa-sort-alpha-down"></i>
                    مرتب‌سازی A تا Z
                </div>
                <div class="sort-option" data-sort="desc" data-column="${columnId}">
                    <i class="fas fa-sort-alpha-up"></i>
                    مرتب‌سازی Z تا A
                </div>
            </div>
            
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-search"></i>
                    جستجو
                </div>
                <input type="text" class="filter-search" placeholder="جستجو در ${columnData.name}...">
            </div>
            
            <div class="filter-section">
                <div class="filter-section-title">
                    <i class="fas fa-filter"></i>
                    فیلتر بر اساس مقادیر
                </div>
                <div class="select-all-filters" data-action="select-all">
                    ✓ انتخاب همه
                </div>
                <div class="filter-values-container">
                    <div class="filter-loading">
                        <i class="fas fa-spinner fa-spin"></i>
                        در حال بارگذاری...
                    </div>
                </div>
            </div>
        `;
    }

    // تغییر تابع بستن dropdown ها
    closeAllDropdowns() {
        // حذف dropdown
        const dropdown = document.querySelector('.filter-dropdown.show');
        if (dropdown) {
            dropdown.classList.remove('show');
            setTimeout(() => {
                dropdown.remove();
            }, 300); // تاخیر برای اتمام انیمیشن
        }
        
        // حذف overlay
        const overlay = document.querySelector('.filter-overlay.show');
        if (overlay) {
            overlay.classList.remove('show');
            setTimeout(() => {
                overlay.remove();
            }, 300); // تاخیر برای اتمام انیمیشن
        }
        
        // همه دکمه‌های فعال را غیرفعال کن
        document.querySelectorAll('.filter-dropdown-btn.active').forEach(button => {
            button.classList.remove('active');
        });
    }

    showToast(message) {
        // ایجاد توست اطلاع‌رسانی
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
    }

    // تابع جدید برای اضافه کردن رویدادهای دکمه‌ها
    attachActionEvents(actionsDiv, columnId, dropdown) {
        const applyBtn = actionsDiv.querySelector('[data-action="apply"]');
        const clearBtn = actionsDiv.querySelector('[data-action="clear"]');
        
        if (applyBtn) {
            applyBtn.addEventListener('click', (e) => {
                console.log('Apply button clicked for column:', columnId);
                e.stopPropagation();
                this.applyColumnFilter(columnId, dropdown);
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                console.log('Clear button clicked for column:', columnId);
                e.stopPropagation();
                this.clearColumnFilter(columnId, dropdown);
            });
        }
    }
}

// راه‌اندازی سیستم فیلتر پس از بارگذاری DOM
document.addEventListener('DOMContentLoaded', function() {
    window.advancedFilter = new AdvancedFilter();
    
    // بروزرسانی دکمه پاک کردن همه فیلترها
    window.advancedFilter.updateClearAllButton();
}); 