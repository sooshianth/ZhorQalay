from django.core.management.base import BaseCommand
import logging
from authentication.models import UserPhoneNumber
from django.contrib.auth.models import User
from core.SalesAgentModel import SalesAgent
from core.LogisticsManagerModel import LogisticsManager
from core.FinancialManagerModel import FinancialManager
from core.SupportAgentModel import SupportAgent
from HR.EmployeeModel import Employee
from django.db import transaction
import time

# ایجاد لاگر برای ثبت رویدادها
logger = logging.getLogger("bugs")

class Command(BaseCommand):
    help = 'انتقال شماره تلفن‌های کاربران از مدل‌های مختلف به مدل UserPhoneNumber'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('شروع مهاجرت شماره تلفن‌ها...'))
        start_time = time.time()
        
        # لیست مدل‌ها و نام فیلد شماره تلفن در هر کدام
        models_to_process = [
            (SalesAgent, 'phone_number'),
            (LogisticsManager, 'phone_number'),
            (FinancialManager, 'phone_number'),
            (SupportAgent, 'phone_number'),
            (Employee, 'phone_number'),
        ]
        
        # شمارنده‌ها برای گزارش
        total_processed = 0
        added_count = 0
        errors_count = 0
        skipped_count = 0
        
        # پردازش هر مدل
        for model_class, phone_field in models_to_process:
            self.stdout.write(f'پردازش مدل {model_class.__name__}...')
            
            # دریافت تمام نمونه‌های مدل
            instances = model_class.objects.all()
            
            for instance in instances:
                try:
                    with transaction.atomic():
                        # دریافت شماره تلفن
                        phone_number = getattr(instance, phone_field, None)
                        
                        if not phone_number:
                            skipped_count += 1
                            continue
                            
                        # اطمینان از اینکه کاربر معتبر است
                        if not instance.user:
                            self.stdout.write(self.style.WARNING(
                                f'کاربر {instance} دارای کاربر Django نیست. رد شد.'
                            ))
                            skipped_count += 1
                            continue
                            
                        # بررسی آیا این شماره تلفن قبلاً ثبت شده است
                        existing = UserPhoneNumber.objects.filter(phone_number=phone_number).first()
                        
                        if existing:
                            # اگر برای کاربر دیگری ثبت شده، خطا
                            if existing.user != instance.user:
                                self.stdout.write(self.style.WARNING(
                                    f'شماره تلفن {phone_number} قبلاً برای کاربر دیگری ثبت شده. رد شد.'
                                ))
                                skipped_count += 1
                                continue
                            else:
                                # این شماره قبلاً برای همین کاربر ثبت شده
                                self.stdout.write(self.style.NOTICE(
                                    f'شماره تلفن {phone_number} قبلاً برای {instance.user.username} ثبت شده. رد شد.'
                                ))
                                skipped_count += 1
                                continue
                                
                        # ایجاد رکورد جدید
                        UserPhoneNumber.objects.create(
                            user=instance.user,
                            phone_number=phone_number,
                            is_verified=True  # فرض بر این است که شماره‌های موجود تایید شده هستند
                        )
                        
                        added_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'شماره تلفن {phone_number} برای کاربر {instance.user.username} با موفقیت ثبت شد.'
                        ))
                        
                except Exception as e:
                    errors_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'خطا در پردازش {instance}: {str(e)}'
                    ))
                    logger.error(f'Error migrating phone number: {str(e)}')
                
                total_processed += 1
        
        elapsed_time = time.time() - start_time
        
        self.stdout.write(self.style.SUCCESS(
            f'مهاجرت با موفقیت به پایان رسید. زمان اجرا: {elapsed_time:.2f} ثانیه\n'
            f'تعداد کل پردازش شده: {total_processed}\n'
            f'افزوده شده: {added_count}\n'
            f'رد شده: {skipped_count}\n'
            f'خطاها: {errors_count}'
        ))





