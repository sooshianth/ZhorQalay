// فایل JavaScript برای عملکرد چک‌باکس انتخاب همه
document.addEventListener('DOMContentLoaded', function() {
    console.log('Select all purchases JS loaded');
    // تابع آپدیت وضعیت چک‌باکس انتخاب همه
    function updateSelectAllCheckbox(tableId, selectAllClass) {
        const checkboxes = document.querySelectorAll(`#${tableId} .row-checkbox`);
        const selectAllCheckbox = document.querySelector(`#${tableId} .${selectAllClass}`);
        
        if (checkboxes.length === 0 || !selectAllCheckbox) return;
        
        const checkedCount = Array.from(checkboxes).filter(checkbox => checkbox.checked).length;
        
        if (checkedCount === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (checkedCount === checkboxes.length) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;  // حالت نیمه انتخاب شده
        }
        
        // بروزرسانی نمایش تعداد انتخاب شده
        updateSelectionIndicator();
    }
    
    // تابع بروزرسانی نمایش تعداد انتخاب شده
    function updateSelectionIndicator() {
        const allCheckboxes = document.querySelectorAll('.row-checkbox');
        const checkedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
        const selectionIndicator = document.getElementById('selectionIndicator');
        const selectionCount = document.getElementById('selectionCount');
        
        if (selectionIndicator && selectionCount) {
            if (checkedCheckboxes.length > 0) {
                selectionCount.textContent = checkedCheckboxes.length;
                selectionIndicator.classList.add('show');
            } else {
                selectionIndicator.classList.remove('show');
            }
        }
    }
    
    // تابع تغییر استایل سطر انتخاب شده
    function updateRowStyle(checkbox) {
        const row = checkbox.closest('tr');
        console.log('updateRowStyle called, row found:', !!row, 'checked:', checkbox.checked);
        if (!row) return;
        
        if (checkbox.checked) {
            row.classList.add('selected-row');
            console.log('Added selected-row class');
        } else {
            row.classList.remove('selected-row');
            console.log('Removed selected-row class');
        }
    }

    // انتخاب همه چک‌باکس‌ها در جدول فعال
    const selectAllActiveCheckbox = document.querySelector('#activePurchasesTable .select-all-checkbox');
    if (selectAllActiveCheckbox) {
        selectAllActiveCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                updateRowStyle(checkbox);
                // تریگر کردن ایونت تغییر برای هر چک‌باکس تا لیست انتخاب‌ها آپدیت شود
                if (typeof window.updateRowCheckboxSelection === 'function') {
                    window.updateRowCheckboxSelection(checkbox);
                }
            });
            updateSelectionIndicator();
        });
    }
    
    // انتخاب همه چک‌باکس‌ها در جدول آرشیو
    const selectAllArchivedCheckbox = document.querySelector('#archivedPurchasesTable .select-all-checkbox-archived');
    if (selectAllArchivedCheckbox) {
        selectAllArchivedCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                updateRowStyle(checkbox);
                // تریگر کردن ایونت تغییر برای هر چک‌باکس تا لیست انتخاب‌ها آپدیت شود
                if (typeof window.updateRowCheckboxSelection === 'function') {
                    window.updateRowCheckboxSelection(checkbox);
                }
            });
            updateSelectionIndicator();
        });
    }
    
    // اضافه کردن رویداد به چک‌باکس‌های ردیف
    const setupRowCheckboxes = function() {
        console.log('Setting up row checkboxes...');
        const checkboxes = document.querySelectorAll('.row-checkbox');
        console.log('Found checkboxes:', checkboxes.length);
        
        checkboxes.forEach(checkbox => {
            // بررسی اینکه آیا قبلاً رویداد به این چک‌باکس اضافه شده است
            if (!checkbox.hasAttribute('data-select-all-initialized')) {
                checkbox.setAttribute('data-select-all-initialized', 'true');
                console.log('Adding event listener to checkbox');
                
                checkbox.addEventListener('change', function() {
                    console.log('Checkbox changed:', this.checked);
                    // تغییر استایل سطر
                    updateRowStyle(this);
                    
                    // به‌روزرسانی وضعیت چک‌باکس انتخاب همه مربوطه
                    if (this.closest('#activePurchasesTable')) {
                        updateSelectAllCheckbox('activePurchasesTable', 'select-all-checkbox');
                    } else if (this.closest('#archivedPurchasesTable')) {
                        updateSelectAllCheckbox('archivedPurchasesTable', 'select-all-checkbox-archived');
                    }
                });
            }
        });
    };
    
    // اجرای اولیه تنظیم چک‌باکس‌ها
    setupRowCheckboxes();
    
    // به‌روزرسانی اولیه وضعیت چک‌باکس‌ها
    updateSelectAllCheckbox('activePurchasesTable', 'select-all-checkbox');
    updateSelectAllCheckbox('archivedPurchasesTable', 'select-all-checkbox-archived');
    
    // بروزرسانی اولیه نمایش انتخاب شده‌ها
    updateSelectionIndicator();
    
    // اعمال استایل اولیه برای سطرهای انتخاب شده
    document.querySelectorAll('.row-checkbox:checked').forEach(checkbox => {
        updateRowStyle(checkbox);
    });
    
    // در صورتی که جدول پس از فیلتر یا تغییر دینامیک آپدیت شود
    document.addEventListener('table-updated', function() {
        setupRowCheckboxes();
        updateSelectAllCheckbox('activePurchasesTable', 'select-all-checkbox');
        updateSelectAllCheckbox('archivedPurchasesTable', 'select-all-checkbox-archived');
        updateSelectionIndicator();
    });
}); 