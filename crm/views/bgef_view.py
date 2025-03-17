from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from core._models import CargoProduct, BGEFile, FinancialManager
import json
import os


@login_required
@require_http_methods(["GET"])
def search_cargo_products(request):
    """
    API برای جستجوی محصولات با قابلیت اتوکامپلیت
    """
    # بررسی اینکه کاربر مدیر مالی است یا خیر
    financial_manager = FinancialManager.find_manager_by_user(request.user)
    if not financial_manager:
        return JsonResponse({'results': []}, status=403)
    
    query = request.GET.get('q', '')
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    # جستجو بر اساس کوتاژ، نوع محصول و کشور
    products = CargoProduct.objects.filter(
        Q(cottage__icontains=query) |
        Q(product_type__icontains=query) |
        Q(country__icontains=query)
    ).filter(status=True)[:10]  # فقط محصولات فعال و حداکثر 10 مورد
    
    results = []
    for product in products:
        results.append({
            'id': product.cottage,
            'text': f"{product.get_product_type_display()} {product.get_country_display()} - {product.cottage}",
            'product_type': product.product_type,
            'product_type_display': product.get_product_type_display(),
            'country': product.country,
            'country_display': product.get_country_display(),
            'cottage': product.cottage,
            'weight': product.weight
        })
    
    return JsonResponse({'results': results})




from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from core._models import CargoProduct, BGEFile, LogisticsManager
import pandas as pd
import os
import io

@login_required
def logistics_bge_files_view(request):
    """
    نمایش لیست فایل‌های اکسل بازارگاه برای کارشناس لجستیک
    """
    # بررسی اینکه کاربر کارشناس لجستیک است یا خیر
    logistics_manager = LogisticsManager.find_logistics_manager_by_user(request.user)
    if not logistics_manager:
        return redirect('home')  # یا هر مسیر دیگری که مناسب است
    
    # دریافت فایل‌های تأیید نشده (برای نمایش در بالای صفحه)
    pending_files = BGEFile.objects.filter(is_approved=False).order_by('-created_at')
    
    # دریافت فایل‌های تأیید شده (برای نمایش در پایین صفحه)
    approved_files = BGEFile.objects.filter(is_approved=True).order_by('-created_at')
    
    context = {
        'logistics_manager': logistics_manager,
        'pending_files': pending_files,
        'approved_files': approved_files,
    }
    
    return render(request, 'bge_files_list.html', context)


import pandas as pd
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core._models import BGEFile

@login_required
def preview_bge_file(request, file_id):
    logistics_manager = LogisticsManager.find_logistics_manager_by_user(request.user)
    if not logistics_manager:
        return JsonResponse({'error': 'شما دسترسی لازم را ندارید'}, status=403)

    bge_file = get_object_or_404(BGEFile, id=file_id)
    try:
        df = pd.read_excel(bge_file.file.path)
        required_columns = ['شناسه تخصیص', 'کد خرید']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({'error': f'ستون‌های {missing_columns} در فایل یافت نشدند'}, status=400)

        preview_rows = int(request.GET.get('rows', 10))
        preview_rows = min(preview_rows, len(df))
        df_preview = df.head(preview_rows)
        table_html = df_preview.to_html(
            classes=['table', 'table-striped', 'table-bordered', 'table-hover'],
            index=False,
            border=0
        )
        total_rows = len(df)
        total_columns = len(df.columns)
        file_size = os.path.getsize(bge_file.file.path) / 1024

        context = {
            'bge_file': bge_file,
            'table_html': table_html,
            'total_rows': total_rows,
            'preview_rows': preview_rows,
            'total_columns': total_columns,
            'file_size': f"{file_size:.2f} KB",
            'file_id': file_id,
        }
        return render(request, 'partials/preview_content.html', context)
    except Exception as e:
        return JsonResponse({'error': f'خطا در خواندن فایل: {str(e)}'}, status=500)

@login_required
@require_http_methods(["POST"])
def approve_bge_file(request, file_id):
    """
    تأیید فایل اکسل بازارگاه
    """
    # بررسی اینکه کاربر کارشناس لجستیک است یا خیر
    logistics_manager = LogisticsManager.find_logistics_manager_by_user(request.user)
    if not logistics_manager:
        return JsonResponse({'status': 'error', 'message': 'شما دسترسی لازم را ندارید'}, status=403)
    
    # دریافت فایل مورد نظر
    try:
        bge_file = BGEFile.objects.get(id=file_id)
    except BGEFile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'فایل مورد نظر یافت نشد'}, status=404)
    
    # تأیید فایل
    bge_file.is_approved = True
    bge_file.save()
    
    return JsonResponse({
        'status': 'success', 
        'message': f'فایل {bge_file.file.name} با موفقیت تأیید شد'
    })


@login_required
def download_bge_file(request, file_id):
    """
    دانلود فایل اکسل بازارگاه
    """
    # بررسی اینکه کاربر کارشناس لجستیک است یا خیر
    logistics_manager = LogisticsManager.find_logistics_manager_by_user(request.user)
    if not logistics_manager:
        return redirect('home')
    
    # دریافت فایل مورد نظر
    bge_file = get_object_or_404(BGEFile, id=file_id)
    
    # دریافت مسیر فایل
    file_path = bge_file.file.path
    
    # ارسال فایل به کاربر
    response = FileResponse(open(file_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
    
    return response


