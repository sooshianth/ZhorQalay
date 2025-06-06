/**
 * Template Management JavaScript
 * Enhanced version for better performance and user experience
 * 
 * Features:
 * - Template caching
 * - Better error handling  
 * - Improved UI feedback
 * - Cleaner code structure
 */

// Template Management System
class TemplateManager {
    constructor() {
        this.templates = {}; // Cache for templates by status
        this.currentStatus = null;
        this.selectedTemplateId = null;
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Purchase selector change event
        const purchaseSelector = document.getElementById('purchase-selector');
        if (purchaseSelector) {
            purchaseSelector.addEventListener('change', (e) => {
                const selectedOption = e.target.options[e.target.selectedIndex];
                const status = selectedOption?.getAttribute('data-status');
                
                if (status) {
                    this.loadTemplatesForStatus(status);
                } else {
                    this.hideTemplateSelector();
                }
            });
        }
        
        // Search input handler
        const searchInput = document.getElementById('template-search');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(() => {
                this.filterTemplateCards();
            }, 300));
        }
    }
    
    /**
     * Load templates for a specific status
     */
    async loadTemplatesForStatus(status) {
        this.currentStatus = status;
        
        // Check cache first
        if (this.templates[status]) {
            this.displayTemplates(this.templates[status], status);
            return;
        }
        
        // Show loading state
        this.showLoading();
        
        try {
            const response = await fetch(`/sms/api/templates/status/?status=${status}`);
            const data = await response.json();
            
            if (data.templates && data.templates.length > 0) {
                // Cache the templates
                this.templates[status] = data.templates;
                this.displayTemplates(data.templates, status);
            } else {
                this.showNoTemplatesMessage(status);
            }
        } catch (error) {
            console.error('Error loading templates:', error);
            this.showErrorMessage();
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Display templates in the UI
     */
    displayTemplates(templates, status) {
        const container = document.getElementById('template-status-cards');
        if (!container) return;
        
        // Clear existing content
        container.innerHTML = '';
        
        // Update header
        this.updateSelectorHeader(status, templates.length);
        
        // Create template cards
        templates.forEach(template => {
            const card = this.createTemplateCard(template);
            container.appendChild(card);
        });
        
        // Show the selector
        this.showTemplateSelector();
        
        // Auto-select default template
        const defaultTemplate = templates.find(t => t.is_active);
        if (defaultTemplate) {
            this.selectTemplateById(defaultTemplate.id);
        }
    }
    
    /**
     * Create a template card element
     */
    createTemplateCard(template) {
        const card = document.createElement('div');
        card.className = 'template-card';
        card.dataset.id = template.id;
        card.dataset.content = template.content;
        
        if (template.is_active) {
            card.classList.add('default');
        }
        
        const previewText = this.truncateText(template.content, 100);
        
        card.innerHTML = `
            <div class="template-card-header">
                <h5 class="template-name">${this.escapeHtml(template.name)}</h5>
                ${template.is_active ? '<span class="template-badge default"><i class="fas fa-star"></i> پیش‌فرض</span>' : ''}
            </div>
            <div class="template-card-body">
                <div class="template-preview">${this.escapeHtml(previewText)}</div>
            </div>
            <div class="template-card-footer">
                <button type="button" class="template-btn select-btn" onclick="templateManager.selectTemplate(${template.id})">
                    <i class="fas fa-check"></i> انتخاب
                </button>
                <button type="button" class="template-btn preview-btn" onclick="templateManager.previewTemplate(${template.id}, event)">
                    <i class="fas fa-eye"></i> پیش‌نمایش
                </button>
            </div>
        `;
        
        // Add click event
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.template-btn')) {
                this.selectTemplate(template.id);
            }
        });
        
        return card;
    }
    
    /**
     * Select a template by ID
     */
    selectTemplate(templateId) {
        const card = document.querySelector(`[data-id="${templateId}"]`);
        if (!card) return;
        
        // Remove selection from all cards
        document.querySelectorAll('.template-card').forEach(c => {
            c.classList.remove('selected');
            const selectBtn = c.querySelector('.select-btn');
            if (selectBtn) {
                selectBtn.innerHTML = '<i class="fas fa-check"></i> انتخاب';
            }
        });
        
        // Select this card
        card.classList.add('selected');
        const selectBtn = card.querySelector('.select-btn');
        if (selectBtn) {
            selectBtn.innerHTML = '<i class="fas fa-check"></i> انتخاب شده';
        }
        
        // Update message field
        this.updateMessageField(card.dataset.content);
        
        // Store selected template ID
        this.selectedTemplateId = templateId;
        
        // Show feedback
        this.showSelectionFeedback(templateId);
    }
    
    /**
     * Select template by ID (for programmatic selection)
     */
    selectTemplateById(templateId) {
        this.selectTemplate(templateId);
    }
    
    /**
     * Preview a template
     */
    previewTemplate(templateId, event) {
        event?.stopPropagation();
        
        const card = document.querySelector(`[data-id="${templateId}"]`);
        if (!card) return;
        
        this.closeTooltip();
        
        const tooltip = this.createPreviewTooltip(card);
        document.body.appendChild(tooltip);
        
        // Position tooltip
        this.positionTooltip(tooltip, event?.target || card);
        
        // Add outside click listener
        setTimeout(() => {
            document.addEventListener('click', this.closeTooltipOnClickOutside.bind(this));
        }, 100);
    }
    
    /**
     * Create preview tooltip
     */
    createPreviewTooltip(card) {
        const tooltip = document.createElement('div');
        tooltip.className = 'template-preview-tooltip';
        tooltip.id = 'template-preview-tooltip';
        
        const templateName = card.querySelector('.template-name').textContent;
        const content = card.dataset.content;
        
        tooltip.innerHTML = `
            <div class="tooltip-header">
                <h5>${this.escapeHtml(templateName)}</h5>
                <button type="button" class="close-tooltip-btn" onclick="templateManager.closeTooltip()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="tooltip-body">
                <div class="template-full-preview">${this.escapeHtml(content)}</div>
            </div>
            <div class="tooltip-footer">
                <button type="button" class="template-btn select-tooltip-btn" onclick="templateManager.selectTemplate(${card.dataset.id}); templateManager.closeTooltip();">
                    <i class="fas fa-check"></i> انتخاب این قالب
                </button>
            </div>
        `;
        
        return tooltip;
    }
    
    /**
     * Position tooltip relative to target element
     */
    positionTooltip(tooltip, target) {
        const rect = target.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let top = rect.bottom + window.scrollY + 10;
        let left = rect.left + window.scrollX - (tooltipRect.width / 2) + (rect.width / 2);
        
        // Ensure tooltip stays within viewport
        if (left < 10) left = 10;
        if (left + tooltipRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tooltipRect.width - 10;
        }
        
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }
    
    /**
     * Close tooltip when clicking outside
     */
    closeTooltipOnClickOutside(event) {
        const tooltip = document.getElementById('template-preview-tooltip');
        if (tooltip && !tooltip.contains(event.target) && !event.target.closest('.preview-btn')) {
            this.closeTooltip();
        }
    }
    
    /**
     * Close preview tooltip
     */
    closeTooltip() {
        const tooltip = document.getElementById('template-preview-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
        document.removeEventListener('click', this.closeTooltipOnClickOutside.bind(this));
    }
    
    /**
     * Update message field with template content
     */
    updateMessageField(content) {
        const messageField = document.getElementById('message');
        const charCount = document.getElementById('char-count');
        const templatePreview = document.getElementById('purchase-template-preview');
        
        if (messageField) {
            messageField.value = content;
            
            if (charCount) {
                charCount.textContent = content.length;
            }
            
            // Trigger input event for any listeners
            messageField.dispatchEvent(new Event('input'));
        }
        
        if (templatePreview) {
            templatePreview.textContent = content;
        }
    }
    
    /**
     * Filter template cards based on search
     */
    filterTemplateCards() {
        const searchInput = document.getElementById('template-search');
        const cards = document.querySelectorAll('.template-card');
        
        if (!searchInput || !cards.length) return;
        
        const searchText = searchInput.value.toLowerCase().trim();
        
        cards.forEach(card => {
            const name = card.querySelector('.template-name').textContent.toLowerCase();
            const content = card.dataset.content.toLowerCase();
            
            const matches = !searchText || name.includes(searchText) || content.includes(searchText);
            card.style.display = matches ? '' : 'none';
        });
        
        // Update results count
        const visibleCards = Array.from(cards).filter(card => card.style.display !== 'none');
        this.updateSearchResults(visibleCards.length, cards.length);
    }
    
    /**
     * Update search results count
     */
    updateSearchResults(visible, total) {
        const resultsText = document.getElementById('search-results-text');
        if (resultsText) {
            resultsText.textContent = `${visible} از ${total} قالب`;
        }
    }
    
    /**
     * Show loading state
     */
    showLoading() {
        const container = document.getElementById('template-status-cards');
        if (container) {
            container.innerHTML = `
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    در حال بارگذاری قالب‌ها...
                </div>
            `;
        }
        this.isLoading = true;
    }
    
    /**
     * Hide loading state
     */
    hideLoading() {
        this.isLoading = false;
    }
    
    /**
     * Show no templates message
     */
    showNoTemplatesMessage(status) {
        const container = document.getElementById('template-status-cards');
        if (container) {
            const statusDisplay = this.getPurchaseStatusDisplay(status);
            container.innerHTML = `
                <div class="no-templates-message">
                    <i class="fas fa-file-alt"></i>
                    <p>هنوز قالبی برای وضعیت "${statusDisplay}" ایجاد نشده است.</p>
                    <a href="/sms/templates/create/?status=${status}" class="btn btn-primary" target="_blank">
                        <i class="fas fa-plus"></i> ایجاد قالب جدید
                    </a>
                </div>
            `;
        }
        this.showTemplateSelector();
    }
    
    /**
     * Show error message
     */
    showErrorMessage() {
        const container = document.getElementById('template-status-cards');
        if (container) {
            container.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>خطا در بارگذاری قالب‌ها</p>
                    <button type="button" class="btn btn-secondary" onclick="templateManager.loadTemplatesForStatus('${this.currentStatus}')">
                        <i class="fas fa-retry"></i> تلاش مجدد
                    </button>
                </div>
            `;
        }
    }
    
    /**
     * Update selector header
     */
    updateSelectorHeader(status, count) {
        const header = document.querySelector('.template-selector-header h4');
        if (header) {
            const statusDisplay = this.getPurchaseStatusDisplay(status);
            header.textContent = `قالب‌های پیام "${statusDisplay}" (${count})`;
        }
    }
    
    /**
     * Show template selector
     */
    showTemplateSelector() {
        const selector = document.getElementById('template-selector');
        if (selector) {
            selector.style.display = 'block';
        }
    }
    
    /**
     * Hide template selector
     */
    hideTemplateSelector() {
        const selector = document.getElementById('template-selector');
        if (selector) {
            selector.style.display = 'none';
        }
    }
    
    /**
     * Show selection feedback
     */
    showSelectionFeedback(templateId) {
        const feedback = document.createElement('div');
        feedback.className = 'selection-feedback';
        feedback.innerHTML = '<i class="fas fa-check"></i> قالب انتخاب شد';
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
        
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 2000);
    }
    
    /**
     * Toggle template selector visibility
     */
    toggleTemplateSelector() {
        const body = document.getElementById('template-selector-body');
        const btn = document.getElementById('template-collapse-btn');
        
        if (body && btn) {
            const isCollapsed = body.classList.contains('collapsed');
            
            if (isCollapsed) {
                body.classList.remove('collapsed');
                btn.innerHTML = '<i class="fas fa-chevron-up"></i>';
            } else {
                body.classList.add('collapsed');
                btn.innerHTML = '<i class="fas fa-chevron-down"></i>';
            }
        }
    }
    
    /**
     * Change template view mode
     */
    changeTemplateView(viewMode) {
        const container = document.getElementById('template-status-cards');
        const gridBtn = document.getElementById('grid-view-btn');
        const listBtn = document.getElementById('list-view-btn');
        
        if (container) {
            container.className = `template-cards ${viewMode}-view`;
        }
        
        if (gridBtn && listBtn) {
            if (viewMode === 'grid') {
                gridBtn.classList.add('active');
                listBtn.classList.remove('active');
            } else {
                listBtn.classList.add('active');
                gridBtn.classList.remove('active');
            }
        }
    }
    
    /**
     * Utility methods
     */
    getPurchaseStatusDisplay(status) {
        const statusesElement = document.getElementById('purchase-statuses');
        if (statusesElement) {
            try {
                const statuses = JSON.parse(statusesElement.textContent);
                return statuses[status] || status;
            } catch (e) {
                return status;
            }
        }
        return status;
    }
    
    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    debounce(func, wait) {
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
}

// Initialize template manager
const templateManager = new TemplateManager();

// Global functions for backward compatibility
function selectTemplate(id) {
    return templateManager.selectTemplate(id);
}

function previewTemplate(id, event) {
    return templateManager.previewTemplate(id, event);
}

function toggleTemplateSelector() {
    return templateManager.toggleTemplateSelector();
}

function changeTemplateView(viewMode) {
    return templateManager.changeTemplateView(viewMode);
}

function filterTemplateCards() {
    return templateManager.filterTemplateCards();
} 