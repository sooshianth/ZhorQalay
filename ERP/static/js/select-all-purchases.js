// فایل JavaScript برای عملکرد چک‌باکس انتخاب همه
document.addEventListener('DOMContentLoaded', function() {
    // تابع آپدیت وضعیت چک‌باکس انتخاب همه
    function updateSelectAllCheckbox(tableId, selectAllId) {
        const checkboxes = document.querySelectorAll(`#${tableId} .row-checkbox`);
        const selectAllCheckbox = document.getElementById(selectAllId);
        
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
    }

    // انتخاب همه چک‌باکس‌ها در جدول فعال
    const selectAllActiveCheckbox = document.getElementById('selectAllActive');
    if (selectAllActiveCheckbox) {
        selectAllActiveCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('#activePurchasesTable .row-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                // تریگر کردن ایونت تغییر برای هر چک‌باکس تا لیست انتخاب‌ها آپدیت شود
                if (typeof window.updateRowCheckboxSelection === 'function') {
                    window.updateRowCheckboxSelection(checkbox);
                }
            });
        });
    }
    
    // انتخاب همه چک‌باکس‌ها در جدول آرشیو
    const selectAllArchivedCheckbox = document.getElementById('selectAllArchived');
    if (selectAllArchivedCheckbox) {
        selectAllArchivedCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('#archivedPurchasesTable .row-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                // تریگر کردن ایونت تغییر برای هر چک‌باکس تا لیست انتخاب‌ها آپدیت شود
                if (typeof window.updateRowCheckboxSelection === 'function') {
                    window.updateRowCheckboxSelection(checkbox);
                }
            });
        });
    }
    
    // به‌روزرسانی اولیه وضعیت چک‌باکس‌ها
    updateSelectAllCheckbox('activePurchasesTable', 'selectAllActive');
    updateSelectAllCheckbox('archivedPurchasesTable', 'selectAllArchived');
    
    // اضافه کردن رویداد به چک‌باکس‌های ردیف
    const setupRowCheckboxes = function() {
        document.querySelectorAll('#activePurchasesTable .row-checkbox, #archivedPurchasesTable .row-checkbox').forEach(checkbox => {
            // بررسی اینکه آیا قبلاً رویداد به این چک‌باکس اضافه شده است
            if (!checkbox.hasAttribute('data-select-all-initialized')) {
                checkbox.setAttribute('data-select-all-initialized', 'true');
                
                checkbox.addEventListener('change', function() {
                    // به‌روزرسانی وضعیت چک‌باکس انتخاب همه مربوطه
                    if (this.closest('#activePurchasesTable')) {
                        updateSelectAllCheckbox('activePurchasesTable', 'selectAllActive');
                    } else if (this.closest('#archivedPurchasesTable')) {
                        updateSelectAllCheckbox('archivedPurchasesTable', 'selectAllArchived');
                    }
                });
            }
        });
    };
    
    // اجرای اولیه تنظیم چک‌باکس‌ها
    setupRowCheckboxes();
    
    // در صورتی که جدول پس از فیلتر یا تغییر دینامیک آپدیت شود
    document.addEventListener('table-updated', function() {
        setupRowCheckboxes();
        updateSelectAllCheckbox('activePurchasesTable', 'selectAllActive');
        updateSelectAllCheckbox('archivedPurchasesTable', 'selectAllArchived');
    });
}); 