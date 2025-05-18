/**
 * Template Management JavaScript
 * 
 * This file contains functions for handling SMS templates including:
 * - Loading templates for a specific status
 * - Setting a template as default
 * - Displaying multiple templates per status
 * - Selecting templates
 */

// سیستم مدیریت قالب‌های پیامک
// Template Management System

let templates = {}; // Object to store templates by status
let currentStatus = null; // Current selected status
let selectedTemplateId = null; // Currently selected template ID

/**
 * Creates a template card for the template selector
 * @param {number} id - Template ID
 * @param {string} name - Template name 
 * @param {string} templateContent - Template content
 * @param {boolean} isDefault - Whether this is the default template
 * @returns {HTMLElement} Template card element
 */
function createTemplateCard(id, name, templateContent, isDefault) {
    const card = document.createElement('div');
    card.className = 'template-card';
    card.dataset.id = id;
    card.dataset.content = templateContent;
    
    if (isDefault) {
        card.classList.add('default');
        selectedTemplateId = id; // Pre-select the default template
    }
    
    const previewText = templateContent.length > 80 ? 
        templateContent.substring(0, 80) + '...' : 
        templateContent;
    
    card.innerHTML = `
        <div class="template-card-header">
            <h5 class="template-name">${name}</h5>
            ${isDefault ? '<span class="template-badge default"><i class="fas fa-star"></i> پیش‌فرض</span>' : ''}
        </div>
        <div class="template-card-body">
            <div class="template-preview">${previewText}</div>
        </div>
        <div class="template-card-footer">
            <button type="button" class="template-btn select-btn" onclick="selectTemplate(${id}, this)">
                ${isDefault ? '<i class="fas fa-check"></i> انتخاب شده' : '<i class="fas fa-check"></i> انتخاب'}
            </button>
            <button type="button" class="template-btn preview-btn" onclick="previewTemplate(event, this)">
                <i class="fas fa-search"></i> پیش‌نمایش
            </button>
        </div>
    `;
    
    // Add click event to select the card
    card.addEventListener('click', function(event) {
        // Prevent clicking when clicking on buttons
        if (event.target.closest('.template-btn')) return;
        
        selectTemplateCard(this);
    });
    
    return card;
}

/**
 * Selects a template card and updates the message field
 * @param {HTMLElement} card - Template card element
 */
function selectTemplateCard(card) {
    // Remove selected class from all cards
    document.querySelectorAll('.template-card').forEach(c => {
        c.classList.remove('selected');
        const selectBtn = c.querySelector('.select-btn');
        if (selectBtn) {
            selectBtn.innerHTML = '<i class="fas fa-check"></i> انتخاب';
        }
    });
    
    // Add selected class to this card
    card.classList.add('selected');
    const selectBtn = card.querySelector('.select-btn');
    if (selectBtn) {
        selectBtn.innerHTML = '<i class="fas fa-check"></i> انتخاب شده';
    }
    
    // Set the message field content
    const messageField = document.getElementById('message');
    if (messageField) {
        messageField.value = card.dataset.content;
        // Update character count
        const charCount = document.getElementById('char-count');
        if (charCount) {
            charCount.textContent = messageField.value.length;
        }
    }
    
    // Update selected template ID
    selectedTemplateId = card.dataset.id;
    
    // Update preview
    const templatePreview = document.getElementById('purchase-template-preview');
    if (templatePreview) {
        templatePreview.textContent = card.dataset.content;
    }
}

/**
 * Fetches all templates for a specific status
 * @param {string} status - Purchase status code
 */
function fetchTemplatesForStatus(status) {
    // Check if we already have templates for this status
    if (templates[status]) {
        updateTemplateSelector(templates[status], getPurchaseStatusDisplay(status));
        return;
    }
    
    // Otherwise fetch from server
    fetch(`/sms/api/templates/status/?status=${status}`)
        .then(response => response.json())
        .then(data => {
            if (data.templates && data.templates.length > 0) {
                templates[status] = data.templates;
                updateTemplateSelector(data.templates, data.status_display);
            } else {
                // No templates found
                const templateSelector = document.getElementById('template-selector');
                if (templateSelector) {
                    templateSelector.style.display = 'none';
                }
            }
        })
        .catch(error => {
            console.error('Error fetching templates:', error);
        });
}

/**
 * Updates the template selector with templates for the current status
 * @param {Array} templates - List of templates
 * @param {string} statusDisplay - Display name of the status
 */
function updateTemplateSelector(templates, statusDisplay) {
    const templateCards = document.getElementById('template-status-cards');
    if (!templateCards) return;
    
    // Clear existing cards
    templateCards.innerHTML = '';
    
    // Update title
    const selectorHeader = document.querySelector('.template-selector-header h4');
    if (selectorHeader) {
        selectorHeader.textContent = `قالب‌های پیام اطلاع‌رسانی ${statusDisplay}`;
    }
    
    // Create cards for each template
    templates.forEach(template => {
        const card = createTemplateCard(
            template.id,
            template.name,
            template.content,
            template.is_active
        );
        templateCards.appendChild(card);
    });
    
    // Show the template selector
    const templateSelector = document.getElementById('template-selector');
    if (templateSelector) {
        templateSelector.style.display = 'block';
    }
}

/**
 * Shows a preview of the template in a tooltip
 * @param {Event} event - Click event
 * @param {HTMLElement} button - Preview button
 */
function previewTemplate(event, button) {
    event.stopPropagation();
    
    // Close any existing tooltip
    closeTooltip();
    
    // Get the template content
    const card = button.closest('.template-card');
    const content = card.dataset.content;
    
    // Create tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'template-preview-tooltip';
    tooltip.innerHTML = `
        <div class="tooltip-header">
            <h5>پیش‌نمایش قالب</h5>
            <button type="button" class="close-tooltip-btn" onclick="closeTooltip()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="tooltip-body">
            <div class="template-full-preview">${content}</div>
        </div>
        <div class="tooltip-footer">
            <button type="button" class="template-btn select-tooltip-btn" onclick="selectTemplateCard(document.querySelector('.template-card[data-id=\\'${card.dataset.id}\\']')); closeTooltip();">
                <i class="fas fa-check"></i> انتخاب این قالب
            </button>
        </div>
    `;
    
    // Position tooltip
    document.body.appendChild(tooltip);
    
    // Calculate position
    const buttonRect = button.getBoundingClientRect();
    tooltip.style.top = `${buttonRect.bottom + window.scrollY + 10}px`;
    tooltip.style.left = `${buttonRect.left + window.scrollX - (tooltip.offsetWidth / 2) + (button.offsetWidth / 2)}px`;
    
    // Add click outside event
    document.addEventListener('click', closeTooltipOnClickOutside);
}

/**
 * Closes tooltip when clicking outside
 */
function closeTooltipOnClickOutside(event) {
    if (!event.target.closest('.template-preview-tooltip') && !event.target.closest('.preview-btn')) {
        closeTooltip();
    }
}

/**
 * Closes the tooltip
 */
function closeTooltip() {
    document.removeEventListener('click', closeTooltipOnClickOutside);
    const tooltip = document.querySelector('.template-preview-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

/**
 * Generates template cards for a specific status
 * @param {string} currentStatus - Current purchase status
 * @param {Object} templateData - All template data
 * @param {Object} purchaseStatuses - Purchase status display names
 */
function generateTemplateCards(currentStatus, templateData, purchaseStatuses) {
    // Set current status
    if (!currentStatus) return;
    
    // Fetch templates for this status
    fetchTemplatesForStatus(currentStatus);
}

/**
 * Gets display name for a purchase status
 * @param {string} status - Status code
 * @returns {string} Status display name
 */
function getPurchaseStatusDisplay(status) {
    // Get purchase statuses from the hidden element
    const purchaseStatusesElem = document.getElementById('purchase-statuses');
    if (!purchaseStatusesElem) return status;
    
    try {
        const purchaseStatuses = JSON.parse(purchaseStatusesElem.textContent);
        return purchaseStatuses[status] || status;
    } catch (e) {
        return status;
    }
}

/**
 * Toggles the template selector visibility
 */
function toggleTemplateSelector() {
    const body = document.getElementById('template-selector-body');
    const btn = document.getElementById('template-collapse-btn');
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        btn.innerHTML = '<i class="fas fa-chevron-up"></i>';
    } else {
        body.style.display = 'none';
        btn.innerHTML = '<i class="fas fa-chevron-down"></i>';
    }
}

/**
 * Changes the template view mode (grid or list)
 */
function changeTemplateView(viewMode) {
    const cards = document.getElementById('template-status-cards');
    const gridBtn = document.getElementById('grid-view-btn');
    const listBtn = document.getElementById('list-view-btn');
    
    if (viewMode === 'grid') {
        cards.className = 'template-cards grid-view';
        gridBtn.classList.add('active');
        listBtn.classList.remove('active');
    } else {
        cards.className = 'template-cards list-view';
        listBtn.classList.add('active');
        gridBtn.classList.remove('active');
    }
}

/**
 * Filters template cards based on search input
 */
function filterTemplateCards() {
    const searchInput = document.getElementById('template-search');
    const cards = document.querySelectorAll('.template-card');
    
    if (!searchInput || !cards.length) return;
    
    const searchText = searchInput.value.toLowerCase();
    
    cards.forEach(card => {
        const name = card.querySelector('.template-name').textContent.toLowerCase();
        const content = card.dataset.content.toLowerCase();
        
        if (name.includes(searchText) || content.includes(searchText)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

/**
 * Selects a template by ID
 */
function selectTemplate(id, button) {
    event.stopPropagation();
    const card = button.closest('.template-card');
    selectTemplateCard(card);
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initial setup for template selector
    const purchaseSelector = document.getElementById('purchase-selector');
    if (purchaseSelector) {
        purchaseSelector.addEventListener('change', function() {
            if (this.value) {
                const selectedOption = this.options[this.selectedIndex];
                const status = selectedOption.getAttribute('data-status');
                
                // Generate template cards for this status
                const templateDataElem = document.getElementById('templates-data');
                const purchaseStatusesElem = document.getElementById('purchase-statuses');
                
                if (templateDataElem && purchaseStatusesElem) {
                    try {
                        const templateData = JSON.parse(templateDataElem.textContent);
                        const purchaseStatuses = JSON.parse(purchaseStatusesElem.textContent);
                        generateTemplateCards(status, templateData, purchaseStatuses);
                    } catch (e) {
                        console.error('Error parsing template data:', e);
                    }
                }
            }
        });
    }
}); 