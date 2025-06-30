/**
 * مدیریت تاریخچه تغییرات
 */
class EditHistoryManager {
    constructor(config = {}) {
        this.config = {
            historyApiUrl: '/table-filter/edit-history-api/',
            restoreValueApiUrl: '/table-filter/restore-value-api/',
            modalSelector: '#historyModal',
            tableBodySelector: '#historyTableBody',
            paginationSelector: '#historyPagination',
            totalRecordsSelector: '#historyTotalRecords',
            userFilterSelector: '#historyUserFilter',
            actionFilterSelector: '#historyActionFilter',
            fieldFilterSelector: '#historyFieldFilter',
            dateFilterSelector: '#historyDateFilter',
            customerFilterSelector: '#historyCustomerFilter',
            applyFiltersSelector: '#applyHistoryFilters',
            resetFiltersSelector: '#resetHistoryFilters',
            currentPage: 1,
            pageSize: 20,
            ...config
        };
        
        console.log('EditHistoryManager تنظیمات:', this.config);
        this.historyData = null;
        this.filters = {
            app_name: '',
            model_name: '',
            user: '',
            action_type: '',
            field_name: '',
            date: '',
            object_id: '',
            customer: ''
        };
    }

    init() {
        // اضافه کردن ارجاع‌های DOM به ابزارهای مختلف
        this.modal = document.querySelector(this.config.modalSelector);
        this.tableBody = document.querySelector(this.config.tableBodySelector);
        this.pagination = document.querySelector(this.config.paginationSelector);
        this.totalRecords = document.querySelector(this.config.totalRecordsSelector);
        this.userFilter = document.querySelector(this.config.userFilterSelector);
        this.actionFilter = document.querySelector(this.config.actionFilterSelector);
        this.fieldFilter = document.querySelector(this.config.fieldFilterSelector);
        this.dateFilter = document.querySelector(this.config.dateFilterSelector);
        this.customerFilter = document.querySelector(this.config.customerFilterSelector);
        this.applyFiltersBtn = document.querySelector(this.config.applyFiltersSelector);
        this.resetFiltersBtn = document.querySelector(this.config.resetFiltersSelector);
        
        // اضافه کردن event listener ها
        this.attachEventListeners();
        
        // اگر مدال باز باشد، دیتا رو لود کن
        if (this.modal && this.modal.classList.contains('show')) {
            this.loadHistoryData();
        }
        
        // افزودن event listener برای باز شدن مدال
        if (this.modal) {
            this.modal.addEventListener('shown.bs.modal', () => {
                // بررسی کنیم که آیا فیلتر خاصی از قبل تنظیم شده
                const hasObjectIdFilter = this.filters.object_id !== '';
                
                // بارگذاری داده‌ها
                this.loadHistoryData();
                
                // اگر فیلتر آبجکت آیدی نداریم، فیلترها رو نشون بده
                const filterSection = this.modal.querySelector('.filter-section');
                if (filterSection) {
                    filterSection.style.display = hasObjectIdFilter ? 'none' : 'block';
                }
                
                // اگر فیلتر آبجکت آیدی داریم، عنوان رو تغییر بده
                if (hasObjectIdFilter) {
                    const title = this.modal.querySelector('.modal-title');
                    if (title) {
                        title.innerHTML = `<i class="fas fa-history me-2"></i>تاریخچه تغییرات آیتم شماره ${this.filters.object_id}`;
                    }
                }
            });
            
            // ریست فیلترها وقتی مدال بسته میشه
            this.modal.addEventListener('hidden.bs.modal', () => {
                // ریست فیلترها فقط اگر بصورت سراسری باز شده باشه
                if (!this.filters.object_id) {
                    this.resetFilters();
                }
                
                // ریست فیلترهای اضافی برای حل مشکل ماندگاری فیلتر
                this.filters.object_id = '';
                this.filters.customer = '';
            });
        }
    }

    attachEventListeners() {
        // دکمه‌های فیلتر
        const applyBtn = document.querySelector(this.config.applyFiltersSelector);
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyFilters();
            });
        }
        
        const resetBtn = document.querySelector(this.config.resetFiltersSelector);
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetFilters();
            });
        }
    }

    applyFilters() {
        this.filters.user = this.userFilter.value;
        this.filters.action_type = this.actionFilter.value;
        this.filters.field_name = this.fieldFilter.value;
        this.filters.date = this.dateFilter.value;
        this.filters.customer = this.customerFilter ? this.customerFilter.value : '';
        
        this.config.currentPage = 1; // بازگشت به صفحه اول
        this.loadHistoryData();
    }

    resetFilters() {
        // ریست فیلترها
        if (this.userFilter) this.userFilter.value = '';
        if (this.actionFilter) this.actionFilter.value = '';
        if (this.fieldFilter) this.fieldFilter.value = '';
        if (this.dateFilter) this.dateFilter.value = '';
        if (this.customerFilter) this.customerFilter.value = '';
        
        // ریست فیلترهای داخلی
        const preserveObjectId = this.filters.object_id; // حفظ فیلتر آبجکت آیدی در برخی موارد
        
        this.filters = {
            app_name: this.filters.app_name,
            model_name: this.filters.model_name,
            user: '',
            action_type: '',
            field_name: '',
            date: '',
            object_id: preserveObjectId, // بازیابی فیلتر آبجکت آیدی
            customer: ''
        };
        
        // بارگیری مجدد با فیلترهای جدید
        this.loadHistoryData();
    }

    loadHistoryData(page = null) {
        // تنظیم شماره صفحه
        if (page !== null) {
            this.config.currentPage = page;
        }
        
        // نمایش وضعیت بارگیری
        if (this.tableBody) {
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="11" class="text-center py-4">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">در حال بارگذاری...</span>
                        </div>
                        <p class="mt-2">در حال دریافت اطلاعات تاریخچه...</p>
                    </td>
                </tr>
            `;
        }
        
        // ساخت URL با پارامترهای فیلتر
        const params = new URLSearchParams({
            page: this.config.currentPage,
            page_size: this.config.pageSize
        });
        
        // اضافه کردن فیلترها به URL
        if (this.filters.app_name) params.append('app_name', this.filters.app_name);
        if (this.filters.model_name) params.append('model_name', this.filters.model_name);
        if (this.filters.user) params.append('user', this.filters.user);
        if (this.filters.action_type) params.append('action_type', this.filters.action_type);
        if (this.filters.field_name) params.append('field_name', this.filters.field_name);
        if (this.filters.date) params.append('date', this.filters.date);
        if (this.filters.object_id) params.append('object_id', this.filters.object_id);
        if (this.filters.customer) params.append('customer', this.filters.customer);
        
        const apiUrl = `${this.config.historyApiUrl}?${params.toString()}`;
        console.log('درخواست API تاریخچه به آدرس:', apiUrl);
        
        // ارسال درخواست به API
        fetch(apiUrl)
            .then(response => {
                console.log('وضعیت پاسخ API:', response.status, response.statusText);
                if (!response.ok) {
                    throw new Error(`خطا در دریافت اطلاعات تاریخچه: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('داده‌های دریافتی از API:', data);
                this.historyData = data;
                this.renderHistoryData();
                
                // نمایش تعداد کل نتایج
                if (this.totalRecords) {
                    this.totalRecords.textContent = `${data.count} رکورد`;
                }
                
                // پر کردن لیست کاربران (اگر بار اول است)
                if (this.userFilter && this.filters.user === '' && data.users && Array.isArray(data.users)) {
                    // حذف همه گزینه‌ها به جز اولی
                    while (this.userFilter.options.length > 1) {
                        this.userFilter.remove(1);
                    }
                    // اضافه کردن گزینه‌های جدید
                    data.users.forEach(user => {
                        const option = document.createElement('option');
                        option.value = user.id;
                        option.textContent = user.username;
                        this.userFilter.appendChild(option);
                    });
                }
                
                // پر کردن لیست فیلدها (اگر بار اول است)
                if (this.fieldFilter && this.filters.field_name === '' && data.fields && Array.isArray(data.fields)) {
                    // حذف همه گزینه‌ها به جز اولی
                    while (this.fieldFilter.options.length > 1) {
                        this.fieldFilter.remove(1);
                    }
                    // اضافه کردن گزینه‌های جدید
                    data.fields.forEach(field => {
                        const option = document.createElement('option');
                        option.value = field;
                        option.textContent = field;
                        this.fieldFilter.appendChild(option);
                    });
                }
                
                // پر کردن لیست مشتریان (اگر بار اول است)
                if (this.customerFilter && this.filters.customer === '' && data.customers && Array.isArray(data.customers)) {
                    // حذف همه گزینه‌ها به جز اولی
                    while (this.customerFilter.options.length > 1) {
                        this.customerFilter.remove(1);
                    }
                    // اضافه کردن گزینه‌های جدید
                    data.customers.forEach(customer => {
                        const option = document.createElement('option');
                        option.value = customer.id;
                        option.textContent = customer.name;
                        this.customerFilter.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('خطا در بارگیری داده‌های تاریخچه:', error);
                if (this.tableBody) {
                    this.tableBody.innerHTML = `
                        <tr>
                            <td colspan="11" class="text-center py-4 text-danger">
                                <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                                <p>خطا در دریافت اطلاعات: ${error.message}</p>
                                <p>لطفا کنسول مرورگر را برای جزئیات بیشتر بررسی کنید</p>
                            </td>
                        </tr>
                    `;
                }
            });
    }

    renderHistoryData() {
        if (!this.historyData) return;
        
        // خالی کردن جدول
        let tableContent = '';
        
        // اگر نتیجه‌ای وجود نداشت
        if (!this.historyData.results.length) {
            tableContent = `
                <tr>
                    <td colspan="11" class="text-center py-4">
                        <div class="text-muted">
                            <i class="fas fa-info-circle fs-4 mb-3 d-block"></i>
                            <p>هیچ رکوردی یافت نشد.</p>
                            <small>فیلترها را تغییر دهید یا همه فیلترها را پاک کنید.</small>
                        </div>
                    </td>
                </tr>
            `;
            this.tableBody.innerHTML = tableContent;
            
            // خالی کردن صفحه‌بندی
            this.pagination.innerHTML = '';
            return;
        }
        
        // پر کردن جدول با اطلاعات
        this.historyData.results.forEach(item => {
            tableContent += `
                <tr>
                    <td>${item.id}</td>
                    <td>${item.user_name || '-'}</td>
                    <td>${item.model_name || '-'}</td>
                    <td>${item.customer_name || '-'}</td>
                    <td>${item.object_id || '-'}</td>
                    <td>${item.field_name || '-'}</td>
                    <td class="text-wrap" style="max-width: 200px;">
                        <div class="text-truncate" title="${item.old_value || '-'}">${item.old_value || '-'}</div>
                    </td>
                    <td class="text-wrap" style="max-width: 200px;">
                        <div class="text-truncate" title="${item.new_value || '-'}">${item.new_value || '-'}</div>
                    </td>
                    <td>
                        ${this.getActionBadge(item.action_type)}
                    </td>
                    <td>${this.formatDate(item.timestamp)}</td>
                    <td>
                        <button class="btn btn-sm restore-value-btn" 
                            data-id="${item.id}" data-object-id="${item.object_id}" 
                            data-field="${item.field_name}" data-value="${item.old_value || ''}">
                            <i class="fas fa-undo-alt"></i> بازگردانی
                        </button>
                    </td>
                </tr>
            `;
        });
        this.tableBody.innerHTML = tableContent;
        
        // اضافه کردن event listener برای دکمه‌های بازگردانی
        this.tableBody.querySelectorAll('.restore-value-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                const objectId = e.currentTarget.getAttribute('data-object-id');
                const field = e.currentTarget.getAttribute('data-field');
                const value = e.currentTarget.getAttribute('data-value');
                
                this.restoreValue(objectId, field, value);
            });
        });
        
        // ساخت صفحه‌بندی
        this.createPagination();
    }

    getActionBadge(actionType) {
        switch(actionType) {
            case 'CREATE':
                return '<span class="badge bg-success">ایجاد</span>';
            case 'UPDATE':
                return '<span class="badge bg-primary">بروزرسانی</span>';
            case 'DELETE':
                return '<span class="badge bg-danger">حذف</span>';
            default:
                return `<span class="badge bg-secondary">${actionType}</span>`;
        }
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        
        // تبدیل تاریخ میلادی به شمسی
        try {
            const date = new Date(dateString);
            return new Intl.DateTimeFormat('fa-IR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            }).format(date);
        } catch (e) {
            return dateString;
        }
    }

    createPagination() {
        const totalPages = Math.ceil(this.historyData.count / this.historyData.page_size);
        const currentPage = this.historyData.current_page;
        
        if (totalPages <= 1) {
            this.pagination.innerHTML = '';
            return;
        }
        
        let paginationHTML = '';
        
        // دکمه قبلی
        paginationHTML += `
            <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${currentPage - 1}" aria-label="Previous">
                    <span aria-hidden="true">&laquo;</span>
                </a>
            </li>
        `;
        
        // محاسبه محدوده صفحات
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, startPage + 4);
        
        if (endPage - startPage < 4) {
            startPage = Math.max(1, endPage - 4);
        }
        
        // اضافه کردن صفحه اول اگر نیاز باشد
        if (startPage > 1) {
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1">1</a>
                </li>
            `;
            if (startPage > 2) {
                paginationHTML += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
        }
        
        // صفحات میانی
        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `;
        }
        
        // اضافه کردن صفحه آخر اگر نیاز باشد
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${totalPages}">${totalPages}</a>
                </li>
            `;
        }
        
        // دکمه بعدی
        paginationHTML += `
            <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${currentPage + 1}" aria-label="Next">
                    <span aria-hidden="true">&raquo;</span>
                </a>
            </li>
        `;
        
        this.pagination.innerHTML = paginationHTML;
        
        // اضافه کردن event listener برای دکمه‌های صفحه‌بندی
        this.pagination.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.getAttribute('data-page') || e.target.closest('.page-link').getAttribute('data-page'));
                if (!isNaN(page) && page > 0) {
                    this.loadHistoryData(page);
                }
            });
        });
    }

    restoreValue(objectId, fieldName, oldValue) {
        // بهبود دیالوگ تایید با نمایش جزئیات بیشتر
        if (!confirm(`آیا مطمئن هستید که می‌خواهید این تغییر را بازگردانی کنید؟\n\nنام فیلد: ${fieldName}\nمقدار قبلی: ${oldValue}\n\nاین عملیات غیرقابل بازگشت است.`)) {
            return;
        }
        
        console.log("Restoring value:", { objectId, fieldName, oldValue });
        
        // نمایش وضعیت بارگذاری
        const loadingToast = this.showToast('در حال بازگردانی مقدار...', 'info', false);
        
        const data = {
            object_id: objectId,
            field_name: fieldName,
            value: oldValue,
            app_name: this.filters.app_name || 'core',
            model_name: this.filters.model_name || 'Purchase'
        };
        
        console.log("Sending restore request with data:", data);
        console.log("API URL:", this.config.restoreValueApiUrl);
        
        fetch(this.config.restoreValueApiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            console.log("Restore API response status:", response.status);
            if (!response.ok) {
                throw new Error(`خطا در بازگردانی مقدار: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Restore API response data:", data);
            // پنهان کردن توست بارگذاری
            if (loadingToast) {
                loadingToast.hide();
            }
            
            if (data.success) {
                // نمایش پیام موفقیت
                this.showToast('مقدار با موفقیت بازگردانی شد', 'success', true);
                
                // بارگیری مجدد تاریخچه
                this.loadHistoryData();
                
                // ریلود صفحه برای نمایش تغییرات پس از مکث کوتاه
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                // نمایش خطا
                this.showToast(`خطا: ${data.error || 'مشکلی در بازگردانی مقدار رخ داد.'}`, 'error', true);
            }
        })
        .catch(error => {
            console.error('Error during restore operation:', error);
            // پنهان کردن توست بارگذاری
            if (loadingToast) {
                loadingToast.hide();
            }
            
            this.showToast(`خطا: ${error.message}`, 'error', true);
        });
    }

    getCsrfToken() {
        // اول از المان meta با نام csrf-token استفاده می‌کنیم که اولویت بالاتری دارد
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // اگر المان meta یافت نشد از کوکی استفاده می‌کنیم
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        console.warn('توکن CSRF یافت نشد! ممکن است درخواست‌های POST با خطا مواجه شوند.');
        return '';
    }

    openHistoryModal(appName, modelName, objectId, customerId = null) {
        this.filters.app_name = appName || '';
        this.filters.model_name = modelName || '';
        this.filters.object_id = objectId || '';
        this.filters.customer = customerId || '';
        
        // باز کردن مدال
        if (this.modal) {
            const modal = new bootstrap.Modal(this.modal);
            modal.show();
        }
    }

    // نمایش توست برای اطلاع‌رسانی
    showToast(message, type = 'info', autoHide = true) {
        // اگر bootstrap toast موجود است از آن استفاده می‌کنیم
        if (typeof bootstrap !== 'undefined' && typeof bootstrap.Toast !== 'undefined') {
            // ساخت یک توست جدید
            const toastEl = document.createElement('div');
            toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');
            
            if (autoHide) {
                toastEl.setAttribute('data-bs-delay', '3000');
            } else {
                toastEl.setAttribute('data-bs-autohide', 'false');
            }
            
            toastEl.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
            
            // اضافه کردن به صفحه
            const toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) {
                const container = document.createElement('div');
                container.className = 'toast-container position-fixed top-0 end-0 p-3';
                container.style.zIndex = '1090';
                document.body.appendChild(container);
                container.appendChild(toastEl);
            } else {
                toastContainer.appendChild(toastEl);
            }
            
            // نمایش توست
            const toast = new bootstrap.Toast(toastEl);
            toast.show();
            
            // اضافه کردن کد برای حذف توست از DOM پس از بسته شدن
            toastEl.addEventListener('hidden.bs.toast', () => {
                toastEl.remove();
            });
            
            return toast;
        } else {
            // اگر bootstrap توست موجود نیست از alert استفاده می‌کنیم
            if (type === 'error') {
                alert(`خطا: ${message}`);
            } else {
                alert(message);
            }
            return null;
        }
    }
}

// ایجاد نمونه جهانی
const editHistoryManager = new EditHistoryManager();

// اجرای اولیه پس از بارگیری صفحه
document.addEventListener('DOMContentLoaded', function() {
    editHistoryManager.init();
}); 