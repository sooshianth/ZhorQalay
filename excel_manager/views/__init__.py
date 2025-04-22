"""
مدیریت کننده رابط دید برای فایل‌های اکسل بازارگاه
این فایل شامل import های هر یک از ماژول‌های جداگانه است
هر ماژول مسئولیت خاصی را برعهده دارد
"""

# توابع مربوط به نمایش و لیست کردن فایل‌های اکسل
from .bge_file_list_views import (
    bge_files_list,
    view_excel_file,
    search_cargo_products,
    save_excel_changes,
    delete_excel_file
)

# توابع مربوط به آپلود و تأیید فایل‌های اکسل
from .bge_file_upload_views import (
    upload_bge_file,
    approve_bge_file
)

# توابع مربوط به پردازش فایل‌های اکسل
from .bge_file_process_views import (
    process_bge_file
) 