from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.PurchaseModel import Purchase
from bki_barnameh.models.BarnamehModel import Barnameh



class Command(BaseCommand):
    help = 'تست گزارش بارنامه‌های سریع'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('شروع تست گزارش بارنامه‌های سریع...'))
        
        # محاسبه تاریخ‌های مورد نیاز
        now = timezone.now()
        four_days_ago = now - timedelta(days=4)
        
        # یافتن خریدهای 4 روز اخیر که دارای بارنامه هستند
        purchases_with_barnamehs = Purchase.objects.filter(
            created_at__gte=four_days_ago
        ).prefetch_related(
            'barnamehs',
            'unique_sales_agent',
            'customer',
            'cargo'
        ).filter(
            barnamehs__isnull=False
        ).distinct()
        
        self.stdout.write(f'تعداد خریدهای یافت شده: {purchases_with_barnamehs.count()}')
        
        # فیلتر کردن خریدهایی که بارنامه‌شان زودتر از 3 روز آمده
        fast_purchases = []
        for purchase in purchases_with_barnamehs:
            for barnameh in purchase.barnamehs.all():
                if barnameh.barnameh_created_at:
                    # محاسبه تفاوت زمان بین ثبت خرید و صدور بارنامه
                    time_diff = barnameh.barnameh_created_at - purchase.created_at
                    if time_diff.days < 3:  # کمتر از 3 روز
                        fast_purchases.append({
                            'purchase': purchase,
                            'barnameh': barnameh,
                            'days_diff': time_diff.days,
                            'hours_diff': time_diff.total_seconds() / 3600
                        })
                        self.stdout.write(
                            f'خرید سریع: {purchase.purchase_number} - '
                            f'بارنامه: {barnameh.number} - '
                            f'تفاوت: {time_diff.days} روز ({time_diff.total_seconds()/3600:.1f} ساعت)'
                        )
                        break  # فقط اولین بارنامه سریع را در نظر بگیریم
        
        self.stdout.write(f'تعداد خریدهای سریع: {len(fast_purchases)}')
        
        # گروه‌بندی بر اساس کارشناس فروش
        sales_agent_groups = {}
        for item in fast_purchases:
            purchase = item['purchase']
            sales_agent = purchase.unique_sales_agent
            
            # اگر کارشناس فروش مشخص نباشد، در گروه "نامشخص" قرار بده
            if not sales_agent:
                agent_key = "نامشخص"
                agent_name = "کارشناس فروش نامشخص"
            else:
                agent_key = str(sales_agent.id)
                agent_name = sales_agent.name or sales_agent.user.get_full_name() or sales_agent.user.username
            
            if agent_key not in sales_agent_groups:
                sales_agent_groups[agent_key] = {
                    'name': agent_name,
                    'purchases': []
                }
            
            sales_agent_groups[agent_key]['purchases'].append(item)
        
        self.stdout.write(f'تعداد کارشناسان فروش: {len(sales_agent_groups)}')
        
        for agent_key, agent_data in sales_agent_groups.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f'کارشناس فروش: {agent_data["name"]} - '
                    f'تعداد خریدهای سریع: {len(agent_data["purchases"])}'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('تست با موفقیت تکمیل شد!'))
