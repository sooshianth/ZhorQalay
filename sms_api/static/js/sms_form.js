// SMS Form Functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log("SMS Form JS loaded");
    
    // Mode switching (Customer Search vs Marketing)
    const customerSearchBtn = document.getElementById('customer-search-btn');
    const directNumberBtn = document.getElementById('direct-number-btn');
    const customerSearchSection = document.getElementById('customer-search-section');
    const directNumberSection = document.getElementById('direct-number-section');
    
    // Initialize elements if they exist
    if (customerSearchBtn && directNumberBtn) {
        console.log("Mode buttons found");
        
        // Customer search button
        customerSearchBtn.addEventListener('click', function() {
            console.log("Customer search button clicked");
            customerSearchBtn.classList.add('selected');
            directNumberBtn.classList.remove('selected');
            customerSearchSection.style.display = 'block';
            directNumberSection.style.display = 'none';
        });
        
        // Marketing button
        directNumberBtn.addEventListener('click', function() {
            console.log("Marketing button clicked");
            directNumberBtn.classList.add('selected');
            customerSearchBtn.classList.remove('selected');
            customerSearchSection.style.display = 'none';
            directNumberSection.style.display = 'block';
        });
    } else {
        console.error("Mode buttons not found!");
        if (!customerSearchBtn) console.error("Customer search button missing");
        if (!directNumberBtn) console.error("Direct number button missing");
    }
    
    // Customer Message Type (Purchase vs Cottage)
    const messageTypeRadios = document.querySelectorAll('input[name="message_type"]');
    const purchaseFields = document.getElementById('purchase-fields');
    const cottageFields = document.getElementById('cottage-fields');
    
    if (messageTypeRadios.length && purchaseFields && cottageFields) {
        console.log("Message type radios found");
        
        // Set initial state
        const checkedRadio = document.querySelector('input[name="message_type"]:checked');
        if (checkedRadio) {
            console.log("Initial radio state:", checkedRadio.value);
            toggleMessageFields(checkedRadio.value);
        } else {
            console.log("No radio checked initially");
        }
        
        // Add change listeners
        messageTypeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                console.log("Radio changed to:", this.value);
                toggleMessageFields(this.value);
            });
        });
    } else {
        console.log("Message type elements not all found", 
                    {radios: messageTypeRadios.length, 
                     purchaseFields: !!purchaseFields, 
                     cottageFields: !!cottageFields});
    }
    
    // Helper function to toggle fields
    function toggleMessageFields(value) {
        if (value === 'purchase') {
            purchaseFields.style.display = 'block';
            cottageFields.style.display = 'none';
        } else if (value === 'cottage') {
            purchaseFields.style.display = 'none';
            cottageFields.style.display = 'block';
        }
    }
    
    // Character counters
    initCharCounter('message', 'char-count');
    initCharCounter('marketing_message', 'marketing-char-count');
    
    // Template buttons
    initTemplateButtons();
    
    // Helper function for character counters
    function initCharCounter(textareaId, counterId) {
        const textarea = document.getElementById(textareaId);
        const counter = document.getElementById(counterId);
        
        if (textarea && counter) {
            console.log(`Character counter found for ${textareaId}`);
            
            // Update counter on load
            counter.textContent = textarea.value.length;
            
            // Add input listener
            textarea.addEventListener('input', function() {
                const count = this.value.length;
                counter.textContent = count;
                
                if (count > 230) {
                    counter.style.color = count > 255 ? 'red' : 'orange';
                } else {
                    counter.style.color = '';
                }
            });
        } else {
            console.log(`Character counter elements not found for ${textareaId}`);
        }
    }
    
    // Helper function for template buttons
    function initTemplateButtons() {
        // Marketing templates
        const marketingTemplates = {
            'promo_1': 'شرکت خدمات بازرگانی جهان تجارت همیشه در کنار شماست. برای مشاوره رایگان در زمینه واردات با ما تماس بگیرید.',
            'promo_2': 'مشتری گرامی، محصولات جدید وارداتی به انبار ما رسیده است. برای اطلاع از قیمت‌ها با ما تماس بگیرید.',
            'promo_3': 'تخفیف ویژه برای مشتریان وفادار! با هر سفارش بیش از 20 تن، 5٪ تخفیف دریافت کنید.'
        };
        
        // Standard templates
        let templates = {};
        try {
            const templatesData = document.getElementById('templates-data');
            if (templatesData) {
                templates = JSON.parse(templatesData.textContent);
                console.log("Templates loaded:", Object.keys(templates).length);
            }
        } catch (error) {
            console.error("Error parsing templates:", error);
        }
        
        // Set up marketing template buttons
        const marketingTemplateButtons = document.querySelectorAll('.marketing-template-btn');
        const marketingMessageTextarea = document.getElementById('marketing_message');
        const marketingCharCount = document.getElementById('marketing-char-count');
        
        if (marketingTemplateButtons.length && marketingMessageTextarea) {
            console.log("Marketing template buttons found:", marketingTemplateButtons.length);
            
            marketingTemplateButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const templateKey = this.dataset.template;
                    console.log("Marketing template clicked:", templateKey);
                    
                    if (marketingTemplates[templateKey]) {
                        marketingMessageTextarea.value = marketingTemplates[templateKey];
                        if (marketingCharCount) {
                            marketingCharCount.textContent = marketingMessageTextarea.value.length;
                        }
                    }
                });
            });
        }
        
        // Set up standard template buttons
        const templateButtons = document.querySelectorAll('.template-btn');
        const messageTextarea = document.getElementById('message');
        const charCount = document.getElementById('char-count');
        
        if (templateButtons.length && messageTextarea) {
            console.log("Template buttons found:", templateButtons.length);
            
            templateButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const templateKey = this.dataset.template;
                    console.log("Template clicked:", templateKey);
                    
                    if (templates[templateKey]) {
                        messageTextarea.value = templates[templateKey];
                        if (charCount) {
                            charCount.textContent = messageTextarea.value.length;
                        }
                    }
                });
            });
        }
        
        // Set up notification type selector
        const notificationTypeSelect = document.getElementById('notification_type');
        
        if (notificationTypeSelect && messageTextarea) {
            notificationTypeSelect.addEventListener('change', function() {
                const selectedType = this.value;
                console.log("Notification type changed:", selectedType);
                
                if (templates[selectedType]) {
                    messageTextarea.value = templates[selectedType];
                    if (charCount) {
                        charCount.textContent = messageTextarea.value.length;
                    }
                }
            });
        }
    }
}); 