document.addEventListener('DOMContentLoaded', function() {
    const templateContent = document.getElementById('templateContent');
    const charCount = document.getElementById('charCount');
    const usedPlaceholdersContainer = document.getElementById('usedPlaceholders');
    
    // استخراج و نمایش متغیرهای استفاده شده
    const contentText = templateContent.textContent;
    const regex = /\{\{(.+?)\}\}/g;
    let match;
    let usedPlaceholders = [];
    
    while ((match = regex.exec(contentText)) !== null) {
        let placeholder = match[1].trim();
        if (!usedPlaceholders.includes(placeholder)) {
            usedPlaceholders.push(placeholder);
        }
    }
    
    // نمایش متغیرهای استفاده شده
    if (usedPlaceholders.length > 0) {
        usedPlaceholders.forEach(function(placeholder) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-info badge-placeholder';
            badge.textContent = placeholder;
            usedPlaceholdersContainer.appendChild(badge);
        });
    } else {
        usedPlaceholdersContainer.innerHTML = '<p class="text-muted">هیچ متغیری در این قالب استفاده نشده است.</p>';
    }
    
    // هایلایت کردن متغیرها در متن قالب
    let highlightedContent = contentText;
    usedPlaceholders.forEach(function(placeholder) {
        const regex = new RegExp('{{\\s*' + placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*}}', 'g');
        highlightedContent = highlightedContent.replace(regex, '<span class="placeholder-highlight">{{ ' + placeholder + ' }}</span>');
    });
    
    templateContent.innerHTML = highlightedContent;
    
    // نمایش تعداد کاراکترها
    charCount.textContent = contentText.length;
    
    // محاسبه تعداد پیامک (هر 70 کاراکتر یک پیامک)
    const smsCountElement = document.getElementById('smsCount');
    if (smsCountElement) {
        const smsCount = Math.ceil(contentText.length / 70) || 1;
        smsCountElement.textContent = smsCount;
    }
    
    // نمایش تعداد متغیرها
    const placeholderCountElement = document.getElementById('placeholderCount');
    if (placeholderCountElement) {
        placeholderCountElement.textContent = usedPlaceholders.length;
    }
}); 