/**
 * مدیریت ویرایش گروهی جداول
 */
class BulkEditManager {
    constructor(config = {}) {
        this.selectedIds = new Set();
        this.currentSection = 'active'; // بخش فعلی
        this.config = {
            bulkEditPageUrl: '/table_filter/bulk-edit-page/',
            excelEditPageUrl: '/table_filter/bulk-edit-excel-page/',
            downloadTemplateUrl: '/table_filter/bulk-edit-template/',
            ...config
        };
        
        // نگهداری reference به control panelهای مختلف
        this.controlPanels = {
            active: document.querySelector('.bulk-edit-controls-active'),
            pending: document.querySelector('.bulk-edit-controls-pending'), 
            archived: document.querySelector('.bulk-edit-controls-archived')
        };
        
        // برای صفحه بارنامه‌ها و خریدهای خارج بازارگاه، یک panel واحد وجود دارد
        const tableType = this.detectTableType();
        if (tableType === 'barnameh' || tableType === 'non_bazargah_purchase' || tableType === 'non_bazargah_barnameh') {
            this.controlPanels = {
                active: document.querySelector('.bulk-edit-controls')
            };
        }
        
        // حذف control panelهای null
        Object.keys(this.controlPanels).forEach(key => {
            if (!this.controlPanels[key]) {
                delete this.controlPanels[key];
            }
        });
        
        this.currentActiveTab = this.detectActiveTab();
    }

    init() {
        this.attachEventListeners();
        this.detectCurrentSection();
        console.log('✅ BulkEditManager راه‌اندازی شد');
        
        // Debug: نمایش همه جداول موجود
        console.log('🔍 Debug: جداول موجود در صفحه:');
        document.querySelectorAll('table').forEach((table, index) => {
            console.log(`  ${index + 1}. Table ID: ${table.id}, Classes: ${table.className}`);
        });
        
        // Debug: نمایش همه checkbox های موجود
        console.log('🔍 Debug: checkbox های موجود:');
        document.querySelectorAll('input[type="checkbox"]').forEach((checkbox, index) => {
            console.log(`  ${index + 1}. Class: ${checkbox.className}, ID: ${checkbox.id}, Data-ID: ${checkbox.dataset.id}`);
        });
        
        // برای صفحه کوتاژها، به‌طور خاص کنترل‌پنل‌ها را تنظیم کنیم
        if (this.detectTableType() === 'cargo_product') {
            console.log('🔍 تشخیص صفحه کوتاژها، تنظیم کنترل‌پنل‌ها');
            this.controlPanels = {
                active: document.querySelector('.bulk-edit-controls-active'),
                archived: document.querySelector('.bulk-edit-controls-archived')
            };
            
            // حذف control panelهای null
            Object.keys(this.controlPanels).forEach(key => {
                if (!this.controlPanels[key]) {
                    delete this.controlPanels[key];
                }
            });
            
            this.updateAllControlPanels();
        }
        
        // برای صفحه خریدهای خارج بازارگاه، کنترل‌پنل‌ها را تنظیم کنیم
        if (this.detectTableType() === 'non_bazargah_purchase') {
            console.log('🔍 تشخیص صفحه خریدهای خارج بازارگاه، تنظیم کنترل‌پنل‌ها');
            this.controlPanels = {
                active: document.querySelector('.bulk-edit-controls')
            };
            
            // حذف control panelهای null
            Object.keys(this.controlPanels).forEach(key => {
                if (!this.controlPanels[key]) {
                    delete this.controlPanels[key];
                }
            });
            
            this.updateAllControlPanels();
        }
        
        // برای صفحه بارنامه‌های خارج بازارگاه، کنترل‌پنل‌ها را تنظیم کنیم
        if (this.detectTableType() === 'non_bazargah_barnameh') {
            console.log('🔍 تشخیص صفحه بارنامه‌های خارج بازارگاه، تنظیم کنترل‌پنل‌ها');
            this.controlPanels = {
                active: document.querySelector('.bulk-edit-controls')
            };
            
            // حذف control panelهای null
            Object.keys(this.controlPanels).forEach(key => {
                if (!this.controlPanels[key]) {
                    delete this.controlPanels[key];
                }
            });
            
            this.updateAllControlPanels();
        }
    }

    detectActiveTab() {
        // تشخیص تب فعال بر اساس نمایش عناصر
        const activeContent = document.getElementById('activeContent');
        const pendingContent = document.getElementById('pendingContent');  
        const archivedContent = document.getElementById('archivedContent');
        
        // بررسی کدام بخش نمایش داده می‌شود
        const activeVisible = activeContent && getComputedStyle(activeContent).display !== 'none';
        const pendingVisible = pendingContent && getComputedStyle(pendingContent).display !== 'none';
        const archivedVisible = archivedContent && getComputedStyle(archivedContent).display !== 'none';
        
        console.log(`🔍 وضعیت بخش‌ها: active=${activeVisible}, pending=${pendingVisible}, archived=${archivedVisible}`);
        
        if (pendingVisible) return 'pending';
        if (archivedVisible) return 'archived';
        if (activeVisible) return 'active';
        
        // اگر هیچ کدام نمایش داده نمی‌شود، active را پیش‌فرض در نظر بگیر
        return 'active';
    }
    
    detectCurrentSection() {
        const previousSection = this.currentSection;
        this.currentActiveTab = this.detectActiveTab();
        this.currentSection = this.currentActiveTab;
        
        console.log(`📍 تشخیص بخش: ${previousSection} → ${this.currentSection}`);
        
        // بررسی وجود جداول مورد نظر
        const tableSelectors = {
            active: '#activePurchasesTable',
            pending: '#pendingPurchasesTable', 
            archived: '#archivedPurchasesTable'
        };
        
        Object.keys(tableSelectors).forEach(section => {
            const table = document.querySelector(tableSelectors[section]);
            console.log(`  ${section}: ${table ? '✅ موجود' : '❌ نامعلوم'}`);
        });
    }

    attachEventListeners() {
        // گوش دادن به تغییرات انتخاب سطرها
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox')) {
                this.handleRowSelection(e.target);
            } else if (e.target.classList.contains('select-all-checkbox') || 
                      e.target.classList.contains('select-all-checkbox-archived') ||
                      e.target.classList.contains('select-all-checkbox-pending')) {
                this.handleSelectAll(e.target);
            }
        });

        document.addEventListener('click', (e) => {
            // دکمه‌های ویرایش گروهی
            if (e.target.classList.contains('bulk-edit-btn') || 
                e.target.closest('.bulk-edit-btn')) {
                const section = e.target.dataset.section || e.target.closest('.bulk-edit-btn').dataset.section;
                this.openBulkEditPage(section);
            } else if (e.target.classList.contains('bulk-edit-excel-btn') || 
                      e.target.closest('.bulk-edit-excel-btn')) {
                const section = e.target.dataset.section || e.target.closest('.bulk-edit-excel-btn').dataset.section;
                this.openExcelEditPage(section);
            } else if (e.target.classList.contains('download-template-btn') || 
                      e.target.closest('.download-template-btn')) {
                const section = e.target.dataset.section || e.target.closest('.download-template-btn').dataset.section;
                this.downloadTemplate(section);
            } else if (e.target.classList.contains('clear-selection-btn') || 
                      e.target.closest('.clear-selection-btn')) {
                const section = e.target.dataset.section || e.target.closest('.clear-selection-btn').dataset.section;
                this.clearSelection(section);
            }

            // دکمه‌های toggle section (purchase-toggle)
            if (e.target.closest('.purchase-toggle') || e.target.closest('.nav-link')) {
                setTimeout(() => {
                    this.detectCurrentSection();
                    this.updateAllControlPanels();
                }, 200); // زمان بیشتر برای انیمیشن
            }
        });
        
        // گوش دادن به رویداد فیلتر جدول
        document.addEventListener('tableFilterApplied', (e) => {
            console.log('🔄 فیلتر جدول اعمال شد، بروزرسانی panel کنترل...');
            this.detectCurrentSection();
            this.updateAllControlPanels();
        });
    }

    handleRowSelection(checkbox) {
        const id = checkbox.dataset.id;
        
        if (checkbox.checked) {
            this.selectedIds.add(id);
            console.log(`✅ انتخاب سطر: ${id}`);
        } else {
            this.selectedIds.delete(id);
            console.log(`❌ حذف انتخاب سطر: ${id}`);
        }
        
        // همگام‌سازی با آمار تجمعی اگر موجود باشد
        if (window.purchaseAggregatedStats) {
            if (checkbox.checked) {
                window.purchaseAggregatedStats.selectedPurchases.add(id);
            } else {
                window.purchaseAggregatedStats.selectedPurchases.delete(id);
            }
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }
        
        // اضافه کردن یا حذف کلاس selected از سطر
        const row = checkbox.closest('tr');
        if (row) {
            if (checkbox.checked) {
                row.classList.add('selected');
                row.classList.add('bulk-selected');
            } else {
                row.classList.remove('selected');
                row.classList.remove('bulk-selected');
            }
        }
        
        this.updateAllControlPanels();
    }

    handleSelectAll(checkbox) {
        const isChecked = checkbox.checked;
        const tableType = this.detectTableType();
        let checkboxes = [];
        
        // تشخیص نوع checkbox و یافتن checkboxهای مربوطه
        if (tableType === 'barnameh') {
            checkboxes = document.querySelectorAll('#barnamehTable .row-checkbox');
        } else if (tableType === 'non_bazargah_purchase') {
            checkboxes = document.querySelectorAll('#purchasesTable .row-checkbox');
        } else if (tableType === 'non_bazargah_barnameh') {
            checkboxes = document.querySelectorAll('#barnamehsTable .row-checkbox');
        } else if (tableType === 'cargo_product') {
            if (checkbox.classList.contains('select-all-checkbox-archived')) {
                checkboxes = document.querySelectorAll('#inactiveProductsTable .row-checkbox');
            } else {
                checkboxes = document.querySelectorAll('#activeProductsTable .row-checkbox');
            }
        } else if (tableType === 'vared_konandeh') {
            checkboxes = document.querySelectorAll('#varedKonandeTable .row-checkbox');
        } else if (tableType === 'barbary') {
            checkboxes = document.querySelectorAll('#barbariesTable .row-checkbox');
        } else {
            if (checkbox.classList.contains('select-all-checkbox-pending')) {
                checkboxes = document.querySelectorAll('#pendingPurchasesTable .row-checkbox');
            } else if (checkbox.classList.contains('select-all-checkbox-archived')) {
                checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
            } else {
                checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
            }
        }
        
        checkboxes.forEach(cb => {
            cb.checked = isChecked;
            const id = cb.dataset.id;
            
            if (isChecked) {
                this.selectedIds.add(id);
            } else {
                this.selectedIds.delete(id);
            }
            
            // اضافه کردن یا حذف کلاس selected از سطر
            const row = cb.closest('tr');
            if (row) {
                if (isChecked) {
                    row.classList.add('selected');
                    row.classList.add('bulk-selected');
                } else {
                    row.classList.remove('selected');
                    row.classList.remove('bulk-selected');
                }
            }
        });

        // همگام‌سازی با آمار تجمعی
        if (window.purchaseAggregatedStats) {
            if (isChecked) {
                checkboxes.forEach(cb => {
                    window.purchaseAggregatedStats.selectedPurchases.add(cb.dataset.id);
                });
            } else {
                checkboxes.forEach(cb => {
                    window.purchaseAggregatedStats.selectedPurchases.delete(cb.dataset.id);
                });
            }
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }

        this.updateAllControlPanels();
    }

    updateAllControlPanels() {
        // بروزرسانی همه control panelها
        Object.keys(this.controlPanels).forEach(section => {
            this.updateControlPanel(section);
        });
    }
    
    updateControlPanel(section = null) {
        const targetSection = section || this.currentSection;
        const panel = this.controlPanels[targetSection];
        const tableType = this.detectTableType();
        
        if (!panel) return;
        
        // محاسبه تعداد انتخاب‌های مربوط به این بخش
        let sectionCount = 0;
        let tableSelector = '';
        
        if (tableType === 'barnameh') {
            tableSelector = '#barnamehTable .row-checkbox:checked';
        } else if (tableType === 'non_bazargah_purchase') {
            tableSelector = '#purchasesTable .row-checkbox:checked';
        } else if (tableType === 'non_bazargah_barnameh') {
            tableSelector = '#barnamehsTable .row-checkbox:checked';
        } else if (tableType === 'cargo_product') {
            switch(targetSection) {
                case 'archived':
                    tableSelector = '#inactiveProductsTable .row-checkbox:checked';
                    break;
                default:
                    tableSelector = '#activeProductsTable .row-checkbox:checked';
            }
        } else if (tableType === 'vared_konandeh') {
            tableSelector = '#varedKonandeTable .row-checkbox:checked';
        } else if (tableType === 'barbary') {
            tableSelector = '#barbariesTable .row-checkbox:checked';
        } else {
            switch(targetSection) {
                case 'pending':
                    tableSelector = '#pendingPurchasesTable .row-checkbox:checked';
                    break;
                case 'archived':
                    tableSelector = '#archivedPurchasesTable .row-checkbox:checked';
                    break;
                default:
                    tableSelector = '#activePurchasesTable .row-checkbox:checked';
            }
        }
        
        sectionCount = document.querySelectorAll(tableSelector).length;
        
        const countElement = panel.querySelector('.count');
            if (countElement) {
            countElement.textContent = sectionCount;
        }
        
        // نمایش/مخفی کردن panel بر اساس انتخاب‌ها و وضعیت بخش
        let isSectionVisible = true;
        
        if (tableType === 'cargo_product') {
            // برای صفحه کوتاژها، بررسی وضعیت نمایش
            if (targetSection === 'archived') {
                const details = document.querySelector('details.dropdown-container');
                isSectionVisible = details && details.hasAttribute('open');
            }
        } else if (tableType === 'non_bazargah_purchase' || tableType === 'non_bazargah_barnameh' || tableType === 'vared_konandeh' || tableType === 'barbary') {
            // برای خریدهای خارج بازارگاه، بارنامه‌های خارج بازارگاه، واردکنندگان و باربری‌ها، همیشه نمایان هستند
            isSectionVisible = true;
        } else {
            const sectionElement = document.getElementById(`${targetSection}Content`);
            isSectionVisible = sectionElement && getComputedStyle(sectionElement).display !== 'none';
        }
        
        const shouldShow = sectionCount > 0 && isSectionVisible;
        panel.style.display = shouldShow ? 'block' : 'none';
        
        console.log(`📊 Panel ${targetSection}: ${sectionCount} انتخاب، بخش نمایان: ${isSectionVisible}, نمایش: ${shouldShow}`);
    }

    // متدهای کمکی
    hasActiveFilters() {
        // بررسی وجود فیلتر فعال
        return document.querySelector('.active-filters-summary.show') !== null ||
               document.querySelector('.filter-dropdown-btn.has-filters') !== null;
    }

    getVisibleRowsCount(table = null) {
        if (table) {
            return table.querySelectorAll('tbody tr:not([style*="display: none"])').length;
        }
        
        let count = 0;
        this.tables.forEach(table => {
            count += table.querySelectorAll('tbody tr:not([style*="display: none"])').length;
        });
        return count;
    }

    getAllRowsCount(table = null) {
        if (table) {
            return table.querySelectorAll('tbody tr').length;
        }
        
        let count = 0;
        this.tables.forEach(table => {
            count += table.querySelectorAll('tbody tr').length;
        });
        return count;
    }

    detectTableType() {
        const url = window.location.pathname;
        if (url.includes('cargo-product') || url.includes('cargo_product')) {
            return 'cargo_product';
        } else if (url.includes('non-bazargah-purchase') || url.includes('non_bazargah_purchase')) {
            return 'non_bazargah_purchase';
        } else if (url.includes('non-bazargah-barnameh') || url.includes('non_bazargah_barnameh')) {
            return 'non_bazargah_barnameh';
        } else if (url.includes('purchase')) {
            return 'purchase';
        } else if (url.includes('customer')) {
            return 'customer';
        } else if (url.includes('barnameh') || url.includes('bki_barnameh')) {
            return 'barnameh';
        } else if (url.includes('vared_konandeh') || url.includes('vared-konandeh')) {
            return 'vared_konandeh';
        } else if (url.includes('barbary') || url.includes('barbaries')) {
            return 'barbary';
        }
        return 'purchase'; // پیش‌فرض
    }

    openBulkEditPage(section = null) {
        const targetSection = section || this.currentSection;
        let selectedIds = [];
        const tableType = this.detectTableType();
        
        console.log(`🎯 درخواست ویرایش گروهی برای بخش: ${targetSection}, نوع: ${tableType}`);
        
        // استفاده از selectedPurchases Set اگر موجود باشد (برای انتخاب همه در بخش)
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases.size > 0) {
            selectedIds = Array.from(window.purchaseAggregatedStats.selectedPurchases);
            console.log(`📋 استفاده از selectedPurchases Set: ${selectedIds.length} مورد`);
        } else {
            // جمع‌آوری آیدی‌های انتخاب شده از checkbox های صفحه فعلی
            let tableMap = {};
            
            if (tableType === 'barnameh') {
                // برای صفحه بارنامه‌ها
                tableMap = {
                    active: '#barnamehTable .row-checkbox:checked',
                    pending: '#barnamehTable .row-checkbox:checked',
                    archived: '#barnamehTable .row-checkbox:checked'
                };
            } else if (tableType === 'non_bazargah_purchase') {
                // برای صفحه خریدهای خارج بازارگاه
                tableMap = {
                    active: '#purchasesTable .row-checkbox:checked',
                    pending: '#purchasesTable .row-checkbox:checked',
                    archived: '#purchasesTable .row-checkbox:checked'
                };
            } else if (tableType === 'cargo_product') {
                // برای صفحه کوتاژها
                tableMap = {
                    active: '#activeProductsTable .row-checkbox:checked',
                    archived: '#inactiveProductsTable .row-checkbox:checked'
                };
            } else if (tableType === 'vared_konandeh') {
                // برای صفحه واردکنندگان
                tableMap = {
                    active: '#varedKonandeTable .row-checkbox:checked'
                };
            } else if (tableType === 'barbary') {
                // برای صفحه باربری‌ها
                tableMap = {
                    active: '#barbariesTable .row-checkbox:checked'
                };
            } else {
                // برای صفحه خریدها
                tableMap = {
                    pending: '#pendingPurchasesTable .row-checkbox:checked',
                    archived: '#archivedPurchasesTable .row-checkbox:checked',
                    active: '#activePurchasesTable .row-checkbox:checked'
                };
            }
            
            const selector = tableMap[targetSection] || '#barnamehTable .row-checkbox:checked';
            console.log(`🔍 انتخاب checkboxها با selector: ${selector}`);
            
            const checkboxes = document.querySelectorAll(selector);
            console.log(`📋 تعداد checkbox های انتخاب شده: ${checkboxes.length}`);
            
            selectedIds = Array.from(checkboxes).map(cb => {
                console.log(`  - ID: ${cb.dataset.id}, Value: ${cb.value}`);
                return cb.dataset.id || cb.value;
            });
        }
        
        console.log(`✅ آیدی‌های جمع‌آوری شده:`, selectedIds);
        
        if (selectedIds.length === 0) {
            console.error('❌ هیچ موردی انتخاب نشده');
            alert('لطفاً حداقل یک مورد انتخاب کنید');
            return;
        }
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = this.config.bulkEditPageUrl;

        const data = {
            'selected_ids': selectedIds,
            'app_name': this.getAppName(tableType),
            'model_name': this.getModelName(tableType),
            'section': targetSection
        };
        
        Object.keys(data).forEach(key => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            if (Array.isArray(data[key])) {
                input.value = JSON.stringify(data[key]);
            } else {
                input.value = data[key];
            }
            form.appendChild(input);
        });

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCSRFToken();
        form.appendChild(csrfInput);
        
        document.body.appendChild(form);
        form.submit();
    }

    openExcelEditPage(section = null) {
        const targetSection = section || this.currentSection;
        let selectedIds = [];
        const tableType = this.detectTableType();
        
        console.log(`📊 درخواست ویرایش اکسلی برای بخش: ${targetSection}, نوع: ${tableType}`);
        
        // استفاده از selectedPurchases Set اگر موجود باشد (برای انتخاب همه در بخش)
        if (window.purchaseAggregatedStats && window.purchaseAggregatedStats.selectedPurchases.size > 0) {
            selectedIds = Array.from(window.purchaseAggregatedStats.selectedPurchases);
            console.log(`📋 استفاده از selectedPurchases Set: ${selectedIds.length} مورد`);
        } else {
            // جمع‌آوری آیدی‌های انتخاب شده از checkbox های صفحه فعلی
            let tableMap = {};
            
            if (tableType === 'barnameh') {
                // برای صفحه بارنامه‌ها
                tableMap = {
                    active: '#barnamehTable .row-checkbox:checked',
                    pending: '#barnamehTable .row-checkbox:checked',
                    archived: '#barnamehTable .row-checkbox:checked'
                };
            } else if (tableType === 'non_bazargah_purchase') {
                // برای صفحه خریدهای خارج بازارگاه
                tableMap = {
                    active: '#purchasesTable .row-checkbox:checked',
                    pending: '#purchasesTable .row-checkbox:checked',
                    archived: '#purchasesTable .row-checkbox:checked'
                };
            } else if (tableType === 'cargo_product') {
                // برای صفحه کوتاژها
                tableMap = {
                    active: '#activeProductsTable .row-checkbox:checked',
                    archived: '#inactiveProductsTable .row-checkbox:checked'
                };
            } else if (tableType === 'vared_konandeh') {
                // برای صفحه واردکنندگان
                tableMap = {
                    active: '#varedKonandeTable .row-checkbox:checked'
                };
            } else if (tableType === 'barbary') {
                // برای صفحه باربری‌ها
                tableMap = {
                    active: '#barbariesTable .row-checkbox:checked'
                };
            } else {
                // برای صفحه خریدها
                tableMap = {
                    pending: '#pendingPurchasesTable .row-checkbox:checked',
                    archived: '#archivedPurchasesTable .row-checkbox:checked',
                    active: '#activePurchasesTable .row-checkbox:checked'
                };
            }
            
            const selector = tableMap[targetSection] || '#barnamehTable .row-checkbox:checked';
            console.log(`🔍 انتخاب checkboxها با selector: ${selector}`);
            
            const checkboxes = document.querySelectorAll(selector);
            console.log(`📋 تعداد checkbox های انتخاب شده: ${checkboxes.length}`);
            
            selectedIds = Array.from(checkboxes).map(cb => {
                console.log(`  - ID: ${cb.dataset.id}, Value: ${cb.value}`);
                return cb.dataset.id || cb.value;
            });
        }
        
        console.log(`✅ آیدی‌های جمع‌آوری شده:`, selectedIds);
        
        if (selectedIds.length === 0) {
            console.error('❌ هیچ موردی انتخاب نشده');
            alert('لطفاً حداقل یک مورد انتخاب کنید');
            return;
        }
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = this.config.excelEditPageUrl;

        const data = {
            'selected_ids': selectedIds,
            'app_name': this.getAppName(tableType),
            'model_name': this.getModelName(tableType),
            'section': targetSection
        };

        Object.keys(data).forEach(key => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            if (Array.isArray(data[key])) {
                input.value = JSON.stringify(data[key]);
            } else {
                input.value = data[key];
            }
            form.appendChild(input);
        });

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCSRFToken();
        form.appendChild(csrfInput);
        
        document.body.appendChild(form);
        form.submit();
    }

    downloadTemplate(section = null) {
        const tableType = this.detectTableType();
        const url = `${this.config.downloadTemplateUrl}?app_name=${this.getAppName(tableType)}&model_name=${this.getModelName(tableType)}`;
        
        window.open(url, '_blank');
    }

    getModelName(tableType) {
        const modelMap = {
            'purchase': 'Purchase',
            'customer': 'Customer',
            'cargo_product': 'CargoProduct',
            'barnameh': 'Barnameh',
            'non_bazargah_purchase': 'NonBazargahPurchase'
        };
        return modelMap[tableType] || 'Purchase';
    }
    
    getAppName(tableType) {
        const appMap = {
            'purchase': 'core',
            'customer': 'core',
            'cargo_product': 'core',
            'barnameh': 'bki_barnameh',
            'non_bazargah_purchase': 'major'
        };
        return appMap[tableType] || 'core';
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    showToast(message, type = 'info') {
        // ایجاد toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast-notification`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideIn 0.3s ease-out;
        `;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : type === 'warning' ? 'exclamation' : 'info'}-circle me-2"></i>
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;

        document.body.appendChild(toast);

        // حذف خودکار بعد از 5 ثانیه
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }

    clearSelection(section = null) {
        const targetSection = section || this.currentSection;
        const tableType = this.detectTableType();
        let checkboxes = [];
        
        // یافتن checkboxهای مربوط به بخش
        if (tableType === 'barnameh') {
            checkboxes = document.querySelectorAll('#barnamehTable .row-checkbox');
        } else if (tableType === 'non_bazargah_purchase') {
            checkboxes = document.querySelectorAll('#purchasesTable .row-checkbox');
        } else if (tableType === 'cargo_product') {
            if (targetSection === 'archived') {
                checkboxes = document.querySelectorAll('#inactiveProductsTable .row-checkbox');
            } else {
                checkboxes = document.querySelectorAll('#activeProductsTable .row-checkbox');
            }
        } else if (tableType === 'vared_konandeh') {
            checkboxes = document.querySelectorAll('#varedKonandeTable .row-checkbox');
        } else if (tableType === 'barbary') {
            checkboxes = document.querySelectorAll('#barbariesTable .row-checkbox');
        } else {
            switch(targetSection) {
                case 'pending':
                    checkboxes = document.querySelectorAll('#pendingPurchasesTable .row-checkbox');
                    break;
                case 'archived':
                    checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
                    break;
                default:
                    checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
            }
        }
        
        // پاک کردن انتخاب‌ها
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            const id = checkbox.dataset.id;
            this.selectedIds.delete(id);
            
            // حذف کلاس selected از سطر
            const row = checkbox.closest('tr');
            if (row) {
                row.classList.remove('selected');
                row.classList.remove('bulk-selected');
            }
        });
        
        // پاک کردن select all checkbox
        const selectAllMap = {
            pending: '.select-all-checkbox-pending',
            archived: '.select-all-checkbox-archived',
            active: '.select-all-checkbox'
        };
        
        const selectAllCheckbox = document.querySelector(selectAllMap[targetSection]);
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        // برای خریدهای خارج بازارگاه، select all checkbox را پاک کن
        if (tableType === 'non_bazargah_purchase') {
            const selectAllCheckbox = document.querySelector('.select-all-checkbox');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
        }
        
        // همگام‌سازی با آمار تجمعی
        if (window.purchaseAggregatedStats) {
            checkboxes.forEach(checkbox => {
                window.purchaseAggregatedStats.selectedPurchases.delete(checkbox.dataset.id);
            });
            window.purchaseAggregatedStats.updateSelectedPurchases();
        }
        
        this.updateAllControlPanels();
    }
}

// استایل برای انیمیشن toast
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .toast-notification {
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 0.375rem;
    }
    
    .toast-notification .btn-close {
        background: transparent;
        border: none;
        font-size: 1.2rem;
        margin-left: 10px;
        cursor: pointer;
    }
    
    .select-all-modal .btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s;
    }
    
    .select-all-modal .btn-primary {
        background: #007bff;
        color: white;
    }
    
    .select-all-modal .btn-success {
        background: #28a745;
        color: white;
    }
    
    .select-all-modal .btn-secondary {
        background: #6c757d;
        color: white;
    }
    
    .select-all-modal .btn:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
`;
document.head.appendChild(style);

// ایجاد instance global
window.bulkEditManager = new BulkEditManager();

// راه‌اندازی خودکار
document.addEventListener('DOMContentLoaded', function() {
    if (window.bulkEditManager) {
        window.bulkEditManager.init();
    }
});

// Export برای استفاده در سایر فایل‌ها
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BulkEditManager;
} 