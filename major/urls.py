from django.urls import path
from .views.non_bazargah_purchase_list_view import non_bazargah_purchase_list, export_non_bazargah_purchases_excel
from .views.non_bazargah_barnameh_list_view import (
    non_bazargah_barnameh_list, 
    export_non_bazargah_barnamehs_excel,
    apply_non_bazargah_barnameh_filter,
    get_non_bazargah_barnameh_column_values,
    get_available_barnameh_fields,
    update_barnameh_table_columns,
    export_full_non_bazargah_barnameh_excel
)
from .views.non_bazargah_purchase_CRUD import (
    non_bazargah_purchase_CRUD_view,
    delete_non_bazargah_purchase_view,
    download_allocation_excel_template,
    download_barnameh_excel_template,
    # upload_non_bazargah_document  # منسوخ شده - حالا درون فرم اصلی handle می‌شود
)
from .views.pdf_views import generate_barnameh_pdf, generate_comprehensive_purchase_pdf

urlpatterns = [
    path('non-bazargah-purchases/', non_bazargah_purchase_list, name='non_bazargah_purchase_list'),
    path('non-bazargah-purchases/export-excel/', export_non_bazargah_purchases_excel, name='export_non_bazargah_purchases_excel'),
    path('non-bazargah-barnamehs/', non_bazargah_barnameh_list, name='non_bazargah_barnameh_list'),
    path('non-bazargah-barnamehs/export-excel/', export_non_bazargah_barnamehs_excel, name='export_non_bazargah_barnamehs_excel'),
    path('non-bazargah-barnamehs/filter/', apply_non_bazargah_barnameh_filter, name='apply_non_bazargah_barnameh_filter'),
    path('non-bazargah-barnamehs/column-values/', get_non_bazargah_barnameh_column_values, name='get_non_bazargah_barnameh_column_values'),
    path('non-bazargah-barnamehs/available-fields/', get_available_barnameh_fields, name='get_available_barnameh_fields'),
    path('non-bazargah-barnamehs/update-columns/', update_barnameh_table_columns, name='update_barnameh_table_columns'),
    path('non-bazargah-barnamehs/export-full-excel/', export_full_non_bazargah_barnameh_excel, name='export_full_non_bazargah_barnameh_excel'),
    path('non-bazargah-purchase/<int:purchase_id>/', non_bazargah_purchase_CRUD_view, name='non_bazargah_purchase_CRUD'),
    path('non-bazargah-purchase/<int:purchase_id>/delete/', delete_non_bazargah_purchase_view, name='delete_non_bazargah_purchase'),
    path('non-bazargah-purchase/<int:purchase_id>/pdf/', generate_barnameh_pdf, name='generate_barnameh_pdf'),
    path('non-bazargah-purchase/<int:purchase_id>/comprehensive-pdf/', generate_comprehensive_purchase_pdf, name='generate_comprehensive_purchase_pdf'),
    path('download-allocation-excel-template/', download_allocation_excel_template, name='download_allocation_excel_template'),
    path('download-barnameh-excel-template/', download_barnameh_excel_template, name='download_barnameh_excel_template'),
    # path('non-bazargah-purchase/<int:purchase_id>/upload/', upload_non_bazargah_document, name='upload_non_bazargah_document'),  # منسوخ
]
