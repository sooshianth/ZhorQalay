# Import all views to make them available through the package
from .excel_file_views import (
    excel_files_list,
    excel_file_detail,
    upload_excel_file,
    preview_excel_file,
    process_excel_file,
    approve_excel_file,
    download_excel_file,
    delete_excel_file
)

from .bge_file_views import (
    bge_files_list,
    upload_bge_file,
    process_bge_file,
    search_cargo_products
) 