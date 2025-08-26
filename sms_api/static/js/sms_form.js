/**
 * SMS Form Management JavaScript
 * Handles the create SMS form functionality
 */

// Global variables
let templateData = {};
let purchaseStatuses = {};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeData();
    initializeFormHandlers();
    initializeCharacterCounters();
    setupVariableTagHandlers();
});

/**
 * Initialize data from hidden JSON elements
 */
function initializeData() {
    try {
        const templatesElement = document.getElementById('templates-data');
        const statusesElement = document.getElementById('purchase-statuses');
        
        templateData = templatesElement ? JSON.parse(templatesElement.textContent || '{}') : {};
        purchaseStatuses = statusesElement ? JSON.parse(statusesElement.textContent || '{}') : {};
    } catch (error) {
        console.error('Error initializing data:', error);
        templateData = {};
        purchaseStatuses = {};
    }
}

/**
 * Initialize form event handlers
 */
function initializeFormHandlers() {
    // Purchase selector handler
    const purchaseSelector = document.getElementById('purchase-selector');
    if (purchaseSelector) {
        purchaseSelector.addEventListener('change', loadPurchaseTemplate);
    }
    
    // Message type radio handlers
    const messageTypeRadios = document.querySelectorAll('input[name="message_type"]');
    messageTypeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            toggleMessageFields(this.value);
        });
    });
}

/**
 * Initialize character counters for textareas
 */
function initializeCharacterCounters() {
    setupCharacterCounter('message', 'char-count');
    setupCharacterCounter('marketing_message', 'marketing-char-count');
}

/**
 * Setup character counter for a specific textarea
 */
function setupCharacterCounter(textareaId, counterId) {
    const textarea = document.getElementById(textareaId);
    const counter = document.getElementById(counterId);
    
    if (textarea && counter) {
        // Initial count
        counter.textContent = textarea.value.length;
        
        // Update on input
        textarea.addEventListener('input', function() {
            counter.textContent = this.value.length;
            
            // Add warning color if approaching limit
            if (this.value.length > 4500) {
                counter.style.color = '#f57c00';
            } else if (this.value.length > 4700) {
                counter.style.color = '#d32f2f';
        } else {
                counter.style.color = '#666';
            }
        });
    }
}

/**
 * Setup click handlers for variable tags
 */
function setupVariableTagHandlers() {
    const variableTags = document.querySelectorAll('.variable-tag');
    variableTags.forEach(tag => {
        tag.addEventListener('click', function() {
            insertVariable(this.textContent);
        });
        
        // Add hover effect
        tag.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
        });
        
        tag.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });
}

/**
 * Mode switching functions
 */
function showCustomerSearch() {
    const customerBtn = document.getElementById('customer-search-btn');
    const directBtn = document.getElementById('direct-number-btn');
    const customerSection = document.getElementById('customer-search-section');
    const directSection = document.getElementById('direct-number-section');
    
    if (customerBtn) customerBtn.classList.add('selected');
    if (directBtn) directBtn.classList.remove('selected');
    if (customerSection) customerSection.style.display = 'block';
    if (directSection) directSection.style.display = 'none';
}

function showDirectMarketing() {
    const customerBtn = document.getElementById('customer-search-btn');
    const directBtn = document.getElementById('direct-number-btn');
    const customerSection = document.getElementById('customer-search-section');
    const directSection = document.getElementById('direct-number-section');
    
    if (directBtn) directBtn.classList.add('selected');
    if (customerBtn) customerBtn.classList.remove('selected');
    if (customerSection) customerSection.style.display = 'none';
    if (directSection) directSection.style.display = 'block';
}

/**
 * Toggle message fields based on message type
 */
function toggleMessageFields(messageType) {
    const purchaseFields = document.getElementById('purchase-fields');
    const marketingFields = document.getElementById('marketing-fields');
    
    if (purchaseFields) {
        purchaseFields.style.display = messageType === 'purchase' ? 'block' : 'none';
    }
    
    if (marketingFields) {
        marketingFields.style.display = messageType === 'marketing' ? 'block' : 'none';
    }
}

/**
 * Load template based on selected purchase
 */
function loadPurchaseTemplate(refresh = false) {
    const purchaseSelector = document.getElementById('purchase-selector');
    const messageField = document.getElementById('message');
    const charCount = document.getElementById('char-count');
    const infoCard = document.getElementById('purchase-info-card');
    const statusDisplay = document.getElementById('purchase-status-display');
    const templatePreview = document.getElementById('purchase-template-preview');
    
    if (!purchaseSelector || !messageField) return;
    
    // Reset if no purchase selected
    if (!purchaseSelector.value) {
        resetPurchaseForm(messageField, charCount, infoCard);
        return;
    }
    
    // Get selected option
    const selectedOption = purchaseSelector.options[purchaseSelector.selectedIndex];
    const status = selectedOption.getAttribute('data-status');
    
    // Show info card
    if (infoCard) infoCard.style.display = 'block';
    
    // Update status display
    updateStatusDisplay(status, statusDisplay);
    
    // Load template for status
    loadTemplateForStatus(status, messageField, charCount, templatePreview, refresh);
}

/**
 * Reset purchase form to initial state
 */
function resetPurchaseForm(messageField, charCount, infoCard) {
    if (messageField) messageField.value = '';
    if (charCount) charCount.textContent = '0';
    if (infoCard) infoCard.style.display = 'none';
}

/**
 * Update status display and badge styling
 */
function updateStatusDisplay(status, statusDisplay) {
    if (statusDisplay && purchaseStatuses[status]) {
        statusDisplay.textContent = purchaseStatuses[status];
        
        // Update status badge color
        const statusBadge = document.getElementById('purchase-status-badge');
        if (statusBadge) {
            statusBadge.className = 'purchase-status-badge';
            statusBadge.classList.add(getStatusClass(status));
        }
    }
}

/**
 * Get CSS class for status badge
 */
function getStatusClass(status) {
    const dangerStatuses = ['CANCELED', 'ARCHIVED'];
    const successStatuses = ['FULLY_SETTLED', 'PURCHASE_CLOSED', 'INVOICE_ISSUED'];
    const warningStatuses = ['WAITING_FOR_BARNAMEH', 'BARNAMEH_INCOMPLETE'];
    
    if (dangerStatuses.includes(status)) return 'status-danger';
    if (successStatuses.includes(status)) return 'status-success';
    if (warningStatuses.includes(status)) return 'status-warning';
    return 'status-info';
}

/**
 * Load template for specific status
 */
function loadTemplateForStatus(status, messageField, charCount, templatePreview, refresh) {
    if (templateData[status] && templateData[status].trim() !== '') {
        // Template exists
        if (messageField.value === '' || refresh) {
            messageField.value = templateData[status];
            if (charCount) charCount.textContent = messageField.value.length;
        }
        
        if (templatePreview) {
            templatePreview.textContent = templateData[status];
        }
    } else {
        // No template exists
        if (refresh) {
            messageField.value = '';
            if (charCount) charCount.textContent = '0';
        }
        
        if (templatePreview) {
            templatePreview.innerHTML = createNoTemplateMessage(status);
        }
    }
}

/**
 * Create no template message HTML
 */
function createNoTemplateMessage(status) {
    return `
        <div class="no-template-message">
            <p>قالب پیامی برای این وضعیت تعریف نشده است.</p>
            <div style="margin-top: 1rem;">
                <a href="/sms/templates/create/?status=${status}" class="action-button light-teal" target="_blank">
                    <i class="fas fa-plus"></i> ایجاد قالب جدید
                </a>
            </div>
        </div>
    `;
}

/**
 * Toggle more variables visibility
 */
function toggleMoreVariables() {
    const moreVars = document.getElementById('more-variables');
    const btn = document.querySelector('.more-variables-btn i');
    
    if (moreVars) {
        const isHidden = moreVars.style.display === 'none';
        moreVars.style.display = isHidden ? 'flex' : 'none';
        
        if (btn) {
            btn.className = isHidden ? 'fas fa-chevron-up' : 'fas fa-ellipsis-h';
        }
    }
}

/**
 * Insert variable into message field at cursor position
 */
function insertVariable(variable) {
    const messageField = document.getElementById('message');
    if (!messageField) return;
    
    const cursorPos = messageField.selectionStart;
    const textBefore = messageField.value.substring(0, cursorPos);
    const textAfter = messageField.value.substring(cursorPos);
    
    messageField.value = textBefore + variable + textAfter;
    
    // Update character count
    const charCount = document.getElementById('char-count');
    if (charCount) charCount.textContent = messageField.value.length;
    
    // Set cursor position after inserted variable
    messageField.focus();
    messageField.setSelectionRange(cursorPos + variable.length, cursorPos + variable.length);
    
    // Trigger input event to update character counter styling
    messageField.dispatchEvent(new Event('input'));
}

/**
 * Marketing templates
 */
const marketingTemplates = {
    'company': 'شرکت تامین نهاده سیمرغ با بیش از 10 سال تجربه در واردات و تأمین نهاده‌های دامی، همراه شما در مسیر موفقیت است. برای مشاوره رایگان تماس بگیرید.\n۰۲۱-۶۶۵۶۲۲۱۶',
    'products': 'مشتری گرامی، محصولات جدید وارداتی شامل ذرت، جو و کنجاله سویا به انبار ما رسیده است. برای اطلاع از قیمت‌ها با ما تماس بگیرید.\n۰۲۱-۶۶۵۶۲۲۱۶',
    'discount': 'پیشنهاد ویژه! با هر سفارش بیش از ۲۰ تن، ۵٪ تخفیف ویژه دریافت کنید. این فرصت محدود است.\nبرای ثبت سفارش: ۰۲۱-۶۶۵۶۲۲۱۶'
};

/**
 * Apply marketing template to message field
 */
function useMarketingTemplate(templateKey) {
    const textarea = document.getElementById('marketing_message') || document.getElementById('message');
    const counter = document.getElementById('marketing-char-count') || document.getElementById('char-count');
    
    if (textarea && marketingTemplates[templateKey]) {
        textarea.value = marketingTemplates[templateKey];
        
        if (counter) {
            counter.textContent = textarea.value.length;
        }
        
        // Trigger input event to update character counter styling
        textarea.dispatchEvent(new Event('input'));
        
        // Add visual feedback
        showTemplateAppliedFeedback(templateKey);
    }
}

/**
 * Show visual feedback when template is applied
 */
function showTemplateAppliedFeedback(templateKey) {
    // Create temporary feedback element
    const feedback = document.createElement('div');
    feedback.className = 'template-feedback';
    feedback.textContent = 'قالب اعمال شد ✓';
    feedback.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #4caf50;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        z-index: 9999;
        animation: fadeInOut 2s ease-in-out;
    `;
    
    document.body.appendChild(feedback);
    
    // Remove after animation
    setTimeout(() => {
        if (feedback.parentNode) {
            feedback.parentNode.removeChild(feedback);
        }
    }, 2000);
}

/**
 * Add CSS animation for feedback
 */
if (!document.getElementById('feedback-animation-styles')) {
    const style = document.createElement('style');
    style.id = 'feedback-animation-styles';
    style.textContent = `
        @keyframes fadeInOut {
            0% { opacity: 0; transform: translateY(-20px); }
            20% { opacity: 1; transform: translateY(0); }
            80% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(-20px); }
        }
    `;
    document.head.appendChild(style);
}

/**
 * Form validation before submission
 */
function validateSmsForm(form) {
    const messageField = form.querySelector('textarea[name="message"]');
    const recipientField = form.querySelector('input[name="recipient_number"]');
    
    if (!messageField || !messageField.value.trim()) {
        alert('لطفاً متن پیام را وارد کنید.');
        return false;
    }
    
    if (messageField.value.length > 255) {
        alert('متن پیام نباید بیش از 255 کاراکتر باشد.');
        return false;
    }
    
    if (recipientField && recipientField.value) {
        const phoneRegex = /^(0|0098|\+98)?9\d{9}$/;
        if (!phoneRegex.test(recipientField.value)) {
            alert('فرمت شماره تلفن صحیح نیست.');
            return false;
        }
    }
    
    return true;
}

// Add form validation to all SMS forms
document.addEventListener('DOMContentLoaded', function() {
    const smsForms = document.querySelectorAll('.sms-form');
    smsForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateSmsForm(this)) {
                e.preventDefault();
            }
        });
    });
});

/**
 * Utility functions
 */

// Debounce function for performance optimization
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Format numbers to Persian digits
function toPersianDigits(str) {
    const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    return str.toString().replace(/\d/g, x => persianDigits[parseInt(x)]);
}

// Export functions for global access
window.SmsForm = {
    showCustomerSearch,
    showDirectMarketing,
    toggleMessageFields,
    loadPurchaseTemplate,
    toggleMoreVariables,
    insertVariable,
    useMarketingTemplate
}; 