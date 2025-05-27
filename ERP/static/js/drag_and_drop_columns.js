// drag_and_drop_columns.js
document.addEventListener('DOMContentLoaded', function() {
    // تنظیمات Drag and Drop برای ستون‌های جدول
    function setupColumnDragAndDrop() {
        const tables = document.querySelectorAll('table');
        let draggedColumn = null;

        tables.forEach(table => {
            const tableHeaders = table.querySelectorAll('thead tr th');
            
            // اضافه کردن ویژگی‌های Drag به هدرهای ستون
            tableHeaders.forEach(header => {
                // ستون‌هایی که دارای کلاس مخفی نیستند را قابل جابجایی کنیم
                if (window.getComputedStyle(header).display !== 'none') {
                    header.setAttribute('draggable', 'true');
                    
                    header.addEventListener('dragstart', function(e) {
                        draggedColumn = this;
                        e.dataTransfer.setData('text/plain', this.cellIndex);
                        this.style.opacity = '0.5';
                        
                        // اضافه کردن کلاس برای نمایش حالت کشیدن
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
                        
                        if (draggedColumn !== this) {
                            // جابجایی ستون‌ها
                            swapColumns(draggedColumn.cellIndex, this.cellIndex);
                            
                            // ذخیره ترتیب جدید ستون‌ها
                            saveColumnOrder();
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
            // جابجایی در هدر
            const headerRow = table.querySelector('thead tr');
            const headers = headerRow.querySelectorAll('th');
            const fromHeader = headers[fromIndex];
            const toHeader = headers[toIndex];
            
            if (fromIndex < toIndex) {
                toHeader.after(fromHeader);
            } else {
                toHeader.before(fromHeader);
            }
            
            // جابجایی در بدنه جدول
            const bodyRows = table.querySelectorAll('tbody tr');
            bodyRows.forEach(row => {
                const cells = row.querySelectorAll('td');
                const fromCell = cells[fromIndex];
                const toCell = cells[toIndex];
                
                if (fromIndex < toIndex) {
                    toCell.after(fromCell);
                } else {
                    toCell.before(fromCell);
                }
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
        fetch("{% url 'update_column_order' %}", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify({
                column_order: columnOrder
            })
        }).then(response => response.json())
          .then(data => {
            if (data.status !== 'success') {
                console.error('Error saving column order:', data.message);
            }
        }).catch(error => {
            console.error('Error:', error);
        });
    }

    // تابع برای اعمال ترتیب ذخیره شده ستون‌ها
    function applySavedColumnOrder() {
        // اولویت‌بندی برای دریافت ترتیب ستون‌ها:
        // 1. از localStorage (برای نمایش سریع)
        // 2. از کوکی (در صورت عدم وجود در localStorage)
        // 3. ترتیب پیش‌فرض
        
        let columnOrder = null;
        
        // بررسی localStorage
        const savedOrder = localStorage.getItem('purchaseListColumnOrder');
        if (savedOrder) {
            try {
                columnOrder = JSON.parse(savedOrder);
            } catch (e) {
                console.error('Error parsing saved column order:', e);
            }
        }
        
        // اگر در localStorage نبود، از کوکی بگیریم
        if (!columnOrder) {
            const cookieValue = document.cookie
                .split('; ')
                .find(row => row.startsWith('purchase_list_column_order='));
            
            if (cookieValue) {
                try {
                    columnOrder = JSON.parse(cookieValue.split('=')[1]);
                } catch (e) {
                    console.error('Error parsing cookie column order:', e);
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
                columnOrder.forEach(columnId => {
                    if (cellMap[columnId]) {
                        row.appendChild(cellMap[columnId]);
                    }
                });
            });
        });
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
        // پاک کردن ترتیب ستون‌ها از localStorage
        localStorage.removeItem('purchaseListColumnOrder');
        
        // پاک کردن کوکی‌های مربوط به ترتیب ستون‌ها
        document.cookie = "purchase_list_column_order=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        
        // نمایش پیام موفقیت (اگر تابع وجود داشته باشد)
        if (typeof showSuccessToast === 'function') {
            showSuccessToast('ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد');
        } else {
            alert('ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد');
        }
        
        // بارگذاری مجدد صفحه برای اعمال تغییرات
        window.location.reload();
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