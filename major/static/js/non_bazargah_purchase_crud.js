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
