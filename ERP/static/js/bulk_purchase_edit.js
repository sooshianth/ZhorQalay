/**
 * نمایش پیام دیباگ در کنسول و در صفحه
 * @param {string} message - پیام برای نمایش
 */
function debugLog(message) {
    console.log(message);
    
    // بررسی وجود عنصر debugLog
    const debugLogElement = document.getElementById('debugLog');
    if (debugLogElement) {
        const logEntry = document.createElement('div');
        logEntry.className = 'debug-log-entry';
        
        // افزودن زمان به پیام
        const now = new Date();
        const timeStr = now.toLocaleTimeString('fa-IR');
        
        logEntry.innerHTML = `<span class="debug-log-time">[${timeStr}]</span> ${message}`;
        debugLogElement.appendChild(logEntry);
        
        // اسکرول به آخرین پیام
        debugLogElement.scrollTop = debugLogElement.scrollHeight;
        
        // حذف پیام‌های قدیمی اگر تعداد پیام‌ها از 100 بیشتر شد
        const entries = debugLogElement.getElementsByClassName('debug-log-entry');
        if (entries.length > 100) {
            debugLogElement.removeChild(entries[0]);
        }
    }
}

// توابع و متغیرهای عمومی 
let selectedPurchases = [];
let allPurchases = [];
let notFoundPurchases = [];

// نمایش لودینگ
function showLoading() {
    debugLog('شروع بارگذاری...');
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
}

// مخفی کردن لودینگ
function hideLoading() {
    debugLog('پایان بارگذاری');
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

// نمایش پیام خطا
function showError(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-3';
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // نمایش در بالای صفحه
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // حذف خودکار بعد از 8 ثانیه
    setTimeout(() => {
        alertDiv.remove();
    }, 8000);
    
    // لاگ کردن خطا
    debugLog(`خطا: ${message}`);
}

// تنظیم تعداد انتخاب شده‌ها
function updateSelectedCount() {
    const selectedCountElement = document.getElementById('selectedCount');
    selectedCountElement.textContent = selectedPurchases.length;
    
    // فعال/غیرفعال کردن دکمه ویرایش
    const editButton = document.querySelector('[data-bs-target="#editModal"]');
    if (selectedPurchases.length > 0) {
        editButton.disabled = false;
    } else {
        editButton.disabled = true;
    }
}

// انتخاب/عدم انتخاب همه
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.purchase-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
        
        const purchaseId = checkbox.value;
        
        if (selectAllCheckbox.checked) {
            // اضافه کردن به لیست انتخاب شده‌ها اگر از قبل وجود نداشت
            if (!selectedPurchases.includes(purchaseId)) {
                selectedPurchases.push(purchaseId);
            }
            
            // اضافه کردن کلاس انتخاب شده به ردیف
            checkbox.closest('tr').classList.add('selected');
        } else {
            // حذف از لیست انتخاب شده‌ها
            selectedPurchases = selectedPurchases.filter(id => id !== purchaseId);
            
            // حذف کلاس انتخاب شده از ردیف
            checkbox.closest('tr').classList.remove('selected');
        }
    });
    
    updateSelectedCount();
}

// فعال/غیرفعال کردن فیلدهای فرم
function toggleFieldEnabled(fieldName) {
    const checkbox = document.getElementById(`${fieldName}Check`);
    const field = document.getElementById(`${fieldName}Field`);
    
    field.disabled = !checkbox.checked;
    
    if (checkbox.checked) {
        field.focus();
    }
}

// دانلود فایل نمونه اکسل
function downloadSampleExcel() {
    // ایجاد یک شی ورک‌بوک جدید
    const wb = XLSX.utils.book_new();
    
    // داده‌های نمونه
    const data = [
        { 'شماره_خرید': '1234567' },
        { 'شماره_خرید': '2345678' },
        { 'شماره_خرید': '3456789' }
    ];
    
    // تبدیل داده‌ها به شیت
    const ws = XLSX.utils.json_to_sheet(data);
    
    // اضافه کردن شیت به ورک‌بوک
    XLSX.utils.book_append_sheet(wb, ws, 'نمونه');
    
    // دانلود فایل
    XLSX.writeFile(wb, 'نمونه_فایل_ویرایش_فله_ای.xlsx');
}

// آپلود فایل اکسل
function uploadExcel(input) {
    if (!input.files || input.files.length === 0) {
        showError('لطفاً یک فایل اکسل انتخاب کنید.');
        return;
    }
    
    const file = input.files[0];
    
    // بررسی پسوند فایل
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        showError('فرمت فایل باید Excel (.xlsx یا .xls) باشد.');
        return;
    }
    
    showLoading();
    
    try {
        debugLog('شروع خواندن فایل اکسل: ' + file.name);
        
        // خواندن فایل اکسل محلی
        const reader = new FileReader();
        
        reader.onload = function(e) {
            try {
                debugLog('فایل اکسل خوانده شد، در حال پردازش...');
                
                // خواندن فایل اکسل
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, {type: 'array'});
                
                // گرفتن شیت اول
                const firstSheetName = workbook.SheetNames[0];
                if (!firstSheetName) {
                    hideLoading();
                    showError('فایل اکسل بدون شیت است.');
                    return;
                }
                
                debugLog('نام شیت: ' + firstSheetName);
                const worksheet = workbook.Sheets[firstSheetName];
                
                // تبدیل به آرایه‌ای از اشیاء
                const excelData = XLSX.utils.sheet_to_json(worksheet);
                debugLog('تعداد ردیف‌های خوانده شده: ' + excelData.length);
                
                if (excelData.length === 0) {
                    hideLoading();
                    showError('فایل اکسل خالی است یا داده‌های قابل خواندن ندارد.');
                    return;
                }
                
                // نمایش ستون‌های موجود
                const firstRow = excelData[0];
                const columns = Object.keys(firstRow);
                debugLog('ستون‌های یافت شده: ' + columns.join(', '));
                
                // بررسی وجود ستون شماره خرید
                const hasRequiredColumn = columns.some(col => 
                    col === "شماره_خرید" || col === "شماره خرید" || col === "purchase_number"
                );
                
                if (!hasRequiredColumn) {
                    hideLoading();
                    showError('فایل اکسل باید شامل ستونی با عنوان "شماره_خرید" یا "شماره خرید" یا "purchase_number" باشد.');
                    return;
                }
                
                // استخراج شماره‌های خرید
                const purchaseNumbers = excelData.map(row => {
                    let number = row["شماره_خرید"] || row["شماره خرید"] || row["purchase_number"];
                    // تبدیل به رشته
                    return number ? String(number) : null;
                }).filter(Boolean); // حذف مقادیر خالی
                
                debugLog('تعداد شماره خریدهای یافت شده: ' + purchaseNumbers.length);
                
                if (purchaseNumbers.length === 0) {
                    hideLoading();
                    showError('هیچ شماره خریدی در فایل اکسل یافت نشد.');
                    return;
                }
                
                // محدود کردن تعداد برای جلوگیری از ارسال داده‌های بزرگ
                const maxSendCount = 1000;
                let sendNumbers = purchaseNumbers;
                if (purchaseNumbers.length > maxSendCount) {
                    sendNumbers = purchaseNumbers.slice(0, maxSendCount);
                    debugLog(`تعداد شماره خریدها زیاد است. فقط ${maxSendCount} مورد اول ارسال می‌شود.`);
                }
                
                // ارسال آیتم‌ها به سرور
                sendPurchaseNumbersToServer(sendNumbers);
                
            } catch (error) {
                hideLoading();
                debugLog('خطا در پردازش فایل اکسل: ' + error.message);
                showError('خطا در خواندن فایل اکسل: ' + error.message);
            }
        };
        
        reader.onerror = function() {
            hideLoading();
            debugLog('خطا در خواندن فایل: ' + reader.error.message);
            showError('خطا در خواندن فایل.');
        };
        
        reader.readAsArrayBuffer(file);
        
    } catch (error) {
        hideLoading();
        debugLog('خطای کلی در آپلود فایل: ' + error.message);
        showError('خطا در پردازش فایل: ' + error.message);
    }
}

// ارسال شماره‌های خرید به سرور
function sendPurchaseNumbersToServer(purchaseNumbers) {
    showLoading();
    debugLog('در حال ارسال شماره‌های خرید به سرور...');
    debugLog(`تعداد شماره‌های خرید برای ارسال: ${purchaseNumbers.length}`);
    
    // ذخیره توکن CSRF برای استفاده‌های بعدی
    const csrftoken = getCsrfToken();
    
    // مسیر صحیح API با ساختار URL درست
    fetch('/erp/bulk-purchase-edit/upload-excel/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({
            purchase_numbers: purchaseNumbers
        })
    })
    .then(response => {
        debugLog(`پاسخ سرور دریافت شد: وضعیت ${response.status}`);
        
        if (!response.ok) {
            throw new Error(`خطای سرور: ${response.status}`);
        }
        
        return response.json();
    })
    .then(data => {
        hideLoading();
        debugLog('پاسخ سرور با موفقیت پردازش شد');
        
        if (data.success) {
            debugLog(`تعداد خریدهای یافت شده: ${data.purchase_data.length}`);
            
            // نمایش پیام موفقیت
            showSuccess(`${data.purchase_data.length} خرید با موفقیت بارگذاری شد.`);
            
            // پر کردن جدول با اطلاعات
            if (data.purchase_data && data.purchase_data.length > 0) {
                populateTable(data.purchase_data);
                
                // مخفی کردن ناحیه آپلود
                document.getElementById('uploadArea').style.display = 'none';
                
                // نمایش جدول
                document.getElementById('purchaseTableContainer').style.display = 'block';
                
                // نمایش دکمه خروجی اکسل
                document.getElementById('exportButton').style.display = 'inline-block';
                
                // ذخیره داده‌ها
                allPurchases = data.purchase_data;
                notFoundPurchases = data.not_found || [];
                
                // نمایش خریدهای یافت نشده
                if (notFoundPurchases.length > 0) {
                    showNotFoundPurchases(notFoundPurchases);
                }
            }
            
            // نمایش خریدهایی که پیدا نشدند
            if (data.not_found && data.not_found.length > 0) {
                debugLog(`تعداد خریدهای پیدا نشده: ${data.not_found.length}`);
                showWarning(`${data.not_found.length} شماره خرید در سیستم پیدا نشد: ${data.not_found.join(', ')}`);
            }
        } else {
            debugLog('پاسخ سرور: عدم موفقیت');
            showError(data.message || 'خطا در بارگذاری خریدها. لطفاً دوباره تلاش کنید.');
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error sending purchase numbers:', error);
        debugLog(`خطا در ارسال اطلاعات: ${error.message}`);
        showError('خطا در ارتباط با سرور. لطفاً اتصال اینترنت خود را بررسی کرده و دوباره تلاش کنید.');
    });
}

// دریافت توکن CSRF از کوکی
function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

// پر کردن جدول با داده‌های دریافتی
function populateTable(purchaseData) {
    const tableBody = document.querySelector('#purchaseTable tbody');
    tableBody.innerHTML = '';
    
    purchaseData.forEach(purchase => {
        const row = document.createElement('tr');
        
        // اضافه کردن چک‌باکس
        row.innerHTML = `
            <td>
                <div class="form-check">
                    <input class="form-check-input purchase-checkbox" type="checkbox" value="${purchase.id}" onchange="togglePurchase(this)">
                </div>
            </td>
            <td>${purchase.purchase_number}</td>
            <td>${purchase.invoice_id}</td>
            <td>${purchase.customer_name}</td>
            <td><span class="badge bg-info">${purchase.state}</span></td>
            <td>${purchase.cargo_name ? purchase.cargo_name + (purchase.cargo_country ? ' (' + purchase.cargo_country + ')' : '') : '-'}</td>
            <td>${formatNumber(purchase.company_price)} ریال</td>
            <td>${formatNumber(purchase.customer_price)} ریال</td>
            <td>${formatNumber(purchase.order_weight)} کیلوگرم</td>
            <td>${formatNumber(purchase.delivered_weight)} کیلوگرم</td>
            <td>${purchase.is_factored ? '<span class="badge bg-success">فاکتور صادر شده</span>' : '<span class="badge bg-warning">فاکتور صادر نشده</span>'}</td>
            <td>
                <button class="btn btn-sm btn-info" onclick="viewPurchaseDetails(${purchase.id})">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

// نمایش خریدهای یافت نشده
function showNotFoundPurchases(notFoundList) {
    const container = document.getElementById('notFoundContainer');
    const listElement = document.getElementById('notFoundList');
    
    listElement.innerHTML = '';
    
    notFoundList.forEach(purchaseNumber => {
        const span = document.createElement('span');
        span.textContent = purchaseNumber;
        listElement.appendChild(span);
    });
    
    container.style.display = 'block';
}

// انتخاب/عدم انتخاب یک خرید
function togglePurchase(checkbox) {
    const purchaseId = checkbox.value;
    const row = checkbox.closest('tr');
    
    if (checkbox.checked) {
        // اضافه کردن به لیست انتخاب شده‌ها
        if (!selectedPurchases.includes(purchaseId)) {
            selectedPurchases.push(purchaseId);
        }
        
        // اضافه کردن کلاس انتخاب شده به ردیف
        row.classList.add('selected');
    } else {
        // حذف از لیست انتخاب شده‌ها
        selectedPurchases = selectedPurchases.filter(id => id !== purchaseId);
        
        // حذف کلاس انتخاب شده از ردیف
        row.classList.remove('selected');
        
        // به‌روزرسانی وضعیت چک‌باکس "انتخاب همه"
        document.getElementById('selectAll').checked = false;
    }
    
    updateSelectedCount();
}

// مشاهده جزئیات خرید
function viewPurchaseDetails(purchaseId) {
    showLoading();
    
    fetch(`/erp/bulk-purchase-edit/details/${purchaseId}/`)
        .then(response => response.json())
        .then(response => {
            hideLoading();
            
            if (response.success) {
                const purchase = response.data;
                
                // ایجاد محتوای مدال
                const modalBody = document.getElementById('purchaseDetailModalBody');
                modalBody.innerHTML = `
                    <div class="row">
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">شماره خرید:</div>
                            <div class="detail-value">${purchase.purchase_number}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">کد سیستمی:</div>
                            <div class="detail-value">${purchase.invoice_id}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">نام مشتری:</div>
                            <div class="detail-value">${purchase.customer_name}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">وضعیت:</div>
                            <div class="detail-value"><span class="badge bg-info">${purchase.state}</span></div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">محصول:</div>
                            <div class="detail-value">${purchase.cargo_name ? purchase.cargo_name + (purchase.cargo_country ? ' (' + purchase.cargo_country + ')' : '') : '-'}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">فی خرید:</div>
                            <div class="detail-value">${formatNumber(purchase.company_price)} ریال</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">فی فروش:</div>
                            <div class="detail-value">${formatNumber(purchase.customer_price)} ریال</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">وزن سفارش:</div>
                            <div class="detail-value">${formatNumber(purchase.order_weight)} کیلوگرم</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">وزن تحویلی:</div>
                            <div class="detail-value">${formatNumber(purchase.delivered_weight)} کیلوگرم</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">مبلغ پرداختی:</div>
                            <div class="detail-value">${formatNumber(purchase.amount_paid)} ریال</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">روش پرداخت:</div>
                            <div class="detail-value">${purchase.payment_method || '-'}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">تاریخ ثبت:</div>
                            <div class="detail-value">${purchase.created_at}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">نوع اختلاف:</div>
                            <div class="detail-value">${purchase.extelaf_type || '-'}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">وزن اختلاف:</div>
                            <div class="detail-value">${purchase.extelaf_weight ? formatNumber(purchase.extelaf_weight) + ' کیلوگرم' : '-'}</div>
                        </div>
                        <div class="col-md-3 mb-3">
                            <div class="detail-label">مبلغ اختلاف:</div>
                            <div class="detail-value">${purchase.extelaf_amount ? formatNumber(purchase.extelaf_amount) + ' ریال' : '-'}</div>
                        </div>
                        <div class="col-md-6 mb-3">
                            <div class="detail-label">آدرس:</div>
                            <div class="detail-value">${purchase.address || '-'}</div>
                        </div>
                        <div class="col-md-6 mb-3">
                            <div class="detail-label">توضیحات:</div>
                            <div class="detail-value">${purchase.description || '-'}</div>
                        </div>
                        <div class="col-md-6 mb-3">
                            <div class="detail-label">وضعیت فاکتور:</div>
                            <div class="detail-value">${purchase.is_factored ? '<span class="badge bg-success">فاکتور صادر شده</span>' : '<span class="badge bg-warning">فاکتور صادر نشده</span>'}</div>
                        </div>
                        <div class="col-md-12 mb-3">
                            <div class="detail-label">کارشناسان فروش:</div>
                            <div class="detail-value">${purchase.sales_agents && purchase.sales_agents.length > 0 ? purchase.sales_agents.map(agent => agent.name).join('، ') : '-'}</div>
                        </div>
                    </div>
                    <div class="mt-3">
                        <a href="/erp/purchase_CRUD/${purchase.id}/" class="btn btn-primary">
                            <i class="fas fa-edit me-1"></i> ویرایش
                        </a>
                    </div>
                `;
                
                // تنظیم عنوان مدال
                document.getElementById('purchaseDetailModalLabel').textContent = `جزئیات خرید ${purchase.purchase_number}`;
                
                // نمایش مدال
                const purchaseDetailModal = new bootstrap.Modal(document.getElementById('purchaseDetailModal'));
                purchaseDetailModal.show();
            } else {
                showError(response.message);
            }
        })
        .catch(error => {
            hideLoading();
            showError('خطا در دریافت اطلاعات: ' + error.message);
        });
}

// اعمال ویرایش فله‌ای
function applyBulkEdit() {
    if (selectedPurchases.length === 0) {
        showError('لطفاً حداقل یک خرید را انتخاب کنید.');
        return;
    }
    
    // جمع‌آوری تغییرات
    const changes = {};
    const changeLabels = [];
    
    // بررسی هر فیلد فعال شده
    const fields = [
        { name: 'state', label: 'وضعیت' },
        { name: 'cargo', label: 'محصول' },
        { name: 'companyPrice', label: 'فی خرید', dbField: 'company_price' },
        { name: 'customerPrice', label: 'فی فروش', dbField: 'customer_price' },
        { name: 'orderWeight', label: 'وزن سفارش', dbField: 'order_weight' },
        { name: 'deliveredWeight', label: 'وزن تحویلی', dbField: 'delivered_weight' },
        { name: 'amountPaid', label: 'مبلغ پرداختی', dbField: 'amount_paid' },
        { name: 'paymentMethod', label: 'روش پرداخت', dbField: 'payment_method' },
        { name: 'extelafType', label: 'نوع اختلاف', dbField: 'extelaf_type' },
        { name: 'extelafWeight', label: 'وزن اختلاف', dbField: 'extelaf_weight' },
        { name: 'extelafAmount', label: 'مبلغ اختلاف', dbField: 'extelaf_amount' },
        { name: 'address', label: 'آدرس' },
        { name: 'description', label: 'توضیحات' },
        { name: 'salesAgent', label: 'کارشناس فروش', dbField: 'sales_agent' },
        { name: 'isFactored', label: 'وضعیت فاکتور', dbField: 'is_factored' }
    ];
    
    fields.forEach(field => {
        const checkbox = document.getElementById(`${field.name}Check`);
        
        if (checkbox && checkbox.checked) {
            const fieldElement = document.getElementById(`${field.name}Field`);
            let value = fieldElement.value;
            
            // اضافه کردن به تغییرات
            const dbField = field.dbField || field.name;
            
            // تبدیل مقادیر مخصوص به نوع مناسب
            if (field.name === 'isFactored') {
                // فقط مقادیر true یا false را به صورت boolean ارسال کن
                if (value === 'true') {
                    value = true;
                } else if (value === 'false') {
                    value = false;
                } else {
                    // اگر مقدار معتبر نیست، آن را ارسال نکن
                    return;
                }
            } else if (['companyPrice', 'customerPrice', 'orderWeight', 'deliveredWeight', 'amountPaid', 'extelafWeight', 'extelafAmount'].includes(field.name) && value !== '') {
                value = Number(value);
            }
            
            changes[dbField] = value;
            
            // خاص برای نمایش وضعیت
            if (field.name === 'state') {
                const stateLabel = fieldElement.options[fieldElement.selectedIndex].text;
                changeLabels.push(`${field.label}: ${stateLabel}`);
            } 
            // خاص برای نمایش محصول
            else if (field.name === 'cargo' && value) {
                const cargoLabel = fieldElement.options[fieldElement.selectedIndex].text;
                changeLabels.push(`${field.label}: ${cargoLabel}`);
            } 
            // خاص برای نمایش کارشناس فروش
            else if (field.name === 'salesAgent' && value) {
                const agentLabel = fieldElement.options[fieldElement.selectedIndex].text;
                changeLabels.push(`افزودن ${field.label}: ${agentLabel}`);
            }
            // خاص برای نمایش وضعیت فاکتور
            else if (field.name === 'isFactored') {
                const isFactoredText = value === true ? 'فاکتور صادر شده' : 'فاکتور صادر نشده';
                changeLabels.push(`${field.label}: ${isFactoredText}`);
            }
            // فیلدهای عمومی
            else {
                changeLabels.push(`${field.label}: ${value}`);
            }
        }
    });
    
    // بررسی وجود تغییر
    if (Object.keys(changes).length === 0) {
        showError('لطفاً حداقل یک فیلد را برای تغییر انتخاب کنید.');
        return;
    }
    
    // مخفی کردن مدال ویرایش
    bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
    
    // نمایش مدال تایید
    document.getElementById('purchaseCount').textContent = selectedPurchases.length;
    document.getElementById('changesList').innerHTML = changeLabels.map(change => `<div>${change}</div>`).join('');
    
    // تنظیم رویداد برای دکمه تایید
    document.getElementById('confirmChangesBtn').onclick = () => confirmBulkEdit(changes);
    
    // نمایش مدال تایید
    new bootstrap.Modal(document.getElementById('confirmModal')).show();
}

// تایید و اعمال تغییرات فله‌ای
function confirmBulkEdit(changes) {
    showLoading();
    
    // مخفی کردن مدال تایید
    bootstrap.Modal.getInstance(document.getElementById('confirmModal')).hide();
    
    // لاگ اطلاعات ارسالی برای دیباگ
    debugLog('در حال ارسال تغییرات به سرور...');
    debugLog('داده‌های ارسالی: ' + JSON.stringify({
        purchase_ids: selectedPurchases,
        changes: changes
    }, null, 2));
    
    // ارسال درخواست به سرور
    fetch('/erp/bulk-purchase-edit/apply/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            purchase_ids: selectedPurchases,
            changes: changes
        })
    })
    .then(response => {
        debugLog(`پاسخ دریافت شد: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
            throw new Error(`خطای سرور: ${response.status} ${response.statusText}`);
        }
        
        return response.json();
    })
    .then(response => {
        hideLoading();
        debugLog('پاسخ سرور با موفقیت پردازش شد: ' + JSON.stringify(response));
        
        if (response.success) {
            // نمایش پیام موفقیت
            Swal.fire({
                title: 'تغییرات اعمال شد',
                text: response.message,
                icon: 'success',
                confirmButtonText: 'تایید'
            }).then(() => {
                // به روزرسانی داده‌های خرید‌ها از سرور
                refreshPurchaseData();
                
                // پاک کردن انتخاب‌ها
                selectedPurchases = [];
                updateSelectedCount();
                
                // بازگشت به حالت نمایش جدول
                document.getElementById('purchaseTableContainer').style.display = 'block';
                document.getElementById('uploadArea').style.display = 'none';
            });
        } else {
            // نمایش پیام خطا
            Swal.fire({
                title: 'خطا',
                text: response.message,
                icon: 'error',
                confirmButtonText: 'تایید'
            });
            
            // نمایش خطاهای جزئی
            if (response.errors && response.errors.length > 0) {
                let errorMessage = '<ul>';
                response.errors.forEach(error => {
                    errorMessage += `<li>${error}</li>`;
                });
                errorMessage += '</ul>';
                
                document.getElementById('errorMessageText').innerHTML = errorMessage;
                document.getElementById('errorMessage').style.display = 'block';
            }
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error in bulk edit:', error);
        debugLog(`خطا در ارتباط با سرور: ${error.message}`);
        
        // نمایش پیام خطا در مودال
        Swal.fire({
            title: 'خطا در برقراری ارتباط',
            text: error.message,
            icon: 'error',
            confirmButtonText: 'تایید'
        });
    });
}

// به‌روزرسانی داده‌های خرید‌ها پس از اعمال تغییرات
function refreshPurchaseData() {
    showLoading();
    
    // شماره‌های خرید موجود در جدول را بازیابی کنیم
    const purchaseNumbers = allPurchases.map(p => p.purchase_number);
    
    // ارسال مجدد شماره‌های خرید برای دریافت اطلاعات به‌روز
    fetch('/erp/bulk-purchase-edit/upload-excel/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            purchase_numbers: purchaseNumbers
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`خطای سرور: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        hideLoading();
        
        if (data.success && data.purchase_data) {
            // به‌روزرسانی داده‌های سراسری
            allPurchases = data.purchase_data;
            
            // به‌روزرسانی جدول
            populateTable(data.purchase_data);
            
            // نمایش پیام موفقیت
            showSuccess("اطلاعات خریدها به‌روز شد");
        } else {
            showError(data.message || 'خطا در به‌روزرسانی اطلاعات خریدها');
        }
    })
    .catch(error => {
        hideLoading();
        showError('خطا در به‌روزرسانی اطلاعات: ' + error.message);
    });
}

// فرمت‌دهی اعداد
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// صدور خروجی اکسل
document.getElementById('exportButton').addEventListener('click', function() {
    if (allPurchases.length === 0) {
        showError('داده‌ای برای خروجی وجود ندارد.');
        return;
    }
    
    // ایجاد آرایه‌ای از داده‌ها برای خروجی
    const exportData = allPurchases.map(purchase => {
        return {
            'شماره خرید': purchase.purchase_number,
            'کد سیستمی': purchase.invoice_id,
            'نام مشتری': purchase.customer_name,
            'وضعیت': purchase.state,
            'محصول': purchase.cargo_name || '',
            'فی خرید': purchase.company_price,
            'فی فروش': purchase.customer_price,
            'وزن سفارش': purchase.order_weight,
            'وزن تحویلی': purchase.delivered_weight,
            'مبلغ پرداختی': purchase.amount_paid || 0
        };
    });
    
    // ایجاد یک شی ورک‌بوک جدید
    const wb = XLSX.utils.book_new();
    
    // تبدیل داده‌ها به شیت
    const ws = XLSX.utils.json_to_sheet(exportData);
    
    // اضافه کردن شیت به ورک‌بوک
    XLSX.utils.book_append_sheet(wb, ws, 'خریدها');
    
    // دانلود فایل
    XLSX.writeFile(wb, 'خروجی_خریدها.xlsx');
});

// نمایش پیام موفقیت
function showSuccess(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // نمایش در بالای صفحه
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // حذف خودکار بعد از 5 ثانیه
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
    
    // لاگ کردن پیام
    debugLog(`پیام موفقیت: ${message}`);
}

// نمایش پیام هشدار
function showWarning(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-warning alert-dismissible fade show mt-3';
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // نمایش در بالای صفحه
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // حذف خودکار بعد از 10 ثانیه
    setTimeout(() => {
        alertDiv.remove();
    }, 10000);
    
    // لاگ کردن پیام
    debugLog(`هشدار: ${message}`);
}

// اضافه کردن تابع به document ready
$(document).ready(function() {
    // بررسی بارگذاری کتابخانه XLSX
    debugLog('بررسی بارگذاری کتابخانه XLSX');
    
    if (typeof XLSX === 'undefined') {
        debugLog('خطا: کتابخانه XLSX بارگذاری نشده است!');
        showError('کتابخانه XLSX بارگذاری نشده است. لطفاً صفحه را رفرش کنید یا با پشتیبانی تماس بگیرید.');
    } else {
        debugLog('کتابخانه XLSX با موفقیت بارگذاری شد.');
    }
    
    // تنظیم رویدادها
    $('#excelFile').on('change', function() {
        uploadExcel(this);
    });
    
    // غیرفعال کردن دکمه ویرایش در ابتدا
    const editButton = document.querySelector('[data-bs-target="#editModal"]');
    if (editButton) {
        editButton.disabled = true;
    }
    
    // مخفی کردن پیام خطا در ابتدا
    document.getElementById('errorMessage').style.display = 'none';
    
    // آماده‌سازی ناحیه کشیدن و رها کردن
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('active');
    });
    
    uploadArea.addEventListener('dragleave', function() {
        this.classList.remove('active');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('active');
        
        if (e.dataTransfer.files.length) {
            document.getElementById('fileUpload').files = e.dataTransfer.files;
            uploadExcel(document.getElementById('fileUpload'));
        }
    });
    
    uploadArea.addEventListener('click', function() {
        document.getElementById('fileUpload').click();
    });
}); 