/**
 * Live Price Display JavaScript
 * نمایش لایو قیمت به حروف فارسی برای فرم‌های مالی
 * 
 * Features:
 * - تبدیل عدد به حروف فارسی
 * - نمایش لایو هنگام تایپ
 * - پشتیبانی از مبالغ تا میلیارد
 * - فرمت‌بندی مناسب برای نمایش
 */

class LivePriceDisplay {
    constructor() {
        this.numberWords = {
            // اعداد پایه
            0: 'صفر',
            1: 'یک',
            2: 'دو',
            3: 'سه',
            4: 'چهار',
            5: 'پنج',
            6: 'شش',
            7: 'هفت',
            8: 'هشت',
            9: 'نه',
            10: 'ده',
            11: 'یازده',
            12: 'دوازده',
            13: 'سیزده',
            14: 'چهارده',
            15: 'پانزده',
            16: 'شانزده',
            17: 'هفده',
            18: 'هجده',
            19: 'نوزده',
            20: 'بیست',
            30: 'سی',
            40: 'چهل',
            50: 'پنجاه',
            60: 'شصت',
            70: 'هفتاد',
            80: 'هشتاد',
            90: 'نود',
            100: 'صد',
            200: 'دویست',
            300: 'سیصد',
            400: 'چهارصد',
            500: 'پانصد',
            600: 'ششصد',
            700: 'هفتصد',
            800: 'هشتصد',
            900: 'نهصد'
        };

        this.scales = {
            1000: 'هزار',
            1000000: 'میلیون',
            1000000000: 'میلیارد'
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // پیدا کردن تمام فیلدهای مبلغ در فرم
        const amountInputs = document.querySelectorAll('input[name="amount"], input[id*="amount"], input[placeholder*="مبلغ"]');
        
        amountInputs.forEach(input => {
            this.attachLiveDisplay(input);
        });

        // برای فیلدهای جدید که ممکن است بعداً اضافه شوند
        this.observeNewInputs();
    }

    attachLiveDisplay(input) {
        // ایجاد عنصر نمایش قیمت به حروف
        const displayElement = this.createDisplayElement(input);
        
        // اضافه کردن عنصر نمایش بعد از فیلد ورودی
        input.parentNode.insertBefore(displayElement, input.nextSibling);
        
        // رویدادهای ورودی
        input.addEventListener('input', () => {
            this.updateDisplay(input, displayElement);
        });

        input.addEventListener('focus', () => {
            displayElement.style.display = 'block';
        });

        input.addEventListener('blur', () => {
            // کمی تاخیر برای نمایش نهایی
            setTimeout(() => {
                if (document.activeElement !== input) {
                    displayElement.style.display = 'none';
                }
            }, 200);
        });

        // مقداردهی اولیه
        this.updateDisplay(input, displayElement);
    }

    createDisplayElement(input) {
        const displayDiv = document.createElement('div');
        displayDiv.className = 'live-price-display';
        displayDiv.style.cssText = `
            display: none;
            margin-top: 0.5rem;
            padding: 0.75rem 1rem;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border: 1px solid #0ea5e9;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            color: #0369a1;
            font-weight: 600;
            text-align: center;
            box-shadow: 0 2px 4px rgba(14, 165, 233, 0.1);
            transition: all 0.3s ease;
            direction: rtl;
            font-family: 'Vazir', 'Tahoma', sans-serif;
        `;

        const icon = document.createElement('i');
        icon.className = 'fas fa-text-width';
        icon.style.marginLeft = '0.5rem';
        icon.style.color = '#0ea5e9';

        const textSpan = document.createElement('span');
        textSpan.className = 'price-text';

        displayDiv.appendChild(icon);
        displayDiv.appendChild(textSpan);

        return displayDiv;
    }

    updateDisplay(input, displayElement) {
        const value = input.value.trim();
        
        if (!value || value === '' || value === '0') {
            displayElement.style.display = 'none';
            return;
        }

        // تبدیل به عدد
        const number = parseInt(value.replace(/[^\d]/g, ''));
        
        if (isNaN(number) || number <= 0) {
            displayElement.style.display = 'none';
            return;
        }

        // تبدیل به حروف
        const words = this.numberToWords(number);
        
        if (words) {
            const textSpan = displayElement.querySelector('.price-text');
            textSpan.textContent = `${words} ریال`;
            displayElement.style.display = 'block';
            
            // انیمیشن ظاهر شدن
            displayElement.style.opacity = '0';
            displayElement.style.transform = 'translateY(-10px)';
            
            setTimeout(() => {
                displayElement.style.opacity = '1';
                displayElement.style.transform = 'translateY(0)';
            }, 50);
        } else {
            displayElement.style.display = 'none';
        }
    }

    numberToWords(number) {
        if (number === 0) return 'صفر';
        if (number < 0) return 'منفی ' + this.numberToWords(-number);

        // محدودیت برای اعداد خیلی بزرگ
        if (number > 999999999999) {
            return 'عدد خیلی بزرگ';
        }

        let result = '';

        // میلیارد
        if (number >= 1000000000) {
            const billions = Math.floor(number / 1000000000);
            result += this.convertHundreds(billions) + ' میلیارد';
            number %= 1000000000;
            if (number > 0) result += ' و ';
        }

        // میلیون
        if (number >= 1000000) {
            const millions = Math.floor(number / 1000000);
            result += this.convertHundreds(millions) + ' میلیون';
            number %= 1000000;
            if (number > 0) result += ' و ';
        }

        // هزار
        if (number >= 1000) {
            const thousands = Math.floor(number / 1000);
            result += this.convertHundreds(thousands) + ' هزار';
            number %= 1000;
            if (number > 0) result += ' و ';
        }

        // زیر هزار
        if (number > 0) {
            result += this.convertHundreds(number);
        }

        return result.trim();
    }

    convertHundreds(number) {
        if (number === 0) return '';
        if (number < 100) return this.convertTens(number);

        const hundreds = Math.floor(number / 100);
        const remainder = number % 100;

        let result = this.numberWords[hundreds * 100];
        
        if (remainder > 0) {
            result += ' و ' + this.convertTens(remainder);
        }

        return result;
    }

    convertTens(number) {
        if (number === 0) return '';
        if (number < 20) return this.numberWords[number];

        const tens = Math.floor(number / 10) * 10;
        const ones = number % 10;

        let result = this.numberWords[tens];
        
        if (ones > 0) {
            result += ' و ' + this.numberWords[ones];
        }

        return result;
    }

    observeNewInputs() {
        // مشاهده تغییرات DOM برای فیلدهای جدید
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // بررسی فیلدهای جدید
                        const newInputs = node.querySelectorAll ? 
                            node.querySelectorAll('input[name="amount"], input[id*="amount"], input[placeholder*="مبلغ"]') : 
                            (node.matches && node.matches('input[name="amount"], input[id*="amount"], input[placeholder*="مبلغ"]') ? [node] : []);
                        
                        newInputs.forEach(input => {
                            if (!input.hasAttribute('data-live-price-attached')) {
                                input.setAttribute('data-live-price-attached', 'true');
                                this.attachLiveDisplay(input);
                            }
                        });
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // متد عمومی برای اضافه کردن نمایش به فیلد خاص
    attachToInput(inputSelector) {
        const input = document.querySelector(inputSelector);
        if (input && !input.hasAttribute('data-live-price-attached')) {
            input.setAttribute('data-live-price-attached', 'true');
            this.attachLiveDisplay(input);
        }
    }

    // متد عمومی برای حذف نمایش از فیلد خاص
    detachFromInput(inputSelector) {
        const input = document.querySelector(inputSelector);
        if (input) {
            input.removeAttribute('data-live-price-attached');
            const displayElement = input.parentNode.querySelector('.live-price-display');
            if (displayElement) {
                displayElement.remove();
            }
        }
    }
}

// CSS اضافی برای بهبود نمایش
const additionalStyles = `
<style>
.live-price-display {
    animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.live-price-display:hover {
    background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(14, 165, 233, 0.15);
}

.price-text {
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* برای حالت تاریک */
@media (prefers-color-scheme: dark) {
    .live-price-display {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        border-color: #3b82f6;
        color: #dbeafe;
    }
    
    .live-price-display:hover {
        background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%);
    }
    
    .live-price-display i {
        color: #3b82f6;
    }
}
</style>
`;

// اضافه کردن استایل‌ها به صفحه
if (!document.querySelector('#live-price-display-styles')) {
    const styleElement = document.createElement('div');
    styleElement.id = 'live-price-display-styles';
    styleElement.innerHTML = additionalStyles;
    document.head.appendChild(styleElement);
}

// مقداردهی اولیه
document.addEventListener('DOMContentLoaded', function() {
    window.livePriceDisplay = new LivePriceDisplay();
});

// Export برای استفاده در ماژول‌های دیگر
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LivePriceDisplay;
}
