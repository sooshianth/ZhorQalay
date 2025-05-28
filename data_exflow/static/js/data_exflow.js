/**
 * Data ExFlow - Main JavaScript
 * Handle interactive functionality for data import/export
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initTooltips();
    
    // Initialize dynamic form elements
    initFormElements();
    
    // Initialize file upload handler
    initFileUpload();
    
    // Initialize table functionality
    initTables();
    
    // Initialize data preview
    initDataPreview();
    
    // Initialize field mapping
    initFieldMapping();
});

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    // Initialize all tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialize dynamic form elements
 */
function initFormElements() {
    // Handle dynamic model selection
    const modelSelect = document.getElementById('content_type_id');
    if (modelSelect) {
        modelSelect.addEventListener('change', function() {
            // Show or hide model-specific fields based on selection
            const selectedModel = this.value;
            document.querySelectorAll('.model-specific-fields').forEach(function(el) {
                el.style.display = 'none';
            });
            
            if (selectedModel) {
                const targetElement = document.getElementById('model-fields-' + selectedModel);
                if (targetElement) {
                    targetElement.style.display = 'block';
                }
                
                // Load model fields via AJAX if needed
                loadModelFields(selectedModel);
            }
        });
    }
    
    // Handle export format selection
    const formatSelect = document.getElementById('format');
    if (formatSelect) {
        formatSelect.addEventListener('change', function() {
            // Update UI based on selected format
            const formatInfo = document.getElementById('format-info');
            if (formatInfo) {
                const format = this.value;
                let infoText = '';
                
                if (format === 'xlsx') {
                    infoText = 'فرمت Excel با پشتیبانی از چندین شیت، فرمت‌بندی و فیلترها';
                } else if (format === 'csv') {
                    infoText = 'فرمت CSV ساده با سازگاری بیشتر برای سیستم‌های مختلف';
                } else if (format === 'json') {
                    infoText = 'فرمت JSON برای توسعه‌دهندگان و API';
                }
                
                formatInfo.textContent = infoText;
            }
        });
    }
    
    // Handle export type selection
    const exportType = document.getElementById('export_type');
    if (exportType) {
        exportType.addEventListener('change', function() {
            const exportOptionsContainer = document.getElementById('export-options-container');
            const filterContainer = document.getElementById('filter-container');
            const fieldsContainer = document.getElementById('fields-container');
            
            if (exportOptionsContainer) {
                exportOptionsContainer.style.display = 'block';
                
                if (this.value === 'filtered') {
                    if (filterContainer) filterContainer.style.display = 'block';
                    if (fieldsContainer) fieldsContainer.style.display = 'none';
                } else if (this.value === 'selected') {
                    if (filterContainer) filterContainer.style.display = 'none';
                    if (fieldsContainer) fieldsContainer.style.display = 'block';
                } else {
                    if (filterContainer) filterContainer.style.display = 'none';
                    if (fieldsContainer) fieldsContainer.style.display = 'none';
                }
            }
        });
    }
    
    // Handle add filter button
    const addFilterBtn = document.getElementById('add-filter');
    if (addFilterBtn) {
        const filtersList = document.getElementById('filters-list');
        
        addFilterBtn.addEventListener('click', function() {
            const filterRows = filtersList.querySelectorAll('.filter-row');
            if (filterRows.length > 0) {
                const newRow = filterRows[0].cloneNode(true);
                // Reset values
                const selects = newRow.querySelectorAll('select');
                selects.forEach(select => select.selectedIndex = 0);
                const inputs = newRow.querySelectorAll('input');
                inputs.forEach(input => input.value = '');
                
                // Add event listener to remove button
                const removeBtn = newRow.querySelector('.remove-filter');
                if (removeBtn) {
                    removeBtn.addEventListener('click', function() {
                        if (filtersList.querySelectorAll('.filter-row').length > 1) {
                            newRow.remove();
                        }
                    });
                }
                
                filtersList.appendChild(newRow);
            }
        });
        
        // Add click handler to existing remove buttons
        const removeButtons = filtersList.querySelectorAll('.remove-filter');
        removeButtons.forEach(button => {
            button.addEventListener('click', function() {
                if (filtersList.querySelectorAll('.filter-row').length > 1) {
                    this.closest('.filter-row').remove();
                }
            });
        });
    }
}

/**
 * Initialize file upload functionality
 */
function initFileUpload() {
    const fileInput = document.getElementById('file');
    const fileLabel = document.querySelector('.custom-file-upload');
    const fileInfo = document.querySelector('.file-upload-info');
    
    if (fileInput && fileLabel) {
        // Show file name when file is selected
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                const fileSize = formatFileSize(this.files[0].size);
                
                if (fileInfo) {
                    fileInfo.innerHTML = `<i class="fas fa-file me-1"></i> ${fileName} (${fileSize})`;
                    fileInfo.style.display = 'block';
                }
                
                // Visual feedback
                fileLabel.classList.add('border-primary');
            } else {
                if (fileInfo) {
                    fileInfo.style.display = 'none';
                }
                fileLabel.classList.remove('border-primary');
            }
        });
        
        // Handle drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileLabel.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            fileLabel.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            fileLabel.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            fileLabel.classList.add('border-primary', 'bg-light');
        }
        
        function unhighlight() {
            fileLabel.classList.remove('border-primary', 'bg-light');
        }
        
        fileLabel.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files && files.length) {
                fileInput.files = files;
                // Trigger change event
                const event = new Event('change');
                fileInput.dispatchEvent(event);
            }
        }
    }
}

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 بایت';
    
    const k = 1024;
    const sizes = ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Load model fields via AJAX
 */
function loadModelFields(modelId) {
    // Only load if needed
    if (document.getElementById('model-fields-cache-' + modelId)) {
        return;
    }
    
    // Get model info
    const option = document.querySelector(`option[value="${modelId}"]`);
    console.log('Selected option:', option);
    
    if (!option) {
        console.error('Model option not found');
        return;
    }
    
    const appLabel = option.getAttribute('data-app-label');
    let modelName = option.getAttribute('data-model-name');
    
    // Ensure the first letter of model name is capitalized to match Django's convention
    if (modelName && modelName.length > 0) {
        modelName = modelName.charAt(0).toUpperCase() + modelName.slice(1);
    }
    
    console.log('Model info:', { appLabel, modelName, modelId });
    
    if (!appLabel || !modelName) {
        console.error('Missing model information');
        const fieldsContainer = document.getElementById('model-fields-container');
        if (fieldsContainer) {
            fieldsContainer.innerHTML = `<div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                اطلاعات مدل ناقص است. لطفاً با پشتیبانی تماس بگیرید.
            </div>`;
        }
        return;
    }
    
    // Show loading indicator
    const fieldsContainer = document.getElementById('model-fields-container');
    if (fieldsContainer) {
        fieldsContainer.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">در حال بارگذاری فیلدها...</p></div>';
    }
    
    // Make AJAX request - use direct content_type_id for the most reliable method
    const directApiUrl = `/data-exflow/api/model-fields/?content_type_id=${modelId}`;
    console.log('Fetching model fields directly with content_type_id:', directApiUrl);
    
    // Try with direct fetch method to better debug the issue
    const apiUrl = `/data-exflow/api/model-fields/${appLabel}/${modelName}/`;
    const apiFallbackUrl = `/data-exflow/api/model-fields/${appLabel}/${modelName}`;
    
    // Function to handle the API response
    const handleApiResponse = (response, data) => {
        console.log('Response status:', response.status);
        console.log('Response data:', data);
        
        if (fieldsContainer && data.fields) {
            // Build fields UI
            let html = `<div id="model-fields-cache-${modelId}">`;
            html += '<div class="list-group mb-3">';
            
            data.fields.forEach(field => {
                html += `<div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${field.verbose_name}</strong>
                            <small class="text-muted d-block">${field.name} (${field.type})</small>
                        </div>
                        <div>
                            <span class="badge ${field.required ? 'bg-danger' : 'bg-secondary'}">
                                ${field.required ? 'ضروری' : 'اختیاری'}
                            </span>
                        </div>
                    </div>
                </div>`;
            });
            
            html += '</div></div>';
            fieldsContainer.innerHTML = html;
            
            // If it's an export, also populate the fields list for selection
            const fieldsList = document.getElementById('fields-list');
            if (fieldsList) {
                let fieldsHtml = '';
                data.fields.forEach(field => {
                    fieldsHtml += `
                    <div class="col-md-6 mb-2">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="field_${modelId}_${field.name}" id="field_${modelId}_${field.name}" value="${field.verbose_name}">
                            <label class="form-check-label" for="field_${modelId}_${field.name}">
                                ${field.verbose_name} <small class="text-muted">(${field.name})</small>
                            </label>
                        </div>
                    </div>`;
                });
                fieldsList.innerHTML = fieldsHtml;
            }
            
            // If it's for filtering, also update filter field dropdowns
            const filterFields = document.querySelectorAll('.filter-field');
            if (filterFields.length > 0) {
                let optionsHtml = '<option value="">-- انتخاب فیلد --</option>';
                data.fields.forEach(field => {
                    optionsHtml += `<option value="${field.name}">${field.verbose_name}</option>`;
                });
                
                filterFields.forEach(select => {
                    select.innerHTML = optionsHtml;
                });
            }
        } else if (fieldsContainer) {
            fieldsContainer.innerHTML = `<div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                هیچ فیلدی برای این مدل یافت نشد.
            </div>`;
        }
    };
    
    // Function to handle errors
    const handleApiError = (error) => {
        console.error('Error loading model fields:', error);
        if (fieldsContainer) {
            fieldsContainer.innerHTML = `<div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                خطا در بارگذاری فیلدها: ${error.message}
                <div class="mt-2">
                    <small class="text-muted">راه حل: از وجود مدل در سیستم اطمینان حاصل کنید یا صفحه را مجدداً بارگذاری نمایید.</small>
                </div>
                <div class="mt-2 d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" id="try-fallback-btn">
                        تلاش با URL بدون اسلش
                    </button>
                    <button class="btn btn-sm btn-primary" id="try-url-btn">
                        تلاش با URL معمولی
                    </button>
                </div>
            </div>`;
            
            // Add click handler for fallback button
            const fallbackBtn = fieldsContainer.querySelector('#try-fallback-btn');
            if (fallbackBtn) {
                fallbackBtn.addEventListener('click', function() {
                    console.log('Trying fallback URL:', apiFallbackUrl);
                    fieldsContainer.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">در حال تلاش مجدد...</p></div>';
                    
                    fetch(apiFallbackUrl)
                        .then(response => {
                            if (!response.ok) {
                                return response.json().then(data => {
                                    throw new Error(data.error || `Network response was not ok: ${response.status} ${response.statusText}`);
                                }).catch(err => {
                                    throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                                });
                            }
                            return response.json();
                        })
                        .then(data => handleApiResponse({ status: 200 }, data))
                        .catch(error => {
                            console.error('Error on fallback URL:', error);
                            fieldsContainer.innerHTML = `<div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                خطا در بارگذاری فیلدها با URL جایگزین: ${error.message}
                            </div>`;
                        });
                });
            }
            
            // Add click handler for direct API button
            const urlBtn = fieldsContainer.querySelector('#try-url-btn');
            if (urlBtn) {
                urlBtn.addEventListener('click', function() {
                    console.log('Trying URL API path:', apiUrl);
                    fieldsContainer.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">در حال تلاش با URL معمولی...</p></div>';
                    
                    fetch(apiUrl)
                        .then(response => {
                            if (!response.ok) {
                                return response.json().then(data => {
                                    throw new Error(data.error || `Network response was not ok: ${response.status} ${response.statusText}`);
                                }).catch(err => {
                                    throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                                });
                            }
                            return response.json();
                        })
                        .then(data => handleApiResponse({ status: 200 }, data))
                        .catch(error => {
                            console.error('Error on URL API path:', error);
                            fieldsContainer.innerHTML = `<div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                خطا در بارگذاری فیلدها با URL معمولی: ${error.message}
                            </div>`;
                        });
                });
            }
        }
    };
    
    // Make the first API request with direct method
    console.log('AJAX DEBUG: Starting API request to:', directApiUrl);
    fetch(directApiUrl)
        .then(response => {
            console.log('AJAX DEBUG: Response received:', {
                status: response.status,
                statusText: response.statusText,
                url: response.url,
                ok: response.ok,
                headers: {
                    contentType: response.headers.get('content-type')
                }
            });
            
            if (!response.ok) {
                console.log('AJAX DEBUG: Response not OK, trying to get error details');
                return response.text().then(text => {
                    console.log('AJAX DEBUG: Error response text:', text);
                    try {
                        const data = JSON.parse(text);
                        console.log('AJAX DEBUG: Parsed error JSON:', data);
                        throw new Error(data.error || `Network response was not ok: ${response.status} ${response.statusText}`);
                    } catch (jsonError) {
                        console.log('AJAX DEBUG: Could not parse JSON from error:', jsonError);
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                });
            }
            
            console.log('AJAX DEBUG: Response OK, parsing JSON');
            return response.text().then(text => {
                console.log('AJAX DEBUG: Raw response text:', text.substring(0, 200) + '...');
                try {
                    return JSON.parse(text);
                } catch (jsonError) {
                    console.log('AJAX DEBUG: JSON parse error:', jsonError);
                    throw new Error('Invalid JSON response');
                }
            });
        })
        .then(data => {
            console.log('AJAX DEBUG: Data received:', data);
            handleApiResponse({ status: 200 }, data);
        })
        .catch(error => {
            console.log('AJAX DEBUG: Fetch error:', error);
            handleApiError(error);
        });
}

/**
 * Initialize table functionality
 */
function initTables() {
    // Make tables responsive
    document.querySelectorAll('.table-container').forEach(function(container) {
        if (container.scrollWidth > container.clientWidth) {
            container.classList.add('table-responsive');
        }
    });
}

/**
 * Initialize data preview
 */
function initDataPreview() {
    // Check if new edit system is present
    const toggleEditBtn = document.getElementById('toggleEditMode');
    if (toggleEditBtn) {
        // New edit system is present, don't initialize old system
        console.log('🔄 New edit system detected, skipping old initDataPreview');
        return;
    }
    
    // Handle editable cells in preview (legacy system)
    document.querySelectorAll('.editable-cell').forEach(function(cell) {
        cell.addEventListener('click', function() {
            // Only proceed if not already editing
            if (this.querySelector('input')) return;
            
            const value = this.textContent.trim();
            const row = this.getAttribute('data-row');
            const column = this.getAttribute('data-column');
            const sessionId = this.getAttribute('data-session-id');
            
            // Create input element
            const input = document.createElement('input');
            input.type = 'text';
            input.value = value;
            input.className = 'form-control form-control-sm';
            
            // Replace cell content with input
            this.textContent = '';
            this.appendChild(input);
            input.focus();
            
            // Handle input blur (save)
            input.addEventListener('blur', function() {
                saveCell(row, column, input.value, sessionId, cell);
            });
            
            // Handle enter key
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    saveCell(row, column, input.value, sessionId, cell);
                }
            });
        });
    });
}

/**
 * Save cell data via AJAX
 */
function saveCell(row, column, value, sessionId, cellElement) {
    // Show loading state
    cellElement.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"></div>';
    
    // Prepare CSRF token
    const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
    
    // Make AJAX request
    fetch(`/data-exflow/api/edit-cell/${sessionId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            row: parseInt(row),
            column: column,
            value: value
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Update cell with new value
            cellElement.textContent = value;
            
            // Show success indicator briefly
            const originalBackground = cellElement.style.backgroundColor;
            cellElement.style.backgroundColor = '#d4edda';
            setTimeout(function() {
                cellElement.style.backgroundColor = originalBackground;
            }, 1000);
        } else {
            // Show error
            cellElement.textContent = value;
            cellElement.style.backgroundColor = '#f8d7da';
            setTimeout(function() {
                cellElement.style.backgroundColor = '';
            }, 2000);
        }
    })
    .catch(error => {
        console.error('Error saving cell:', error);
        cellElement.textContent = value;
        cellElement.style.backgroundColor = '#f8d7da';
    });
}

/**
 * Initialize field mapping UI
 */
function initFieldMapping() {
    // Handle mapping form
    const mappingForm = document.getElementById('mapping-form');
    if (!mappingForm) return;
    
    // Handle identifier field selection
    const identifierFieldRadios = document.querySelectorAll('input[name="identifier_field"]');
    identifierFieldRadios.forEach(function(radio) {
        radio.addEventListener('change', function() {
            // Update UI to highlight selected identifier
            document.querySelectorAll('.mapping-field').forEach(function(field) {
                field.classList.remove('border-primary', 'bg-light');
            });
            
            if (this.checked) {
                const fieldContainer = this.closest('.mapping-field');
                if (fieldContainer) {
                    fieldContainer.classList.add('border-primary', 'bg-light');
                }
            }
        });
    });
    
    // Handle mapping dropdown changes
    document.querySelectorAll('.mapping-select').forEach(function(select) {
        select.addEventListener('change', function() {
            const columnName = this.getAttribute('data-column');
            const identifierRadio = document.querySelector(`input[name="identifier_field"][value="${columnName}"]`);
            
            // Only enable identifier selection if mapped to a field
            if (identifierRadio) {
                if (this.value && this.value !== 'ignore') {
                    identifierRadio.disabled = false;
                    identifierRadio.closest('.form-check').classList.remove('text-muted');
                } else {
                    identifierRadio.disabled = true;
                    identifierRadio.checked = false;
                    identifierRadio.closest('.form-check').classList.add('text-muted');
                }
            }
        });
    });
    
    // Auto-suggest mappings
    document.getElementById('auto-suggest-mappings').addEventListener('click', function(e) {
        e.preventDefault();
        
        document.querySelectorAll('.mapping-select').forEach(function(select) {
            const columnName = select.getAttribute('data-column').toLowerCase();
            
            // Find the best match
            let bestMatch = null;
            let bestScore = 0;
            
            Array.from(select.options).forEach(function(option) {
                if (option.value && option.value !== 'ignore') {
                    const fieldName = option.value.toLowerCase();
                    const displayName = option.textContent.trim().toLowerCase();
                    
                    // Calculate similarity score
                    let score = 0;
                    
                    // Exact match gets highest score
                    if (fieldName === columnName) {
                        score = 100;
                    } 
                    // Field name contains column name
                    else if (fieldName.includes(columnName)) {
                        score = 80;
                    }
                    // Column name contains field name
                    else if (columnName.includes(fieldName)) {
                        score = 70;
                    }
                    // Display name matches
                    else if (displayName === columnName) {
                        score = 60;
                    }
                    // Display name contains column name
                    else if (displayName.includes(columnName)) {
                        score = 50;
                    }
                    // Column name contains display name
                    else if (columnName.includes(displayName)) {
                        score = 40;
                    }
                    
                    if (score > bestScore) {
                        bestScore = score;
                        bestMatch = option.value;
                    }
                }
            });
            
            // Set the best match if score is above threshold
            if (bestScore > 30) {
                select.value = bestMatch;
                
                // Trigger change event
                const event = new Event('change');
                select.dispatchEvent(event);
            }
        });
        
        // Suggest primary identifier
        const identifierSuggestions = [
            'id', 'pk', 'uuid', 'code', 'number', 'identifier', 'email', 'username', 'phone'
        ];
        
        for (const suggestion of identifierSuggestions) {
            const identifierRadio = document.querySelector(`input[name="identifier_field"][value*="${suggestion}"]`);
            if (identifierRadio && !identifierRadio.disabled) {
                identifierRadio.checked = true;
                
                // Trigger change event
                const event = new Event('change');
                identifierRadio.dispatchEvent(event);
                
                break;
            }
        }
    });
} 