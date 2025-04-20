from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import ValidationError
from core._models import Purchase
from core.PurchaseModel import PurchaseHistory, PurchaseStateChange
from django.http import HttpResponse
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os
import jdatetime
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    BIDI_ENABLED = True
except ImportError:
    BIDI_ENABLED = False

def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    """
    if hasattr(user, 'financial_manager') and user.financial_manager is not None:
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager') and user.logistics_manager is not None:
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent') and user.sales_agent is not None:
        return 'sales_agent'
    elif hasattr(user, 'support_agent') and user.support_agent is not None:
        return 'support_agent'
    elif user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None

class RoleBasedPurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = '__all__'
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user_role == 'sales_agent' or user_role == 'admin':
            allowed_fields = [
                'weight', 'description', 'tracking_number', 'purchase_date', 'purchase_number', 'barnameh', 
                'payment_method', 'customer_price','amount_paid', 'cargo', 'shenase_takhsis', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number',
            ]
        elif user_role == 'logistics_manager':
            allowed_fields = [
                'weight', 'description', 'tracking_number', 'purchase_number', 'amount_paid', 'barnameh', 
                'customer_price', 'payment_method', 'cargo', 'shenase_takhsis', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number', 'address',
            ]
        elif user_role == 'financial_manager':
            allowed_fields = [
                'description', 'payment_method', 'company_price', 'customer_price', 'amount_paid', 'barnameh', 
                'cargo', 'purchase_date', 'purchase_number', 'tracking_number', 'weight',
            ]
        else:
            allowed_fields = []
        
        # اگر بارنامه صادر شده باشد، فیلدهای اختلاف را نشان بده
        if True or self.instance.state == 'BARNAMEH_ISSUED':
            allowed_fields += ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
                
        # برای خریدهای خارج از بازارگاه، فیلدهای مرتبط با بازارگاه را حذف می‌کنیم
        if self.instance.type == 'non_bazaargah':
            if 'purchase_number' in self.fields:
                del self.fields['purchase_number']
            if 'tracking_number' in self.fields:
                del self.fields['tracking_number']
                
    def clean(self):
        cleaned_data = super().clean()
        # اعتبارسنجی اصلی در متد save مدل انجام می‌شود
        # این باعث می‌شود از تکرار پیام‌های خطا جلوگیری شود
        return cleaned_data

@login_required
def purchase_CRUD_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    history_logs = PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp')
    state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('-changed_at')
    user_role = determine_user_role(request.user)
    
    # ساخت مراحل پیشرفت بر اساس state (وضعیت فعلی)
    progress_steps = [
        {'name': 'شروع شده', 'status': True},  # همیشه شروع شده
        {'name': 'پیامک ارسال شده', 'status': purchase.state != 'INITIATED'},
        {'name': 'تأیید ثبت خرید در بازارگاه', 'status': purchase.state in ['BAZAARGAH_CONFIRMED', 'PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تأیید انجام پرداخت توسط واحد مالی', 'status': purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ثبت تخصیص توسط مشتری', 'status': purchase.state in ['ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید تخصیص', 'status': purchase.state in ['ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تسویه با واردکننده', 'status': purchase.state in ['VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به واردکننده', 'status': purchase.state in ['ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به باربری', 'status': purchase.state in ['SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'بارنامه صادر شده', 'status': purchase.state in ['BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تحویل به مشتری', 'status': purchase.state in ['DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید اختلاف', 'status': purchase.state in ['DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'کسری/سرک واریز شده', 'status': purchase.state in ['SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ثبت رسید', 'status': purchase.state in ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'صدور فاکتور', 'status': purchase.state in ['INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد فروش', 'status': purchase.state in ['SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد لجستیک', 'status': purchase.state in ['LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد مالی', 'status': purchase.state in ['FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تکمیل شده', 'status': purchase.state == 'COMPLETED'},
    ]
    
    # برای خریدهای خارج از بازارگاه مراحل مرتبط با بازارگاه را حذف می‌کنیم
    if purchase.type == 'non_bazaargah':
        progress_steps = [step for i, step in enumerate(progress_steps) if i not in [2, 4, 5]]

    if request.method == 'POST':
        form = RoleBasedPurchaseForm(request.POST, instance=purchase, user_role=user_role)
        if form.is_valid():
            try:
                with transaction.atomic():
                    original_obj = Purchase.objects.get(id=purchase_id)
                    changed_fields = []
                    
                    # پردازش اکشن‌های مبتنی بر نقش
                    action_taken = False
                    try:
                        # اکشن‌های مبتنی بر state machine
                        if 'approve_bazaargah' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.confirm_bazaargah(request.user)
                            action_taken = True
                        elif 'approve_payment' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.verify_payment(request.user)
                            action_taken = True
                        elif 'approve_allocation' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.register_allocation(request.user)
                            action_taken = True
                        elif 'approve_allocation_approval' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_allocation(request.user)
                            action_taken = True
                        elif 'approve_tasvied_with_vared_konandeh' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.settle_with_vendor(request.user)
                            action_taken = True
                        elif 'approve_address' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_address_to_vendor(request.user)
                            action_taken = True
                        elif 'approve_sent_to_barbari' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_to_shipping(request.user)
                            action_taken = True
                        elif 'approve_barnamed' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.issue_barnameh(request.user)
                            action_taken = True
                        elif 'approve_delivered' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.mark_as_delivered(request.user)
                            action_taken = True
                        elif 'approve_ekhtelaf' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.approve_difference(request.user)
                            action_taken = True
                        elif 'approve_kasri' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.deposit_shortage(request.user)
                            action_taken = True
                        elif 'approve_sarak' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.deposit_surplus(request.user)
                            action_taken = True
                        elif 'approve_kasri_reciept' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.submit_receipt(request.user)
                            action_taken = True
                        elif 'approve_factor' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.issue_invoice(request.user)
                            action_taken = True
                        elif 'approve_salesman' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.approve_by_sales(request.user)
                            action_taken = True
                        elif 'approve_logistics' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_by_logistics(request.user)
                            action_taken = True
                        elif 'approve_financial' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.approve_by_financial(request.user)
                            action_taken = True
                    except ValidationError as action_error:
                        # نمایش خطای اعتبارسنجی به صورت پیام دوستانه کاربر
                        if hasattr(action_error, 'message'):
                            messages.error(request, action_error.message)
                        else:
                            for field, errors in action_error.message_dict.items():
                                for error in errors:
                                    messages.error(request, error)
                        return redirect('purchase_CRUD', purchase_id=purchase_id)
                    
                    # پردازش تغییرات فرم فقط در صورتی که دکمه اکشن فشرده نشده باشد یا اکشن موفقیت‌آمیز بوده باشد
                    if not action_taken or (action_taken and request.POST.get('save_changes')):
                        for field in form.changed_data:
                            old_value = getattr(original_obj, field)
                            new_value = form.cleaned_data.get(field)
                            changed_fields.append(f"{field}: {old_value} → {new_value}")
                    
                    form.save()
                    if changed_fields:
                        PurchaseHistory.objects.create(
                            purchase=purchase,
                            user=request.user,
                            changes=" | ".join(changed_fields)
                        )
                    
                    messages.success(request, 'تغییرات با موفقیت اعمال شد')
                    return redirect('purchase_CRUD', purchase_id=purchase_id)
            except ValidationError as e:
                # مدیریت خطاهای اعتبارسنجی فرم
                if hasattr(e, 'message'):
                    messages.error(request, e.message)
                else:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, error)
            except Exception as e:
                messages.error(request, f'خطا: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')

    else:
        form = RoleBasedPurchaseForm(instance=purchase, user_role=user_role)

    context = {
        'purchase': purchase,
        'form': form,
        'progress_steps': progress_steps,
        'history_logs': history_logs,
        'state_changes': state_changes,
        'user_role': user_role,
    }
    return render(request, 'purchase_CRUD_view.html', context)

@login_required
def delete_purchase_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'خرید با موفقیت حذف شد')
        return redirect('purchase_list')  # مسیر redirect را بر اساس نیاز خود تنظیم کنید

    context = {
        'purchase': purchase,
    }
    return render(request, 'confirm_delete.html', context)

@login_required
def generate_purchase_pdf(request, purchase_id):
    user_role = determine_user_role(request.user)
    if user_role == 'support_agent':
        messages.error(request, 'شما اجازه ایجاد گزارش خرید را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)

    purchase = get_object_or_404(Purchase, id=purchase_id)
    
    # ساخت پاسخ HTTP برای PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="purchase_{purchase.invoice_id}.pdf"'
    
    # ایجاد فایل PDF در حافظه
    buffer = io.BytesIO()
    
    # تنظیم فونت فارسی
    font_path = os.path.join(settings.BASE_DIR, 'crm', 'static', 'fonts', 'Vazir.ttf')
    pdfmetrics.registerFont(TTFont('Vazir', font_path))
    
    # تابع کمکی برای تبدیل متن فارسی به حالت صحیح برای نمایش
    def process_persian_text(text):
        """تبدیل متن فارسی به حالت صحیح برای نمایش در PDF"""
        if text is None:
            return "-"
        
        text = str(text)
        if not BIDI_ENABLED:
            return text
        
        try:
            # بازسازی متن فارسی
            reshaped_text = arabic_reshaper.reshape(text)
            # تبدیل به BIDI
            bidi_text = get_display(reshaped_text)
            return bidi_text
        except:
            return text
    
    # تابع کمکی برای تبدیل مقادیر به متن امن
    def safe_text(value, default='-'):
        """تبدیل مقادیر به متن امن"""
        if value is None:
            return default
        return process_persian_text(str(value))
    
    # تابع کمکی برای تبدیل اعداد به متن فارسی با کاما
    def format_number(value, default='0'):
        """تبدیل اعداد به متن فارسی با کاما"""
        if value is None or value == 0:
            return default
        try:
            return process_persian_text(f"{int(value):,}")
        except (ValueError, TypeError):
            return default
    
    # تنظیمات حاشیه‌ها
    doc = SimpleDocTemplate(
        buffer,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
        pagesize=A4
    )
    
    # تنظیم استایل فارسی
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Right',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=10,
        leading=14,
        firstLineIndent=0,
        rightIndent=0
    ))
    styles.add(ParagraphStyle(
        name='RightTitle',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=14,
        leading=16,
        spaceAfter=10,
        firstLineIndent=0,
        rightIndent=0
    ))
    
    # لیست آیتم‌های پلاتی‌پاس برای قرار دادن در PDF
    elements = []
    
    # عنوان گزارش
    title_text = process_persian_text(f"گزارش کامل خرید - کد شناسه: {safe_text(purchase.invoice_id)} - شرکت تأمین نهاده سیمرغ")
    elements.append(Paragraph(title_text, styles['RightTitle']))
    elements.append(Spacer(width=0, height=10))
    
    # بخش اطلاعات مشتری
    # دریافت شماره تلفن اصلی مشتری به جای استفاده از فیلد قدیمی
    primary_phone = purchase.customer.get_primary_phone() if hasattr(purchase.customer, 'get_primary_phone') else purchase.customer.phone_number
    
    customer_data = [
        [Paragraph(safe_text(purchase.customer.name), styles['Right']), Paragraph(process_persian_text('نام مشتری:'), styles['Right'])],
        [Paragraph(safe_text(purchase.customer.city), styles['Right']), Paragraph(process_persian_text('شهر/استان:'), styles['Right'])],
        [Paragraph(safe_text(primary_phone), styles['Right']), Paragraph(process_persian_text('شماره تماس:'), styles['Right'])],
    ]
    
    # اضافه کردن کارشناس فروش مربوطه
    sales_agents = purchase.customer.sales_agent.all()
    if sales_agents:
        sales_agent_names = ", ".join([agent.name for agent in sales_agents])
        customer_data.append([Paragraph(safe_text(sales_agent_names), styles['Right']), Paragraph(process_persian_text('کارشناس فروش:'), styles['Right'])])
    
    customer_table = Table(customer_data, colWidths=[doc.width*3/4, doc.width/4])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات مشتری"), styles['RightTitle']))
    elements.append(customer_table)
    elements.append(Spacer(width=0, height=15))
    
    # بخش اطلاعات اصلی خرید
    purchase_status = dict(Purchase.STATUS_CHOICES).get(purchase.state, '')
    purchase_type = dict([('bazaargah', 'بازارگاه'), ('non_bazaargah', 'خارج از بازارگاه')]).get(purchase.type, '-')
    
    cargo_product_type = '-'
    cargo_country = '-'
    if purchase.cargo:
        try:
            cargo_product_type = purchase.cargo.get_product_type_display() or '-'
        except (AttributeError, ValueError):
            cargo_product_type = '-'
            
        try:
            cargo_country = purchase.cargo.get_country_display() or '-'
        except (AttributeError, ValueError):
            cargo_country = '-'
    
    created_at = '-'
    updated_at = '-'
    if purchase.created_at:
        try:
            created_at = purchase.created_at.strftime('%Y/%m/%d %H:%M')
        except AttributeError:
            created_at = '-'
            
    if purchase.updated_at:
        try:
            updated_at = purchase.updated_at.strftime('%Y/%m/%d %H:%M')
        except AttributeError:
            updated_at = '-'
    
    purchase_data = [
        [Paragraph(safe_text(purchase.invoice_id), styles['Right']), Paragraph(process_persian_text('کد درون سازمانی:'), styles['Right'])],
        [Paragraph(safe_text(purchase_status), styles['Right']), Paragraph(process_persian_text('وضعیت فعلی:'), styles['Right'])],
        [Paragraph(process_persian_text(purchase_type), styles['Right']), Paragraph(process_persian_text('نوع خرید:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_product_type), styles['Right']), Paragraph(process_persian_text('نوع کالا:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_country), styles['Right']), Paragraph(process_persian_text('کشور مبدا:'), styles['Right'])],
        [Paragraph(format_number(purchase.weight), styles['Right']), Paragraph(process_persian_text('وزن (کیلوگرم):'), styles['Right'])],
        [Paragraph(safe_text(purchase.payment_method), styles['Right']), Paragraph(process_persian_text('روش پرداخت:'), styles['Right'])],
        [Paragraph(format_number(purchase.customer_price), styles['Right']), Paragraph(process_persian_text('فی فروش (ریال):'), styles['Right'])],
        [Paragraph(format_number(purchase.amount_paid), styles['Right']), Paragraph(process_persian_text('مبلغ پرداختی (ریال):'), styles['Right'])],
        [Paragraph(process_persian_text(created_at), styles['Right']), Paragraph(process_persian_text('تاریخ ثبت:'), styles['Right'])],
        [Paragraph(process_persian_text(updated_at), styles['Right']), Paragraph(process_persian_text('تاریخ بروزرسانی:'), styles['Right'])],
    ]
    
    purchase_table = Table(purchase_data, colWidths=[doc.width*2/3, doc.width/3])
    purchase_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات خرید"), styles['RightTitle']))
    elements.append(purchase_table)
    elements.append(Spacer(width=0, height=15))
    
    # اطلاعات بازارگاه یا بارنامه
    if purchase.type == 'bazaargah':
        # دریافت شناسه تخصیص از جدول ManyToMany
        shenase_takhsis_list = []
        try:
            shenase_takhsis_objects = purchase.shenase_takhsis_set.all()
            if shenase_takhsis_objects.exists():
                shenase_takhsis_list = [obj.code for obj in shenase_takhsis_objects]
        except:
            pass
        
        shenase_takhsis_text = ", ".join(shenase_takhsis_list) if shenase_takhsis_list else purchase.shenase_takhsis or '-'
        
        bazargah_data = [
            [Paragraph(safe_text(purchase.purchase_number), styles['Right']), Paragraph(process_persian_text('شماره خرید بازارگاه:'), styles['Right'])],
            [Paragraph(safe_text(purchase.tracking_number), styles['Right']), Paragraph(process_persian_text('شماره پیگیری:'), styles['Right'])],
            [Paragraph(safe_text(shenase_takhsis_text), styles['Right']), Paragraph(process_persian_text('شناسه تخصیص:'), styles['Right'])],
            [Paragraph(safe_text(purchase.code_melli_tahvil), styles['Right']), Paragraph(process_persian_text('کد ملی تحویل:'), styles['Right'])],
            [Paragraph(safe_text(purchase.bazaargah_phone_number), styles['Right']), Paragraph(process_persian_text('شماره تلفن بازارگاه:'), styles['Right'])],
            [Paragraph(safe_text(purchase.tahvil_phone_number), styles['Right']), Paragraph(process_persian_text('شماره تلفن تحویل:'), styles['Right'])],
        ]
        
        bazargah_table = Table(bazargah_data, colWidths=[doc.width*2/3, doc.width/3])
        bazargah_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("اطلاعات بازارگاه"), styles['RightTitle']))
        elements.append(bazargah_table)
        elements.append(Spacer(width=0, height=15))
    
    # اطلاعات بارنامه و حمل
    shipping_data = [
        [Paragraph(safe_text(purchase.barnameh), styles['Right']), Paragraph(process_persian_text('شماره بارنامه:'), styles['Right'])],
        [Paragraph(safe_text(purchase.address), styles['Right']), Paragraph(process_persian_text('آدرس تحویل:'), styles['Right'])],
    ]
    
    shipping_table = Table(shipping_data, colWidths=[doc.width*2/3, doc.width/3])
    shipping_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات حمل و نقل"), styles['RightTitle']))
    elements.append(shipping_table)
    elements.append(Spacer(width=0, height=15))
    
    # اطلاعات اختلاف وزن
    if purchase.extelaf_type:
        extelaf_data = [
            [Paragraph(safe_text(purchase.extelaf_type), styles['Right']), Paragraph(process_persian_text('نوع اختلاف:'), styles['Right'])],
            [Paragraph(format_number(purchase.extelaf_weight), styles['Right']), Paragraph(process_persian_text('وزن اختلاف (کیلوگرم):'), styles['Right'])],
            [Paragraph(format_number(purchase.extelaf_amount), styles['Right']), Paragraph(process_persian_text('مبلغ اختلاف (ریال):'), styles['Right'])],
        ]
        
        extelaf_table = Table(extelaf_data, colWidths=[doc.width*2/3, doc.width/3])
        extelaf_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("اطلاعات اختلاف وزن"), styles['RightTitle']))
        elements.append(extelaf_table)
        elements.append(Spacer(width=0, height=15))
    
    # توضیحات
    if purchase.description:
        desc_data = [
            [Paragraph(safe_text(purchase.description), styles['Right']), Paragraph(process_persian_text('توضیحات:'), styles['Right'])],
        ]
        
        desc_table = Table(desc_data, colWidths=[doc.width*2/3, doc.width/3])
        desc_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("توضیحات"), styles['RightTitle']))
        elements.append(desc_table)
        elements.append(Spacer(width=0, height=15))
    
    # پاورقی با تاریخ تولید گزارش
    now = jdatetime.datetime.now()
    try:
        footer_date = now.strftime('%Y/%m/%d %H:%M')
    except:
        footer_date = "تاریخ نامشخص"
        
    footer_text = process_persian_text(f"تاریخ گزارش: {footer_date}")
    elements.append(Paragraph(footer_text, styles['Right']))
    
    # ساخت PDF
    try:
        doc.build(elements)
    except Exception as e:
        # در صورت بروز خطا، یک صفحه ساده با پیام خطا نمایش دهیم
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        p.setFont('Vazir', 14)
        p.drawCentredString(A4[0]/2, A4[1]/2, process_persian_text("خطا در تولید PDF"))
        p.drawCentredString(A4[0]/2, A4[1]/2 - 20, f"کد خطا: {str(e)[:100]}")
        p.save()
        
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response