// تابع toggle برای بخش‌ها
function toggleSection(titleElement) {
    const section = titleElement.closest('.form-section');
    const content = section.querySelector('.section-content');
    const toggle = titleElement.querySelector('.section-toggle');
    
    if (content.classList.contains('expanded')) {
        content.classList.remove('expanded');
        content.classList.add('collapsed');
        toggle.classList.add('rotated');
    } else {
        content.classList.remove('collapsed');
        content.classList.add('expanded');
        toggle.classList.remove('rotated');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // تایم‌لاین tooltip
    const steps = document.querySelectorAll(".timeline-item");
    steps.forEach(step => {
        step.addEventListener("mouseenter", function() {
            const info = step.getAttribute("data-step-info");
            step.title = info;
        });
    });
    
    // محاسبه خودکار مبلغ پرداختی
    function calculateTotalAmount() {
        const quantityField = document.querySelector('input[name="quantity"]');
        const customerPriceField = document.querySelector('input[name="customer_price"]');
        const unitField = document.querySelector('select[name="unit"]');
        const bagWeightField = document.querySelector('input[name="bag_weight"]');
        const amountPaidField = document.querySelector('input[name="amount_paid"]');
        
        if (quantityField && customerPriceField && unitField && amountPaidField) {
            const quantity = parseFloat(quantityField.value) || 0;
            const customerPrice = parseFloat(customerPriceField.value) || 0;
            const unit = unitField.value;
            const bagWeight = parseFloat(bagWeightField?.value) || 0;
            
            let quantityInKg = quantity;
            
            if (unit === 'Ton') {
                quantityInKg = quantity * 1000;
            } else if (unit === 'Kiseh' && bagWeight > 0) {
                quantityInKg = quantity * bagWeight;
            }
            
            const totalAmount = quantityInKg * customerPrice;
            
            if (totalAmount > 0) {
                amountPaidField.value = Math.round(totalAmount);
            } else {
                amountPaidField.value = '';
            }
        }
    }
    
    // اتصال رویدادها برای محاسبه خودکار
    const fieldsForCalculation = ['quantity', 'customer_price', 'unit', 'bag_weight'];
    fieldsForCalculation.forEach(fieldName => {
        const field = document.querySelector(`[name="${fieldName}"]`);
        if (field) {
            field.addEventListener('input', calculateTotalAmount);
            field.addEventListener('change', calculateTotalAmount);
        }
    });
    
    calculateTotalAmount();
});

// توابع مدیریت فرم اضافه کردن بارنامه
function showAddBarnamehForm(allocationId) {
    const form = document.getElementById(`add-barnameh-form-${allocationId}`);
    if (form) {
        form.style.display = 'block';
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function hideAddBarnamehForm(allocationId) {
    const form = document.getElementById(`add-barnameh-form-${allocationId}`);
    if (form) {
        form.style.display = 'none';
        const inputs = form.querySelectorAll('input[type="text"], input[type="number"]');
        inputs.forEach(input => {
            input.value = '';
        });
    }
}

// تابع تایید بروزرسانی همه بارنامه‌ها
function confirmUpdateAllBarnamehs() {
    // شمارش تعداد بارنامه‌ها
    const barnamehForms = document.querySelectorAll('.barnameh-form');
    const barnamehCount = barnamehForms.length;
    
    if (barnamehCount === 0) {
        alert('هیچ بارنامه‌ای برای بروزرسانی یافت نشد');
        return false;
    }
    
    // بررسی اینکه آیا فیلدهایی با prefix barnameh_ وجود دارند یا نه
    let hasBarnamehFields = false;
    const filledFields = [];
    
    // جستجوی تمام فیلدهای بارنامه در کل صفحه
    const allInputs = document.querySelectorAll('input[name^="barnameh_"]');
    
    allInputs.forEach(input => {
        if (input.name.startsWith('barnameh_') && input.value.trim() !== '') {
            hasBarnamehFields = true;
            const fieldLabel = input.closest('.form-group')?.querySelector('label')?.textContent?.replace(':', '') || 'نامشخص';
            const barnamehId = input.name.split('_')[1];
            filledFields.push(`بارنامه #${barnamehId}: ${fieldLabel} = "${input.value}"`);
        }
    });
    
    console.log('تعداد فیلدهای یافت شده:', allInputs.length);
    console.log('فیلدهای پر شده:', filledFields);
    
    if (!hasBarnamehFields) {
        const result = confirm(
            `هیچ اطلاعاتی در فیلدهای بارنامه‌ها وارد نشده است.\n\n` +
            `آیا می‌خواهید عملیات بروزرسانی را ادامه دهید؟\n\n` +
            `تعداد بارنامه‌ها: ${barnamehCount}\n` +
            `تعداد فیلدهای بارنامه: ${allInputs.length}`
        );
        return result;
    }
    
    // نمایش تایید نهایی با جزئیات فیلدهای پر شده
    const fieldsList = filledFields.slice(0, 5).join('\n• ');
    const moreFields = filledFields.length > 5 ? `\n• و ${filledFields.length - 5} فیلد دیگر...` : '';
    
    const confirmMessage = 
        `آیا از بروزرسانی همه بارنامه‌ها اطمینان دارید؟\n\n` +
        `تعداد بارنامه‌ها: ${barnamehCount}\n` +
        `تعداد فیلدهای پر شده: ${filledFields.length}\n\n` +
        `برخی از فیلدهای پر شده:\n• ${fieldsList}${moreFields}\n\n` +
        `⚠️ توجه: این عملیات قابل برگشت نیست!`;
    
    return confirm(confirmMessage);
}

// تابع ارسال بروزرسانی همه بارنامه‌ها
function submitUpdateAllBarnamehs() {
    if (!confirmUpdateAllBarnamehs()) {
        return;
    }
    
    // ایجاد فرم جدید برای ارسال همه داده‌ها
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.href;
    
    // اضافه کردن CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfToken) {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken.value;
        form.appendChild(csrfInput);
    }
    
    // اضافه کردن فیلد اکشن
    const actionInput = document.createElement('input');
    actionInput.type = 'hidden';
    actionInput.name = 'update_all_barnamehs';
    actionInput.value = 'true';
    form.appendChild(actionInput);
    
    // جمع‌آوری همه فیلدهای بارنامه
    const allInputs = document.querySelectorAll('input[name^="barnameh_"]');
    console.log('تعداد فیلدهای بارنامه یافت شده:', allInputs.length);
    
    let addedFields = 0;
    allInputs.forEach(input => {
        if (input.value.trim() !== '') {
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = input.name;
            hiddenInput.value = input.value;
            form.appendChild(hiddenInput);
            addedFields++;
            console.log('اضافه شد:', input.name, '=', input.value);
        }
    });
    
    console.log('تعداد فیلدهای اضافه شده به فرم:', addedFields);
    
    // اضافه کردن فرم به صفحه و ارسال
    document.body.appendChild(form);
    form.submit();
}