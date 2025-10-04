document.addEventListener('DOMContentLoaded', function() {
    // داده‌های نمونه برای پیش‌نمایش
    const sampleData = {
        customer_name: 'احمد محمدی',
        customer_phone: '09123456789',
        purchase_number: '1234567',
        invoice_id: '99000123',
        order_weight: '25000',
        product_type: 'ذرت',
        product_country: 'آرژانتین',
        cottage: '12345678',
        amount_paid: '750000000',
        customer_price: '30000',
        sales_agent_name: 'مهندس رضایی',
        status_display: 'ثبت شده',
        created_at: '1403/03/15',
        shenase_takhsis: 'ABC123456789'
    };

    const contentTextarea = document.getElementById('content');
    const previewBox = document.getElementById('previewBox');
    const samplePreviewBox = document.getElementById('samplePreviewBox');
    const charCountSpan = document.getElementById('charCount');
    const smsCountSpan = document.getElementById('smsCount');

    // تابع تبدیل اعداد انگلیسی به فارسی
    function toPersianNumbers(str) {
        const persianNumbers = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
        return str.replace(/[0-9]/g, function(w) {
            return persianNumbers[+w];
        });
    }

    // تابع شمارش کاراکتر و تعداد پیامک
    function updateCharacterCount() {
        const text = contentTextarea.value;
        const charCount = text.length;
        const smsCount = Math.ceil(charCount / 70) || 1;
        
        charCountSpan.textContent = toPersianNumbers(charCount.toString());
        smsCountSpan.textContent = toPersianNumbers(smsCount.toString());
        
        // تغییر رنگ بر اساس تعداد پیامک
        const counter = document.getElementById('charCounter');
        if (smsCount <= 1) {
            counter.style.color = '#2e7d32'; // سبز
        } else if (smsCount <= 3) {
            counter.style.color = '#f57c00'; // نارنجی
        } else {
            counter.style.color = '#d32f2f'; // قرمز
        }
    }

    // تابع به‌روزرسانی پیش‌نمایش
    function updatePreview() {
        const text = contentTextarea.value;
        previewBox.textContent = text || 'پیش‌نمایش متن در اینجا نمایش داده می‌شود...';
        
        // پیش‌نمایش با داده‌های نمونه
        let sampleText = text;
        
        // استفاده از روش ساده‌تر برای جایگزینی
        for (const [key, value] of Object.entries(sampleData)) {
            const pattern = new RegExp('{{\\s*' + key + '\\s*}}', 'g');
            sampleText = sampleText.replace(pattern, value);
        }
        
        samplePreviewBox.textContent = sampleText || 'پیش‌نمایش با داده‌های نمونه در اینجا نمایش داده می‌شود...';
    }

    // تابع نمایش toast برای متغیرها
    function showVariableToast(label, code) {
        // حذف toast قبلی
        const existingToast = document.querySelector('.variable-hint-toast');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = 'variable-hint-toast';
        toast.innerHTML = '<div class="variable-label">' + label + ' به متن اضافه شد</div>' +
                         '<div class="variable-code">کد متغیر: {{' + code + '}}</div>';
        
        document.body.appendChild(toast);
        
        setTimeout(function() {
            toast.remove();
        }, 3000);
    }

    // رویداد تایپ در textarea
    contentTextarea.addEventListener('input', function() {
        updateCharacterCount();
        updatePreview();
    });

    // رویداد کلیک روی دکمه‌های متغیر
    const placeholderButtons = document.querySelectorAll('.btn-placeholder');
    placeholderButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const placeholder = this.getAttribute('data-placeholder');
            const label = this.getAttribute('data-label');
            const cursorPosition = contentTextarea.selectionStart;
            const textBefore = contentTextarea.value.substring(0, cursorPosition);
            const textAfter = contentTextarea.value.substring(cursorPosition);
            
            const placeholderText = '{{' + placeholder + '}}';
            contentTextarea.value = textBefore + placeholderText + textAfter;
            
            // تنظیم مکان cursor بعد از متغیر
            const newCursorPosition = cursorPosition + placeholderText.length;
            contentTextarea.setSelectionRange(newCursorPosition, newCursorPosition);
            contentTextarea.focus();
            
            updateCharacterCount();
            updatePreview();
            showVariableToast(label, placeholder);
            
            // انیمیشن کلیک
            this.style.transform = 'scale(0.95)';
            setTimeout(function() {
                button.style.transform = '';
            }, 150);
        });
    });

    // بارگذاری متن پیش‌فرض
    const btnLoadDefault = document.getElementById('btnLoadDefault');
    if (btnLoadDefault) {
        btnLoadDefault.addEventListener('click', function() {
            const templateType = document.getElementById('template_type').value;
            let status = '';
            let defaultText = '';
            
            if (templateType === 'purchase') {
                status = document.getElementById('status').value;
                if (!status) {
                    alert('لطفا ابتدا وضعیت خرید بازارگاه را انتخاب کنید');
                    return;
                }
                
                // دریافت قالب‌های پیش‌فرض از Django context
                if (typeof defaultTemplates !== 'undefined') {
                    defaultText = defaultTemplates[status];
                }
            } else if (templateType === 'non_bazargah_purchase') {
                status = document.getElementById('non_bazargah_status').value;
                if (!status) {
                    alert('لطفا ابتدا وضعیت خرید خارج بازارگاه را انتخاب کنید');
                    return;
                }
                
                // دریافت قالب‌های پیش‌فرض از Django context
                if (typeof nonBazargahDefaultTemplates !== 'undefined') {
                    defaultText = nonBazargahDefaultTemplates[status];
                }
            } else {
                alert('لطفا ابتدا نوع قالب را انتخاب کنید');
                return;
            }
            
            if (defaultText) {
                contentTextarea.value = defaultText;
                updateCharacterCount();
                updatePreview();
            } else {
                alert('قالب پیش‌فرضی برای این وضعیت یافت نشد');
            }
        });
    }

    // مقداردهی اولیه
    updateCharacterCount();
    updatePreview();
}); 