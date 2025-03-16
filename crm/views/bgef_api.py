# views.py
import pandas as pd
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from core._models import Purchase
import os
from io import BytesIO
from django.utils import timezone

@csrf_exempt
def import_and_clean_excel(request):
    if request.method != 'POST' or 'file' not in request.FILES:
        return JsonResponse({"error": "Send a POST request with an Excel file."}, status=400)

    file = request.FILES['file']
    file_path = default_storage.save(f'temp/{file.name}', file)

    try:
        df = pd.read_excel(default_storage.path(file_path))
    except Exception as e:
        return JsonResponse({"error": f"Failed to read Excel: {str(e)}"}, status=400)

    updated, skipped_zero, skipped_duplicate, not_found = 0, 0, 0, 0
    cleaned_rows = []

    for index, row in df.iterrows():
        purchase_number = str(row.iloc[0]).strip()
        allocation_id = str(row.iloc[1]).strip()

        if allocation_id == '0':
            skipped_zero += 1
            continue

        try:
            purchase = Purchase.objects.get(purchase_number=purchase_number)
        except Purchase.DoesNotExist:
            not_found += 1
            continue

        if getattr(purchase, 'allocation_id', None) == allocation_id:
            skipped_duplicate += 1
            continue

        # ثبت تخصیص جدید در ERP
        if hasattr(purchase, 'allocation_id'):
            setattr(purchase, 'allocation_id', allocation_id)
            purchase.save()
            updated += 1
            cleaned_rows.append(row)  # فقط رکوردهای موفق در فایل خروجی بمانند

    os.remove(default_storage.path(file_path))

    # ساخت فایل اکسل تمیزشده فقط با ردیف‌های جدید و مفید
    cleaned_df = pd.DataFrame(cleaned_rows, columns=df.columns)
    cleaned_file = BytesIO()
    cleaned_df.to_excel(cleaned_file, index=False)
    cleaned_file.seek(0)

    response = FileResponse(cleaned_file, as_attachment=True, filename=f'cleaned_purchases_{timezone.now().strftime("%Y%m%d")}.xls')
    response['X-Updated'] = str(updated)
    response['X-Skipped-Zero'] = str(skipped_zero)
    response['X-Skipped-Duplicates'] = str(skipped_duplicate)
    response['X-Not-Found'] = str(not_found)

    return response
