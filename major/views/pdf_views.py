from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.colors import black, blue, red, green
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF
from io import BytesIO
import os
import arabic_reshaper
from bidi.algorithm import get_display
import jdatetime
import logging

from major.models.NonBazargahPurchase import NonBazargahPurchase
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role

logger = logging.getLogger("major_pdf_views")

# Check if BIDI is enabled
BIDI_ENABLED = True

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

def safe_text(value, default='-'):
    """تبدیل مقادیر به متن امن"""
    if value is None:
        return default
    return process_persian_text(str(value))

def format_number(value, default='0'):
    """تبدیل اعداد به متن فارسی با کاما"""
    if value is None or value == 0:
        return default
    try:
        return process_persian_text(f"{int(value):,}")
    except (ValueError, TypeError):
        return default

def get_pdf_styles():
    """Return standardized styles for PDF generation"""
    styles = getSampleStyleSheet()
    
    # Right-aligned paragraph style (for Persian text)
    styles.add(ParagraphStyle(
        name='Right',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=10,
        leading=14,
        firstLineIndent=0,
        rightIndent=0
    ))
    
    # Right-aligned title style
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
    
    # Centered title style
    styles.add(ParagraphStyle(
        name='CenterTitle',
        fontName='Vazir',
        alignment=TA_CENTER,
        fontSize=16,
        leading=18,
        spaceAfter=10
    ))
    
    # Header style
    styles.add(ParagraphStyle(
        name='Header',
        fontName='Vazir',
        alignment=TA_CENTER,
        fontSize=12,
        leading=14
    ))
    
    # Footer style
    styles.add(ParagraphStyle(
        name='Footer',
        fontName='Vazir',
        alignment=TA_CENTER,
        fontSize=8,
        leading=10
    ))
    
    # Small text style
    styles.add(ParagraphStyle(
        name='Small',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=8,
        leading=10
    ))
    
    return styles

def register_persian_fonts():
    """ثبت فونت‌های فارسی برای PDF"""
    try:
        # تلاش برای ثبت فونت‌های فارسی (در صورت وجود)
        font_path = os.path.join(settings.BASE_DIR, 'ERP', 'static', 'fonts', 'Vazir.ttf')
        pdfmetrics.registerFont(TTFont('Vazir', font_path))
    except:
        # در صورت عدم وجود فونت فارسی، از فونت پیش‌فرض استفاده کن
        global BIDI_ENABLED
        BIDI_ENABLED = False


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
@login_required
def generate_barnameh_pdf(request, purchase_id):
    """تولید PDF برای تمام بارنامه‌های یک خرید خارج بازارگاه"""
    logger.info(f"درخواست تولید PDF بارنامه‌ها برای خرید {purchase_id} توسط {request.user.username}")
    
    purchase = get_object_or_404(NonBazargahPurchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش
    if user_role == 'sales_agent':
        if not purchase.customer or not hasattr(request.user, 'sales_agent'):
            raise PermissionDenied('شما اجازه دسترسی به این خرید را ندارید.')
        
        if not purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
            raise PermissionDenied('شما اجازه دسترسی به این خرید را ندارید.')
    
        # بررسی اینکه خرید در مرحله صدور بارنامه یا بعد از آن باشد
        if purchase.state not in ['barnameh_issued', 'delivered', 'purchase_closed']:
            raise PermissionDenied('فقط در مرحله صدور بارنامه یا بعد از آن می‌توان PDF تولید کرد.')
    
    # دریافت تمام بارنامه‌ها
    barnamehs = purchase.get_all_barnamehs()
    if not barnamehs:
        raise PermissionDenied('هیچ بارنامه‌ای برای این خرید وجود ندارد.')
    
    try:
        # ایجاد PDF
        buffer = BytesIO()
        
        # ثبت فونت‌های فارسی
        register_persian_fonts()
        
        # Document dimensions
        doc_width = A4[0] - 40 * mm  # A4 width minus margins
        
        # Get styles
        styles = get_pdf_styles()
        
        # Create the document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=30 * mm,
        )
        
        # محتوای PDF
        story = []
        
        # عنوان اصلی
        story.append(Paragraph(process_persian_text("گزارش بارنامه‌های خرید خارج بازارگاه"), styles['CenterTitle']))
        story.append(Spacer(1, 10 * mm))
        
        # اطلاعات خرید
        story.append(Paragraph(process_persian_text("اطلاعات خرید"), styles['RightTitle']))
        story.append(Spacer(1, 5 * mm))
        
        # جدول اطلاعات خرید
        purchase_data = [
            [Paragraph(safe_text(purchase.purchase_number or purchase.id), styles['Right']), Paragraph(process_persian_text('شماره خرید:'), styles['Right'])],
            [Paragraph(safe_text(purchase.product.name if purchase.product else 'نامشخص'), styles['Right']), Paragraph(process_persian_text('محصول:'), styles['Right'])],
            [Paragraph(safe_text(purchase.customer.name if purchase.customer else 'نامشخص'), styles['Right']), Paragraph(process_persian_text('مشتری:'), styles['Right'])],
            [Paragraph(safe_text(f"{purchase.quantity} {purchase.get_unit_display() if purchase.unit else ''}"), styles['Right']), Paragraph(process_persian_text('مقدار:'), styles['Right'])],
            [Paragraph(safe_text(purchase.get_state_display()), styles['Right']), Paragraph(process_persian_text('وضعیت:'), styles['Right'])],
            [Paragraph(safe_text(len(barnamehs)), styles['Right']), Paragraph(process_persian_text('تعداد بارنامه‌ها:'), styles['Right'])],
        ]
        
        purchase_table = Table(purchase_data, colWidths=[doc_width*2/3, doc_width/3])
        purchase_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(purchase_table)
        story.append(Spacer(1, 10 * mm))
        
        # جدول بارنامه‌ها
        story.append(Paragraph(process_persian_text("اطلاعات بارنامه‌ها"), styles['RightTitle']))
        story.append(Spacer(1, 5 * mm))
        
        # Create table headers (ترتیب از راست به چپ)
        barnameh_data = [
             [
                 Paragraph(process_persian_text('مقصد'), styles['Right']),
                 Paragraph(process_persian_text('وزن خالص'), styles['Right']),
                 Paragraph(process_persian_text('وزن پر'), styles['Right']),
                 Paragraph(process_persian_text('وزن خالی'), styles['Right']),
                 Paragraph(process_persian_text('پلاک ماشین'), styles['Right']),
                 Paragraph(process_persian_text('تلفن راننده'), styles['Right']),
                 Paragraph(process_persian_text('راننده'), styles['Right']),
                 Paragraph(process_persian_text('شماره بارنامه'), styles['Right']),
                 Paragraph(process_persian_text('ردیف'), styles['Right'])
             ]
         ]
        
        total_empty_weight = 0
        total_loaded_weight = 0
        total_net_weight = 0
        
        for i, barnameh in enumerate(barnamehs, 1):
            empty_weight = barnameh.empty_vehicle_weight or 0
            loaded_weight = barnameh.loaded_vehicle_weight or 0
            net_weight = loaded_weight - empty_weight if loaded_weight and empty_weight else 0
            
            total_empty_weight += empty_weight
            total_loaded_weight += loaded_weight
            total_net_weight += net_weight
            
            barnameh_data.append([
                 Paragraph(safe_text(barnameh.destination), styles['Right']),
                 Paragraph((format_number(net_weight) + ' ' + process_persian_text('کیلوگرم')) if net_weight else '-', styles['Right']),
                 Paragraph((format_number(loaded_weight) + ' ' + process_persian_text('کیلوگرم')) if loaded_weight else '-', styles['Right']),
                 Paragraph((format_number(empty_weight) + ' ' + process_persian_text('کیلوگرم')) if empty_weight else '-', styles['Right']),
                 Paragraph(safe_text(barnameh.vehicle_plate), styles['Right']),
                 Paragraph(safe_text(barnameh.driver_phone), styles['Right']),
                 Paragraph(safe_text(barnameh.driver_name), styles['Right']),
                 Paragraph(safe_text(barnameh.number), styles['Right']),
                 Paragraph(str(i), styles['Right'])
             ])
        
        # اضافه کردن ردیف مجموع
        barnameh_data.append([
             Paragraph('', styles['Right']),
             Paragraph(format_number(total_net_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']),
             Paragraph(format_number(total_loaded_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']),
             Paragraph(format_number(total_empty_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']),
             Paragraph('', styles['Right']),
             Paragraph('', styles['Right']),
             Paragraph('', styles['Right']),
             Paragraph('', styles['Right']),
             Paragraph(process_persian_text('مجموع'), styles['Right'])
         ])
        
        # Calculate column widths (ترتیب از راست به چپ)
        col_widths = [
             doc_width * 0.12,  # مقصد
             doc_width * 0.11,  # وزن خالص
             doc_width * 0.11,  # وزن پر
             doc_width * 0.11,  # وزن خالی
             doc_width * 0.10,  # پلاک ماشین
             doc_width * 0.11,  # تلفن راننده
             doc_width * 0.11,  # راننده
             doc_width * 0.11,  # شماره بارنامه
             doc_width * 0.12,  # ردیف
         ]
        
        # ایجاد جدول
        barnameh_table = Table(barnameh_data, colWidths=col_widths)
        barnameh_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        
        story.append(barnameh_table)
        story.append(Spacer(1, 10 * mm))
        
        # اطلاعات تفصیلی هر بارنامه
        for i, barnameh in enumerate(barnamehs, 1):
            story.append(Paragraph(process_persian_text(f"بارنامه {i}: {barnameh.number or 'نامشخص'}"), styles['RightTitle']))
            
            # محاسبه وزن خالص برای این بارنامه
            barnameh_empty_weight = barnameh.empty_vehicle_weight or 0
            barnameh_loaded_weight = barnameh.loaded_vehicle_weight or 0
            barnameh_net_weight = barnameh_loaded_weight - barnameh_empty_weight if barnameh_loaded_weight and barnameh_empty_weight else 0
            
            # اطلاعات تفصیلی بارنامه
            detail_data = [
                [Paragraph(safe_text(barnameh.number), styles['Right']), Paragraph(process_persian_text('شماره بارنامه:'), styles['Right'])],
                [Paragraph(safe_text(barnameh.driver_name), styles['Right']), Paragraph(process_persian_text('نام راننده:'), styles['Right'])],
                [Paragraph(safe_text(barnameh.driver_phone), styles['Right']), Paragraph(process_persian_text('شماره تلفن راننده:'), styles['Right'])],
                [Paragraph(safe_text(barnameh.vehicle_plate), styles['Right']), Paragraph(process_persian_text('پلاک ماشین:'), styles['Right'])],
                 [Paragraph((format_number(barnameh_empty_weight) + ' ' + process_persian_text('کیلوگرم')) if barnameh_empty_weight else '-', styles['Right']), Paragraph(process_persian_text('وزن خالی ماشین:'), styles['Right'])],
                 [Paragraph((format_number(barnameh_loaded_weight) + ' ' + process_persian_text('کیلوگرم')) if barnameh_loaded_weight else '-', styles['Right']), Paragraph(process_persian_text('وزن پر ماشین:'), styles['Right'])],
                 [Paragraph((format_number(barnameh_net_weight) + ' ' + process_persian_text('کیلوگرم')) if barnameh_net_weight else '-', styles['Right']), Paragraph(process_persian_text('وزن خالص بار:'), styles['Right'])],
                 [Paragraph((format_number(barnameh.final_delivered_weight) + ' ' + process_persian_text('کیلوگرم')) if barnameh.final_delivered_weight else '-', styles['Right']), Paragraph(process_persian_text('وزن نهایی تحویل:'), styles['Right'])],
                [Paragraph(safe_text(barnameh.destination), styles['Right']), Paragraph(process_persian_text('مقصد:'), styles['Right'])],
                [Paragraph(safe_text(barnameh.barnameh_created_at.strftime('%Y/%m/%d %H:%M') if barnameh.barnameh_created_at else 'نامشخص'), styles['Right']), Paragraph(process_persian_text('تاریخ ایجاد:'), styles['Right'])],
            ]
            
            detail_table = Table(detail_data, colWidths=[doc_width*2/3, doc_width/3])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
                ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(detail_table)
            story.append(Spacer(1, 10 * mm))
        
        # اطلاعات تخصیص‌ها
        if purchase.allocations.exists():
            story.append(Paragraph(process_persian_text("اطلاعات تخصیص‌ها"), styles['RightTitle']))
            story.append(Spacer(1, 5 * mm))
            
            allocation_data = [
                [
                    Paragraph(process_persian_text('شماره تخصیص'), styles['Right']),
                    Paragraph(process_persian_text('آدرس تحویل'), styles['Right']),
                    Paragraph(process_persian_text('نام گیرنده'), styles['Right']),
                    Paragraph(process_persian_text('وزن تخصیص یافته'), styles['Right'])
                ]
            ]
            
            for allocation in purchase.allocations.all():
                allocation_data.append([
                    Paragraph(safe_text(allocation.allocation_number or f"تخصیص {allocation.id}"), styles['Right']),
                    Paragraph(safe_text(allocation.delivery_address), styles['Right']),
                    Paragraph(safe_text(allocation.delivery_receiver_name), styles['Right']),
                     Paragraph((format_number(allocation.allocated_weight) + ' ' + process_persian_text('کیلوگرم')) if allocation.allocated_weight else '-', styles['Right'])
                ])
            
            allocation_table = Table(allocation_data, colWidths=[doc_width*0.25, doc_width*0.4, doc_width*0.2, doc_width*0.15])
            allocation_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
                ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(allocation_table)
            story.append(Spacer(1, 10 * mm))
        
        # خلاصه نهایی
        story.append(Paragraph(process_persian_text("خلاصه نهایی"), styles['RightTitle']))
        story.append(Spacer(1, 5 * mm))
        
        summary_data = [
            [Paragraph(safe_text(len(barnamehs)), styles['Right']), Paragraph(process_persian_text('تعداد بارنامه‌ها:'), styles['Right'])],
             [Paragraph(format_number(total_empty_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']), Paragraph(process_persian_text('مجموع وزن خالی:'), styles['Right'])],
             [Paragraph(format_number(total_loaded_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']), Paragraph(process_persian_text('مجموع وزن پر:'), styles['Right'])],
             [Paragraph(format_number(total_net_weight) + ' ' + process_persian_text('کیلوگرم'), styles['Right']), Paragraph(process_persian_text('مجموع وزن خالص:'), styles['Right'])],
             [Paragraph(format_number(purchase.get_remaining_weight_for_allocation() + purchase.get_total_allocated_weight()) + ' ' + process_persian_text('کیلوگرم'), styles['Right']), Paragraph(process_persian_text('وزن درخواستی:'), styles['Right'])],
             [Paragraph(format_number(total_net_weight - (purchase.get_remaining_weight_for_allocation() + purchase.get_total_allocated_weight())) + ' ' + process_persian_text('کیلوگرم'), styles['Right']), Paragraph(process_persian_text('اختلاف وزن:'), styles['Right'])],
        ]
        
        summary_table = Table(summary_data, colWidths=[doc_width*2/3, doc_width/3])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgreen),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(summary_table)
        
        # ساخت PDF
        doc.build(story)
        
        # تنظیم response
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="barnameh_report_{purchase.purchase_number or purchase.id}.pdf"'
        
        logger.info(f"PDF بارنامه‌ها برای خرید {purchase_id} با موفقیت تولید شد")
        return response
        
    except Exception as e:
        logger.error(f"خطا در تولید PDF بارنامه‌ها برای خرید {purchase_id}: {str(e)}")
        return HttpResponse(f"خطا در تولید PDF: {str(e)}", status=500)
