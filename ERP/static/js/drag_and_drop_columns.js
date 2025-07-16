// drag_and_drop_columns.js
document.addEventListener('DOMContentLoaded', function() {
    // تنظیمات Drag and Drop برای ستون‌های جدول
    function setupColumnDragAndDrop() {
        const tables = document.querySelectorAll('table');
        let draggedColumn = null;
    
        tables.forEach(table => {
            const tableHeaders = table.querySelectorAll('thead tr th');
    
            tableHeaders.forEach(header => {
                if (window.getComputedStyle(header).display !== 'none') {
                    header.setAttribute('draggable', 'true');
    
                    header.addEventListener('dragstart', function(e) {
                        draggedColumn = this;
                        this.style.opacity = '0.5';
                        this.classList.add('dragging-column');
                    });
    
                    header.addEventListener('dragend', function() {
                        this.style.opacity = '1';
                        this.classList.remove('dragging-column');
                    });
    
                    header.addEventListener('dragover', function(e) {
                        e.preventDefault();
                        this.classList.add('drag-over');
                    });
    
                    header.addEventListener('dragleave', function() {
                        this.classList.remove('drag-over');
                    });
    
                    header.addEventListener('drop', function(e) {
                        e.preventDefault();
                        this.classList.remove('drag-over');
    
                        if (draggedColumn && draggedColumn !== this) {
                            // اینجا هر دو رو از DOM آپدیت بگیر:
                            const headerRow = table.querySelector('thead tr');
                            // فقط visible headers
                            const visibleHeaders = Array.from(headerRow.querySelectorAll('th')).filter(
                                th => window.getComputedStyle(th).display !== 'none'
                            );
    
                            // مطمئن شو هر دو visible هستن
                            if (
                                visibleHeaders.includes(draggedColumn) &&
                                visibleHeaders.includes(this)
                            ) {
                                const fromIndex = draggedColumn.cellIndex;
                                const toIndex = this.cellIndex;
                                swapColumns(fromIndex, toIndex);
                                saveColumnOrder();
                            }
                        }
                    });
                }
            });
        });
    }
    

    // تابع برای جابجایی ستون‌ها
    function swapColumns(fromIndex, toIndex) {
        const tables = document.querySelectorAll('table');
    tables.forEach(table => {
        const headerRow = table.querySelector('thead tr');
        // فیلتر only visible headers
        const visibleHeaders = Array.from(headerRow.querySelectorAll('th')).filter(
            th => window.getComputedStyle(th).display !== 'none'
        );

        // ایندکس واقعی در جدول (cellIndex)
        const fromRealIndex = visibleHeaders[fromIndex]?.cellIndex;
        const toRealIndex = visibleHeaders[toIndex]?.cellIndex;

        // اگر اختلال داشت (مثلاً -1 یا undefined)، هیچی نکن!
        if (
            fromRealIndex === undefined ||
            toRealIndex === undefined
        ) return;

        // جابه‌جایی در thead:
        const headers = headerRow.children;
        const fromHeader = headers[fromRealIndex];
        const toHeader = headers[toRealIndex];
        if (!(fromHeader && toHeader)) return;
        if (fromRealIndex < toRealIndex) {
            toHeader.after(fromHeader);
        } else {
            toHeader.before(fromHeader);
        }

        // جابه‌جایی ردیف‌های tbody:
        const bodyRows = table.querySelectorAll('tbody tr');
        bodyRows.forEach(row => {
            const cells = row.children;
            const fromCell = cells[fromRealIndex];
            const toCell = cells[toRealIndex];
            if (!(fromCell && toCell)) return;
            if (fromRealIndex < toRealIndex) {
                toCell.after(fromCell);
            } else {
                toCell.before(fromCell);
            }
        });
    });
        
        // بروزرسانی فیلترها بعد از جابجایی ستون‌ها
        if (typeof window.tableFilter !== 'undefined' && window.tableFilter) {
            // اعمال مجدد فیلترهای فعال
            setTimeout(() => {
                window.tableFilter.applyAllFilters();
                // بروزرسانی نشانگرهای فیلتر
                if (window.tableFilter.config.enableIndicators) {
                    window.tableFilter.updateFilterIndicators();
                }
            }, 100);
        }
        
        // بعد از جابجایی، واحدها را دوباره اضافه کن
        setTimeout(() => {
            if (typeof addUnitsToHeaders === 'function') {
                addUnitsToHeaders();
            }
        }, 150);
    }

    // تابع برای دریافت ترتیب ستون‌ها از سرور
    function getColumnOrderFromServer() {
        return new Promise((resolve, reject) => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || 
                             document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
            
            fetch('/erp/get_column_order/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    resolve(data.column_order);
                } else {
                    reject(new Error(data.message || 'خطا در دریافت ترتیب ستون‌ها'));
                }
            })
            .catch(error => {
                console.error('Error fetching column order from server:', error);
                reject(error);
            });
        });
    }

    // تابع برای ذخیره ترتیب جدید ستون‌ها
    function saveColumnOrder() {
        const headers = document.querySelectorAll('table thead tr th');
        const columnOrder = [];
        
        headers.forEach(header => {
            const columnClasses = Array.from(header.classList).filter(cls => cls.startsWith('column-'));
            if (columnClasses.length > 0) {
                const columnId = columnClasses[0].replace('column-', '');
                columnOrder.push(columnId);
            }
        });
        
        // ذخیره در localStorage برای نمایش سریع
        localStorage.setItem('purchaseListColumnOrder', JSON.stringify(columnOrder));
        
        // ارسال به سرور برای ذخیره دائمی
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || 
                         document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
        
        fetch('/erp/update_column_order/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                column_order: columnOrder
            })
        }).then(response => response.json())
          .then(data => {
            if (data.status !== 'success') {
                console.error('Error saving column order:', data.message);
                // نمایش پیام خطا به کاربر
                if (typeof showErrorToast === 'function') {
                    showErrorToast('خطا در ذخیره ترتیب ستون‌ها');
                }
            } else {
                // نمایش پیام موفقیت
                if (typeof showSuccessToast === 'function') {
                    showSuccessToast('ترتیب ستون‌ها با موفقیت ذخیره شد');
                }
            }
        }).catch(error => {
            console.error('Error:', error);
            // نمایش پیام خطا به کاربر
            if (typeof showErrorToast === 'function') {
                showErrorToast('خطا در ذخیره ترتیب ستون‌ها');
            }
        });
    }

    // تابع برای اعمال ترتیب ذخیره شده ستون‌ها
    async function applySavedColumnOrder() {
        try {
            // ابتدا از سرور دریافت کن
            let columnOrder = await getColumnOrderFromServer();
            
            // اگر از سرور دریافت نشد، از localStorage استفاده کن
            if (!columnOrder || columnOrder.length === 0) {
                const savedOrder = localStorage.getItem('purchaseListColumnOrder');
                if (savedOrder) {
                    try {
                        columnOrder = JSON.parse(savedOrder);
                    } catch (e) {
                        console.error('Error parsing saved column order:', e);
                        return;
                    }
                }
            }
            
            // اگر هنوز ترتیبی نداریم، از ترتیب فعلی استفاده می‌کنیم
            if (!columnOrder || columnOrder.length === 0) {
                return;
            }
            
            // اعمال ترتیب جدید
            const tableHeaders = document.querySelectorAll('table thead tr th');
            const headersArray = Array.from(tableHeaders);
            const currentOrder = headersArray.map(header => {
                const columnClasses = Array.from(header.classList).filter(cls => cls.startsWith('column-'));
                return columnClasses.length > 0 ? columnClasses[0].replace('column-', '') : null;
            }).filter(Boolean);
            
            // اگر ترتیب یکسان است، نیازی به تغییر نیست
            if (JSON.stringify(columnOrder) === JSON.stringify(currentOrder)) {
                return;
            }
            
            // جابجایی ستون‌ها بر اساس ترتیب ذخیره شده
            const tables = document.querySelectorAll('table');
            tables.forEach(table => {
                const headerRow = table.querySelector('thead tr');
                const headers = Array.from(headerRow.querySelectorAll('th'));
                const bodyRows = table.querySelectorAll('tbody tr');
                
                // ایجاد یک مپ از ستون‌ها بر اساس ID
                const headerMap = {};
                headers.forEach(header => {
                    const columnClasses = Array.from(header.classList).filter(cls => cls.startsWith('column-'));
                    if (columnClasses.length > 0) {
                        const columnId = columnClasses[0].replace('column-', '');
                        headerMap[columnId] = header;
                    }
                });
                
                // مرتب‌سازی هدرها بر اساس ترتیب ذخیره شده
                headerRow.innerHTML = '';
                // ابتدا ستون چک‌باکس را اضافه کن (اگر وجود دارد)
                const checkboxColumn = headers.find(h => h.querySelector('input[type="checkbox"]'));
                if (checkboxColumn) {
                    headerRow.appendChild(checkboxColumn);
                }
                
                // ابتدا ستون‌های مرتب شده را اضافه کن
                columnOrder.forEach(columnId => {
                    if (headerMap[columnId]) {
                        headerRow.appendChild(headerMap[columnId]);
                    }
                });
                
                // سپس ستون‌های نامرتب را در انتها اضافه کن
                currentOrder.forEach(columnId => {
                    if (!columnOrder.includes(columnId) && headerMap[columnId]) {
                        headerRow.appendChild(headerMap[columnId]);
                    }
                });
                
                // مرتب‌سازی سلول‌های هر سطر بر اساس ترتیب جدید
                bodyRows.forEach(row => {
                    const cells = Array.from(row.querySelectorAll('td'));
                    const cellMap = {};
                    
                    cells.forEach((cell, index) => {
                        const columnClasses = Array.from(headers[index].classList).filter(cls => cls.startsWith('column-'));
                        if (columnClasses.length > 0) {
                            const columnId = columnClasses[0].replace('column-', '');
                            cellMap[columnId] = cell;
                        }
                    });
                    
                    // پاک کردن و اضافه کردن مجدد سلول‌ها با ترتیب جدید
                    row.innerHTML = '';
                    // ابتدا ستون چک‌باکس را اضافه کن (اگر وجود دارد)
                    const checkboxCell = cells.find(c => c.querySelector('input[type="checkbox"]'));
                    if (checkboxCell) {
                        row.appendChild(checkboxCell);
                    }
                    
                    // ابتدا سلول‌های مرتب شده را اضافه کن
                    columnOrder.forEach(columnId => {
                        if (cellMap[columnId]) {
                            row.appendChild(cellMap[columnId]);
                        }
                    });
                    
                    // سپس سلول‌های نامرتب را در انتها اضافه کن
                    currentOrder.forEach(columnId => {
                        if (!columnOrder.includes(columnId) && cellMap[columnId]) {
                            row.appendChild(cellMap[columnId]);
                        }
                    });
                });
            });
            
            // بعد از اعمال ترتیب، واحدها را دوباره اضافه کن
            setTimeout(() => {
                if (typeof addUnitsToHeaders === 'function') {
                    addUnitsToHeaders();
                }
            }, 100);
            
        } catch (error) {
            console.error('Error applying saved column order:', error);
            // در صورت خطا، از localStorage استفاده کن
            const savedOrder = localStorage.getItem('purchaseListColumnOrder');
            if (savedOrder) {
                try {
                    const columnOrder = JSON.parse(savedOrder);
                    // اعمال ترتیب از localStorage
                    applyColumnOrderFromArray(columnOrder);
                } catch (e) {
                    console.error('Error parsing localStorage column order:', e);
                }
            }
        }
    }

    // تابع کمکی برای اعمال ترتیب ستون‌ها از آرایه
    function applyColumnOrderFromArray(columnOrder) {
        if (!columnOrder || columnOrder.length === 0) {
            return;
        }
        
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            const headerRow = table.querySelector('thead tr');
            const headers = Array.from(headerRow.querySelectorAll('th'));
            const bodyRows = table.querySelectorAll('tbody tr');
            
            // ایجاد یک مپ از ستون‌ها بر اساس ID
            const headerMap = {};
            headers.forEach(header => {
                const columnClasses = Array.from(header.classList).filter(cls => cls.startsWith('column-'));
                if (columnClasses.length > 0) {
                    const columnId = columnClasses[0].replace('column-', '');
                    headerMap[columnId] = header;
                }
            });
            
            // مرتب‌سازی هدرها بر اساس ترتیب ذخیره شده
            headerRow.innerHTML = '';
            // ابتدا ستون چک‌باکس را اضافه کن (اگر وجود دارد)
            const checkboxColumn = headers.find(h => h.querySelector('input[type="checkbox"]'));
            if (checkboxColumn) {
                headerRow.appendChild(checkboxColumn);
            }
            
            // ابتدا ستون‌های مرتب شده را اضافه کن
            columnOrder.forEach(columnId => {
                if (headerMap[columnId]) {
                    headerRow.appendChild(headerMap[columnId]);
                }
            });
            
            // مرتب‌سازی سلول‌های هر سطر بر اساس ترتیب جدید
            bodyRows.forEach(row => {
                const cells = Array.from(row.querySelectorAll('td'));
                const cellMap = {};
                
                cells.forEach((cell, index) => {
                    const columnClasses = Array.from(headers[index].classList).filter(cls => cls.startsWith('column-'));
                    if (columnClasses.length > 0) {
                        const columnId = columnClasses[0].replace('column-', '');
                        cellMap[columnId] = cell;
                    }
                });
                
                // پاک کردن و اضافه کردن مجدد سلول‌ها با ترتیب جدید
                row.innerHTML = '';
                // ابتدا ستون چک‌باکس را اضافه کن (اگر وجود دارد)
                const checkboxCell = cells.find(c => c.querySelector('input[type="checkbox"]'));
                if (checkboxCell) {
                    row.appendChild(checkboxCell);
                }
                
                // ابتدا سلول‌های مرتب شده را اضافه کن
                columnOrder.forEach(columnId => {
                    if (cellMap[columnId]) {
                        row.appendChild(cellMap[columnId]);
                    }
                });
            });
        });
        
        // بعد از اعمال ترتیب، واحدها را دوباره اضافه کن
        setTimeout(() => {
            if (typeof addUnitsToHeaders === 'function') {
                addUnitsToHeaders();
            }
        }, 100);
    }

    // استایل‌های CSS برای Drag and Drop
    function addDragAndDropStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* استایل‌های مربوط به Drag and Drop ستون‌ها */
            th[draggable="true"] {
                cursor: grab;
                user-select: none;
                position: relative;
            }
            
            th[draggable="true"]:active {
                cursor: grabbing;
            }
            
            .dragging-column {
                background-color: rgba(13, 110, 253, 0.1) !important;
                border: 2px dashed #0d6efd !important;
                opacity: 0.8;
            }
            
            .drag-over {
                background-color: rgba(13, 110, 253, 0.2) !important;
                border-left: 3px solid #0d6efd !important;
            }
            
            /* آیکون نشانگر قابلیت جابجایی */
            th[draggable="true"]::after {
                content: "⣿";
                position: absolute;
                left: 5px;
                top: 50%;
                transform: translateY(-50%);
                font-size: 12px;
                color: #6c757d;
                opacity: 0.5;
            }
            
            th[draggable="true"]:hover::after {
                opacity: 1;
            }
            
            /* انیمیشن برای جابجایی ستون‌ها */
            @keyframes slideIn {
                from { transform: translateX(-10px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            table thead tr th {
                transition: all 0.3s ease;
                animation: slideIn 0.3s ease-out;
            }
        `;
        document.head.appendChild(style);
    }

    // تابع برای بازگرداندن ترتیب ستون‌ها به حالت پیش‌فرض
    function resetColumnOrder() {
        console.log('Resetting column order to default...');
        
        // پاک کردن ترتیب ستون‌ها از localStorage
        localStorage.removeItem('purchaseListColumnOrder');
        
        // پاک کردن کوکی‌های مربوط به ترتیب ستون‌ها
        document.cookie = "purchase_list_column_order=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        
        // نمایش پیام در حال پردازش
        const button = document.getElementById('resetColumnOrderBtn');
        if (button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> در حال بازگردانی...';
            button.disabled = true;
            
            // ارسال درخواست به سرور برای بازگردانی کامل
            fetch('/erp/purchase/reset_column_order/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || 
                                   document.querySelector('input[name="csrfmiddlewaretoken"]')?.value
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Reset response:', data);
                // بازگردانی ظاهر دکمه
                button.innerHTML = originalText;
                button.disabled = false;
                
                // نمایش پیام موفقیت
                if (typeof showSuccessToast === 'function') {
                    showSuccessToast('ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد');
                } else {
                    alert('ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد');
                }
                
                // بارگذاری مجدد صفحه برای اعمال تغییرات
                window.location.reload();
            })
            .catch(error => {
                console.error('Error resetting column order:', error);
                // بازگردانی ظاهر دکمه
                button.innerHTML = originalText;
                button.disabled = false;
                
                // نمایش پیام خطا
                if (typeof showErrorToast === 'function') {
                    showErrorToast('خطا در بازگردانی ترتیب ستون‌ها');
                } else {
                    alert('خطا در بازگردانی ترتیب ستون‌ها');
                }
                
                // بازگذاری مجدد صفحه برای اعمال تغییرات به هر حال
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            });
        } else {
            // اگر دکمه پیدا نشد، مستقیماً صفحه را بارگذاری مجدد کنیم
            window.location.reload();
        }
    }

    // اضافه کردن رویداد کلیک به دکمه بازگردانی ترتیب پیش‌فرض
    const resetColumnOrderBtn = document.getElementById('resetColumnOrderBtn');
    if (resetColumnOrderBtn) {
        resetColumnOrderBtn.addEventListener('click', resetColumnOrder);
    }

    // مقداردهی اولیه
    addDragAndDropStyles();
    applySavedColumnOrder();
    setupColumnDragAndDrop();
});