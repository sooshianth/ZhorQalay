document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');
    
    // Initialize table filter first
    const tableFilter = new TableFilter({
        tableSelector: '.enable-filter',
        enableToast: true,
        enableIndicators: true,
        enableSummary: true,
        enableClearAll: true,
        autoDetectColumns: true
    });
    tableFilter.init();
    console.log('Table filter initialized');
    
    // Initialize columns management
    initializeColumnManagement();
    

    
    // Initialize the bulk edit manager
    let bulkEditManager;
    
    // Wait for BulkEditManager to be loaded
    function initBulkEdit() {
        if (typeof BulkEditManager !== 'undefined') {
            bulkEditManager = new BulkEditManager({
                tableSelector: '.enable-filter',
                bulkEditPageUrl: '/table_filter/bulk_edit_page/',
                excelEditPageUrl: '/table_filter/bulk_edit_excel_page/',
                downloadTemplateUrl: '/table_filter/bulk_edit_template/'
            });
            
            // اضافه کردن امکان تشخیص نوع جدول برای customer
            bulkEditManager.detectTableType = function() {
                const url = window.location.pathname;
                if (url.includes('customer')) {
                    return 'customer';
                }
                return 'generic';
            };
            
            // اضافه کردن نگاشت مدل برای customer
            bulkEditManager.getModelName = function(tableType) {
                const modelMap = {
                    'customer': 'Customer'
                };
                return modelMap[tableType] || 'Customer';
            };
            
            // تنظیم اپلیکیشن مدل
            bulkEditManager.getAppName = function(tableType) {
                return 'core';
            };
            
            bulkEditManager.init();
            console.log('✅ Bulk edit manager initialized successfully');
        } else {
            console.log('⏳ BulkEditManager not loaded yet, retrying...');
            setTimeout(initBulkEdit, 500);
        }
    }
    
    // Start bulk edit initialization
    initBulkEdit();

    // Real-time search functionality
    let searchTimeout;
    const realTimeSearchInput = document.getElementById('real-time-search');
    const searchLoadingIcon = document.getElementById('search-loading');
    let lastSearchValue = realTimeSearchInput?.value || '';

    function performRealTimeSearch(searchValue) {
        // نمایش loading
        if (searchLoadingIcon) {
            searchLoadingIcon.classList.remove('hidden');
        }

        // فیلتر کردن سطرهای جدول
        const tableRows = document.querySelectorAll('tbody tr');
        let visibleCount = 0;

        tableRows.forEach(row => {
            const nameCell = row.querySelector('.column-name a');
            const phoneCell = row.querySelector('.column-phone');
            
            if (nameCell && phoneCell) {
                const name = nameCell.textContent.toLowerCase();
                const phone = phoneCell.textContent.toLowerCase();
                const searchLower = searchValue.toLowerCase();
                
                // حذف کاراکترهای غیرعددی از شماره تلفن برای جستجوی بهتر
                const cleanPhone = phone.replace(/[^\d]/g, '');
                const cleanSearch = searchValue.replace(/[^\d]/g, '');
                
                const matches = name.includes(searchLower) || 
                               phone.includes(searchLower) ||
                               (cleanSearch && cleanPhone.includes(cleanSearch));
                
                if (matches) {
                    row.style.display = '';
                    visibleCount++;
                    // اضافه کردن انیمیشن نمایش
                    row.style.animation = 'fadeIn 0.3s ease-in-out';
                } else {
                    row.style.display = 'none';
                }
            }
        });

        // بروزرسانی تعداد نتایج
        updateResultCount(visibleCount);

        // مخفی کردن loading بعد از 300ms
        setTimeout(() => {
            if (searchLoadingIcon) {
                searchLoadingIcon.classList.add('hidden');
            }
        }, 300);
    }

    function updateResultCount(count) {
        const resultElement = document.querySelector('.tag span.font-bold');
        if (resultElement) {
            resultElement.textContent = count.toLocaleString('fa-IR');
        }
    }

    // Event listener برای جستجوی real-time
    if (realTimeSearchInput) {
        realTimeSearchInput.addEventListener('input', function() {
            const searchValue = this.value.trim();
            
            // Clear previous timeout
            clearTimeout(searchTimeout);
            
            // اگر مقدار تغییر نکرده باشد، هیچکاری نکن
            if (searchValue === lastSearchValue) {
                return;
            }
            
            lastSearchValue = searchValue;
            
            // Set new timeout برای کاهش تعداد درخواست‌ها
            searchTimeout = setTimeout(() => {
                performRealTimeSearch(searchValue);
            }, 300); // 300ms delay
        });
        
        // اجرای جستجوی اولیه اگر مقدار پیش‌فرض وجود دارد
        if (realTimeSearchInput.value.trim()) {
            performRealTimeSearch(realTimeSearchInput.value.trim());
        }
    }

    // مدیریت فیلتر پیشرفته
    const toggleFiltersBtn = document.getElementById('toggle-filters-btn');
    const filtersContainer = document.getElementById('filters-container');
    const closeFiltersBtn = document.getElementById('close-filters');
    const resetFiltersBtn = document.getElementById('reset-filters');

    console.log('Toggle button:', toggleFiltersBtn);
    console.log('Filters container:', filtersContainer);

    // نمایش/مخفی کردن فیلتر پیشرفته
    if (toggleFiltersBtn && filtersContainer) {
        console.log('Setting up filter toggle');
        
        toggleFiltersBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Filter button clicked');
            
            // Toggle نمایش فیلتر
            if (filtersContainer.classList.contains('hidden')) {
                filtersContainer.classList.remove('hidden');
                this.innerHTML = '<i class="fas fa-times me-2"></i>بستن فیلترها';
                this.classList.remove('btn-secondary');
                this.classList.add('btn-info');
            } else {
                filtersContainer.classList.add('hidden');
                this.innerHTML = '<i class="fas fa-filter me-2"></i>فیلترهای پیشرفته';
                this.classList.remove('btn-info');
                this.classList.add('btn-secondary');
            }
        });
    } else {
        console.error('Toggle button or filters container not found!', {
            toggleBtn: toggleFiltersBtn,
            container: filtersContainer
        });
    }

    // بستن فیلتر از داخل خودش
    if (closeFiltersBtn && filtersContainer && toggleFiltersBtn) {
        closeFiltersBtn.addEventListener('click', function() {
            filtersContainer.classList.add('hidden');
            toggleFiltersBtn.innerHTML = '<i class="fas fa-filter me-2"></i>فیلترهای پیشرفته';
            toggleFiltersBtn.classList.remove('btn-info');
            toggleFiltersBtn.classList.add('btn-secondary');
        });
    }

    // پاک کردن فیلترها
    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', function() {
            // پاک کردن همه فیلدهای فرم
            const filterForm = document.getElementById('filter-form');
            if (filterForm) {
                // پاک کردن input ها
                const inputs = filterForm.querySelectorAll('input[type="text"], input[type="number"]');
                inputs.forEach(input => {
                    input.value = '';
                });
                
                // پاک کردن checkbox ها
                const checkboxes = filterForm.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = false;
                });
                
                // پاک کردن select ها
                const selects = filterForm.querySelectorAll('select');
                selects.forEach(select => {
                    if (select.multiple) {
                        // برای select های چندگانه
                        Array.from(select.options).forEach(option => {
                            option.selected = false;
                        });
                    } else {
                        // برای select های تکی
                        select.selectedIndex = 0;
                    }
                });
                
                // بازگشت به صفحه بدون فیلتر
                window.location.href = '/sales/customers/';
            }
        });
    }

    // تغییر وضعیت علاقه‌مندی
    var favoriteIcons = document.querySelectorAll('.favorite-icon');
    console.log('Found ' + favoriteIcons.length + ' favorite icons');
    
    favoriteIcons.forEach(function(icon) {
        icon.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            var customerId = this.getAttribute('data-customer-id');
            console.log('Favorite icon clicked for customer ID:', customerId);
            toggleFavorite(customerId, this);
        });
    });
});

// تابع تغییر وضعیت علاقه‌مندی
function toggleFavorite(customerId, iconElement) {
    if (!customerId) {
        console.error('شناسه مشتری یافت نشد');
        return;
    }
    
    console.log('Toggling favorite for customer ID:', customerId);
    
    // یافتن توکن CSRF
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    if (!csrfToken) {
        console.error('CSRF token not found');
        return;
    }
    
    // نمایش لودینگ روی آیکون
    var originalHTML = iconElement.innerHTML;
    iconElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    // ساخت داده‌های فرم
    var formData = new FormData();
    formData.append('customer_id', customerId);
    
    // ارسال درخواست
    fetch('/sales/toggle_favorite/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(function(response) {
        console.log('Response status:', response.status);
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.status);
        }
        return response.json();
    })
    .then(function(data) {
        console.log('Response data:', data);
        
        if (data.success) {
            // تغییر آیکون بر اساس وضعیت جدید
            if (data.is_favorite) {
                iconElement.innerHTML = '<i class="fas fa-star text-yellow-500"></i>';
                iconElement.setAttribute('data-is-favorite', 'true');
            } else {
                iconElement.innerHTML = '<i class="far fa-star"></i>';
                iconElement.setAttribute('data-is-favorite', 'false');
            }
            
            // نمایش پیام موفقیت
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'موفق',
                    text: data.message,
                    showConfirmButton: false,
                    timer: 1500
                });
            }
        } else {
            // بازگرداندن آیکون به حالت قبلی در صورت خطا
            iconElement.innerHTML = originalHTML;
            
            // نمایش پیام خطا
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'خطا',
                    text: data.error || 'خطایی رخ داد',
                });
            }
        }
    })
    .catch(function(error) {
        // بازگرداندن آیکون به حالت قبلی در صورت خطا
        iconElement.innerHTML = originalHTML;
        
        console.error('خطا در ارسال درخواست:', error);
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'error',
                title: 'خطا',
                text: 'خطایی در ارتباط با سرور رخ داد: ' + error.message,
            });
        }
    });
}

// نمایش وضعیت جاوااسکریپت
var jsStatus = document.getElementById('js-status');
if (jsStatus) {
    jsStatus.classList.remove('hidden');
    setTimeout(function() {
        jsStatus.classList.add('hidden');
    }, 3000);
}

// انتخاب همه
var selectAllBtn = document.getElementById('select-all-btn');
if (selectAllBtn) {
    selectAllBtn.addEventListener('click', function() {
        var checkboxes = document.querySelectorAll('.row-checkbox');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = true;
            checkbox.closest('tr').classList.add('selected-row');
        });
        updateSelectionCount();
    });
}

// لغو انتخاب همه
var deselectAllBtn = document.getElementById('deselect-all-btn');
if (deselectAllBtn) {
    deselectAllBtn.addEventListener('click', function() {
        var checkboxes = document.querySelectorAll('.row-checkbox');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = false;
            checkbox.closest('tr').classList.remove('selected-row');
        });
        updateSelectionCount();
    });
}

// انتخاب همه در هدر جدول
var selectAllCheckbox = document.getElementById('select-all-checkbox');
if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function() {
        var checkboxes = document.querySelectorAll('.row-checkbox');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = this.checked;
            if (this.checked) {
                checkbox.closest('tr').classList.add('selected-row');
            } else {
                checkbox.closest('tr').classList.remove('selected-row');
            }
        });
        updateSelectionCount();
    });
}

// محاسبه تعداد انتخاب‌ها
function updateSelectionCount() {
    var count = document.querySelectorAll('.row-checkbox:checked').length;
    var sendSmsBtn = document.getElementById('send-sms-btn');
    if (sendSmsBtn) {
        sendSmsBtn.disabled = count === 0;
    }
    var selectedCount = document.getElementById('selected-count');
    if (selectedCount) {
        selectedCount.textContent = count;
    }
}

// اضافه کردن event listener به تمام چک‌باکس‌ها
var customerCheckboxes = document.querySelectorAll('.row-checkbox');
customerCheckboxes.forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
        console.log('Checkbox changed');
        if (this.checked) {
            this.closest('tr').classList.add('selected-row');
        } else {
            this.closest('tr').classList.remove('selected-row');
        }
        updateSelectionCount();
    });
});

// راه‌اندازی checkbox های انتخاب همه و سطرها
function initializeTableCheckboxes() {
    console.log('Initializing table checkboxes...');
    
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');
    
    console.log('Select all checkbox:', selectAllCheckbox);
    console.log('Row checkboxes found:', rowCheckboxes.length);
    
    // Event listener برای checkbox انتخاب همه
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function(e) {
            e.stopPropagation();
            const isChecked = this.checked;
            console.log('Select all clicked:', isChecked);
            
            // انتخاب/لغو انتخاب همه سطرها
            rowCheckboxes.forEach(checkbox => {
                if (checkbox.checked !== isChecked) {
                    checkbox.checked = isChecked;
                    // Add/remove selected row class
                    const row = checkbox.closest('tr');
                    if (row) {
                        if (isChecked) {
                            row.classList.add('selected-row');
                        } else {
                            row.classList.remove('selected-row');
                        }
                    }
                }
            });
            
            updateSelectionCount();
        });
    }
    
    // Event listener برای checkbox های سطر
    rowCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            e.stopPropagation();
            console.log('Row checkbox changed:', this.checked, 'Customer ID:', this.getAttribute('data-id'));
            
            // Add/remove selected row class
            const row = this.closest('tr');
            if (row) {
                if (this.checked) {
                    row.classList.add('selected-row');
                } else {
                    row.classList.remove('selected-row');
                }
            }
            
            // بررسی وضعیت checkbox انتخاب همه
            if (selectAllCheckbox) {
                const checkedCount = document.querySelectorAll('.row-checkbox:checked').length;
                const totalCount = rowCheckboxes.length;
                
                if (checkedCount === totalCount && totalCount > 0) {
                    selectAllCheckbox.checked = true;
                    selectAllCheckbox.indeterminate = false;
                } else if (checkedCount === 0) {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = false;
                } else {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = true;
                }
            }
            
            updateSelectionCount();
        });
    });
    
    console.log('Table checkboxes initialized successfully');
}

// فراخوانی تابع راه‌اندازی checkbox ها
initializeTableCheckboxes();

// نمایش پنل ارسال پیامک
var sendSmsBtn = document.getElementById('send-sms-btn');
if (sendSmsBtn) {
    sendSmsBtn.addEventListener('click', function() {
        var smsPanel = document.getElementById('sms-panel');
        if (smsPanel) {
            smsPanel.classList.remove('hidden');
        }
    });
}

// بستن پنل پیامک
var closeSmsPanel = document.getElementById('close-sms-panel');
if (closeSmsPanel) {
    closeSmsPanel.addEventListener('click', function() {
        var smsPanel = document.getElementById('sms-panel');
        if (smsPanel) {
            smsPanel.classList.add('hidden');
        }
    });
}

// Column Management functionality
function initializeColumnManagement() {
    console.log('Initializing column management...');
    
    // Load saved column preferences
    loadColumnPreferences();
    
    // Event listeners for column management
    const selectAllBtn = document.getElementById('selectAllColumns');
    const deselectAllBtn = document.getElementById('deselectAllColumns');
    const saveColumnsBtn = document.getElementById('saveColumnsBtn');
    
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function() {
            const checkboxes = document.querySelectorAll('#columnsForm input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    }
    
    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function() {
            const checkboxes = document.querySelectorAll('#columnsForm input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    }
    
    if (saveColumnsBtn) {
        saveColumnsBtn.addEventListener('click', function() {
            saveColumnPreferences();
        });
    }
}

function loadColumnPreferences() {
    // Get saved preferences from localStorage
    const savedColumns = localStorage.getItem('customer_visible_columns');
    
    if (savedColumns) {
        try {
            const columnPreferences = JSON.parse(savedColumns);
            
            // Update checkboxes in modal
            Object.keys(columnPreferences).forEach(columnId => {
                const checkbox = document.getElementById(`col-${columnId}`);
                if (checkbox) {
                    checkbox.checked = columnPreferences[columnId];
                }
            });
            
            // Apply column visibility to table
            applyColumnVisibility(columnPreferences);
        } catch (e) {
            console.error('Error loading column preferences:', e);
        }
    }
}

function saveColumnPreferences() {
    const checkboxes = document.querySelectorAll('#columnsForm input[type="checkbox"]');
    const preferences = {};
    
    checkboxes.forEach(checkbox => {
        const columnId = checkbox.value;
        preferences[columnId] = checkbox.checked;
    });
    
    // Save to localStorage
    localStorage.setItem('customer_visible_columns', JSON.stringify(preferences));
    
    // Apply to table
    applyColumnVisibility(preferences);
    
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('columnsModal'));
    if (modal) {
        modal.hide();
    }
    
    // Show success message
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: 'success',
            title: 'موفق',
            text: 'تنظیمات ستون‌ها ذخیره شد',
            showConfirmButton: false,
            timer: 1500
        });
    } else {
        alert('تنظیمات ستون‌ها ذخیره شد');
    }
}

function applyColumnVisibility(preferences) {
    // Show/hide table columns based on preferences
    Object.keys(preferences).forEach(columnId => {
        const isVisible = preferences[columnId];
        
        // Skip checkbox and favorite columns (always visible)
        if (columnId === 'checkbox' || columnId === 'favorite') {
            return;
        }
        
        // Find all elements with column class
        const columnElements = document.querySelectorAll(`.column-${columnId}`);
        
        columnElements.forEach(element => {
            if (isVisible) {
                element.style.display = '';
                element.classList.remove('d-none');
            } else {
                element.style.display = 'none';
                element.classList.add('d-none');
            }
        });
    });
    
    console.log('Applied column visibility:', preferences);
}

// اضافه کردن انیمیشن برای فیلدهای فیلتر
const filterInputs = document.querySelectorAll('#filters-container input, #filters-container select');
filterInputs.forEach(input => {
    input.addEventListener('focus', function() {
        this.parentElement.style.transform = 'scale(1.02)';
        this.parentElement.style.transition = 'transform 0.2s ease';
    });
    
    input.addEventListener('blur', function() {
        this.parentElement.style.transform = 'scale(1)';
    });
});

// کد مربوط به قالب‌های پیامک و سایر عملکردها را حفظ می‌کنیم
// ...