import pandas as pd
import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from core._models import CargoProduct, BGEFile, FinancialManager
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@login_required
def upload_bge_file_view(request):
    """
    نمایش فرم آپلود فایل اکسل بازارگاه و پردازش آن
    """
    # بررسی اینکه کاربر مدیر مالی است یا خیر
    financial_manager = FinancialManager.find_manager_by_user(request.user)
    if not financial_manager:
        return redirect('home')  # یا هر مسیر دیگری که مناسب است

    if request.method == 'POST':
        cargo_id = request.POST.get('cargo_id')
        excel_file = request.FILES.get('excel_file')

        if not cargo_id or not excel_file:
            return JsonResponse({
                'status': 'error',
                'message': 'لطفاً تمام فیلدها را پر کنید'
            }, status=400)

        # بررسی پسوند فایل
        file_extension = os.path.splitext(excel_file.name)[1].lower()
        if file_extension not in ['.xlsx', '.xls']:
            return JsonResponse({
                'status': 'error',
                'message': 'فقط فایل‌های اکسل (.xlsx, .xls) مجاز هستند'
            }, status=400)

        try:
            cargo_product = CargoProduct.objects.get(cottage=cargo_id)

            # بررسی وجود فایل قبلی برای این محصول
            existing_file = BGEFile.objects.filter(cargo=cargo_product).first()
            if existing_file:
                # حذف فایل قبلی و ایجاد فایل جدید
                existing_file.file = excel_file
                existing_file.user = request.user
                existing_file.save()
                file_obj = existing_file
            else:
                # ایجاد رکورد جدید
                file_obj = BGEFile.objects.create(
                    user=request.user,
                    cargo=cargo_product,
                    file=excel_file
                )

            # تغییر نام فایل به فرمت مناسب
            new_filename = f"BGE_{cargo_product.cottage}_{cargo_product.get_product_type_display()}.xlsx"
            file_obj.change_file_name(new_filename)

            # ----------------------------------------------------------------------
            # پردازش فایل اکسل و به‌روزرسانی رکوردهای Purchase
            # ----------------------------------------------------------------------
            file_path = file_obj.file.path
            output_file_path = os.path.splitext(file_path)[0] + "_cleaned.xlsx"  # مسیر فایل اکسل تمیزشده

            try:
                df = pd.read_excel(file_path)

                # ۱. حذف رکوردهای تکراری شناسه تخصیص
                column_name_shenase_takhsis = 'شناسه تخصیص'  # نام ستون "شناسه تخصیص" در اکسل
                if column_name_shenase_takhsis in df.columns:
                    df.drop_duplicates(subset=[column_name_shenase_takhsis], keep='first', inplace=True)
                else:
                    raise ValueError(f"ستون '{column_name_shenase_takhsis}' در فایل اکسل یافت نشد.")

                # ۲. به‌روزرسانی رکوردهای Purchase
                column_name_kod_kharid = 'کد خرید'  # نام ستون "کد خرید" در اکسل
                column_name_shenase_takhsis_excel = 'شناسه تخصیص'  # نام ستون "شناسه تخصیص" در اکسل

                if column_name_kod_kharid not in df.columns:
                    raise ValueError(f"ستون '{column_name_kod_kharid}' در فایل اکسل یافت نشد.")

                from core._models import Purchase  # Import Purchase model here to avoid circular import issues

                for index, row in df.iterrows():
                    purchase_number_excel = row[column_name_kod_kharid]
                    tracking_number_excel = row[column_name_shenase_takhsis_excel]

                    try:
                        purchase = Purchase.objects.get(purchase_number=purchase_number_excel)
                        purchase.tracking_number = tracking_number_excel  # به‌روزرسانی شناسه تخصیص
                        purchase.save()
                        print(f"رکورد Purchase با کد خرید '{purchase_number_excel}' به‌روزرسانی شد.")
                    except Purchase.DoesNotExist:
                        print(f"رکورد Purchase با کد خرید '{purchase_number_excel}' یافت نشد.")
                    except Exception as e:
                        print(f"خطا در به‌روزرسانی رکورد Purchase با کد خرید '{purchase_number_excel}': {e}")

                # ۳. ذخیره فایل اکسل تمیزشده
                df.to_excel(output_file_path, index=False)
                print(f"فایل اکسل تمیزشده در '{output_file_path}' ذخیره شد.")

                # Save the cleaned file to Django storage
                with open(output_file_path, 'rb') as f:
                    data = f.read()
                    file_obj.file.save(new_filename.replace(".xlsx", "_cleaned.xlsx"), ContentFile(data)) # change file_obj's file with cleaned file
                    print(f"فایل اکسل تمیز شده در مسیر اصلی خود جایگذاری شد")


            except Exception as e:
                print(f"خطا در پردازش فایل اکسل: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در پردازش فایل اکسل: {str(e)}'
                }, status=500)
            # ----------------------------------------------------------------------

            return JsonResponse({
                'status': 'success',
                'message': 'فایل با موفقیت آپلود و پردازش شد',
                'file_name': new_filename
            })

        except CargoProduct.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'محصول مورد نظر یافت نشد'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در آپلود فایل: {str(e)}'
            }, status=500)

    # برای درخواست‌های GET، فرم را نمایش می‌دهیم
    return render(request, 'bgef_upload.html', {
        'financial_manager': financial_manager
    })
