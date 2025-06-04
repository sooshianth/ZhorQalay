from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from django.conf import settings
import os
import arabic_reshaper
from bidi.algorithm import get_display
import jdatetime
from io import BytesIO

# Check if BIDI is enabled
BIDI_ENABLED = True

# Helper functions for PDF generation
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

def create_header_table(doc_width, purchase, styles):
    """Create the header table for the PDF"""
    # Company logo path
    logo_path = os.path.join(settings.BASE_DIR, 'ERP', 'static', 'img', 'logo.png')
    logo_exists = os.path.exists(logo_path)
    
    # Header data
    if logo_exists:
        logo = Image(logo_path)
        logo.drawHeight = 15 * mm
        logo.drawWidth = 15 * mm
        header_data = [
            [
                Paragraph(process_persian_text("شرکت تأمین نهاده سیمرغ"), styles['Header']),
                logo,
                Paragraph(process_persian_text(f"گزارش خرید: {safe_text(purchase.invoice_id)}"), styles['Header'])
            ]
        ]
    else:
        header_data = [
            [
                Paragraph(process_persian_text("شرکت تأمین نهاده سیمرغ"), styles['Header']),
                Paragraph(process_persian_text(f"گزارش خرید: {safe_text(purchase.invoice_id)}"), styles['Header'])
            ]
        ]
    
    # Create header table
    if logo_exists:
        col_widths = [doc_width/3, doc_width/3, doc_width/3]
    else:
        col_widths = [doc_width/2, doc_width/2]
        
    header_table = Table(header_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    return header_table

def create_footer_table(doc_width, styles, page_number=None):
    """Create the footer table for the PDF"""
    now = jdatetime.datetime.now()
    try:
        footer_date = now.strftime('%Y/%m/%d %H:%M')
    except:
        footer_date = "تاریخ نامشخص"
    
    footer_data = []
    
    if page_number:
        footer_data = [
            [
                Paragraph(process_persian_text(f"صفحه {page_number}"), styles['Footer']),
                Paragraph(process_persian_text("این سند بدون مهر و امضا فاقد اعتبار است"), styles['Footer']),
                Paragraph(process_persian_text(f"تاریخ گزارش: {footer_date}"), styles['Footer'])
            ]
        ]
    else:
        footer_data = [
            [
                Paragraph(process_persian_text("این سند بدون مهر و امضا فاقد اعتبار است"), styles['Footer']),
                Paragraph(process_persian_text(f"تاریخ گزارش: {footer_date}"), styles['Footer'])
            ]
        ]
    
    col_widths = [doc_width/3, doc_width/3, doc_width/3] if page_number else [doc_width/2, doc_width/2]
    
    footer_table = Table(footer_data, colWidths=col_widths)
    footer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    return footer_table

def create_customer_info_table(doc_width, purchase, styles):
    """Create customer information table"""
    # Get primary phone
    primary_phone = purchase.customer.get_primary_phone() if hasattr(purchase.customer, 'get_primary_phone') else purchase.customer.phone_number
    
    customer_data = [
        [Paragraph(safe_text(purchase.customer.name), styles['Right']), Paragraph(process_persian_text('نام مشتری:'), styles['Right'])],
        [Paragraph(safe_text(purchase.customer.city), styles['Right']), Paragraph(process_persian_text('شهر/استان:'), styles['Right'])],
        [Paragraph(safe_text(purchase.customer.get_field_of_activity_display()), styles['Right']), Paragraph(process_persian_text('حیطه فعالیت:'), styles['Right'])],
        [Paragraph(safe_text(primary_phone), styles['Right']), Paragraph(process_persian_text('شماره تماس:'), styles['Right'])],
    ]
    
    # Add sales agent info if available
    sales_agents = purchase.customer.sales_agent.all()
    if sales_agents:
        sales_agent_names = ", ".join([agent.name for agent in sales_agents])
        customer_data.append([Paragraph(safe_text(sales_agent_names), styles['Right']), Paragraph(process_persian_text('کارشناس فروش:'), styles['Right'])])
    
    customer_table = Table(customer_data, colWidths=[doc_width*3/4, doc_width/4])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    return customer_table

def create_purchase_info_table(doc_width, purchase, styles):
    """Create purchase information table"""
    purchase_status = dict(purchase.STATUS_CHOICES).get(purchase.state, '')
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
        [Paragraph(safe_text(purchase.purchase_number), styles['Right']), Paragraph(process_persian_text('شماره خرید بازارگاه:'), styles['Right'])],
        [Paragraph(process_persian_text(getattr(purchase.cargo, 'cottage', '-')), styles['Right']), Paragraph(process_persian_text('کوتاژ:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_product_type), styles['Right']), Paragraph(process_persian_text('نوع کالا:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_country), styles['Right']), Paragraph(process_persian_text('کشور مبدا:'), styles['Right'])],
        [Paragraph(format_number(purchase.order_weight), styles['Right']), Paragraph(process_persian_text('وزن سفارش (کیلوگرم):'), styles['Right'])],
        [Paragraph(format_number(purchase.delivered_weight), styles['Right']), Paragraph(process_persian_text('وزن تحویلی (کیلوگرم):'), styles['Right'])],
        [Paragraph(safe_text(purchase.payment_method), styles['Right']), Paragraph(process_persian_text('روش پرداخت:'), styles['Right'])],
        [Paragraph(format_number(purchase.customer_price), styles['Right']), Paragraph(process_persian_text('فی فروش (ریال):'), styles['Right'])],
        [Paragraph(format_number(purchase.amount_paid), styles['Right']), Paragraph(process_persian_text('مبلغ پرداختی (ریال):'), styles['Right'])],
        [Paragraph(process_persian_text(created_at), styles['Right']), Paragraph(process_persian_text('تاریخ ثبت:'), styles['Right'])],
        [Paragraph(process_persian_text(updated_at), styles['Right']), Paragraph(process_persian_text('تاریخ بروزرسانی:'), styles['Right'])],
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
    
    return purchase_table

def create_allocation_info_table(doc_width, purchase, styles):
    """Create allocation IDs information table"""
    # Get allocation IDs
    shenase_takhsis_list = []
    try:
        shenase_takhsis_objects = purchase.shenase_takhsis_set.all()
        if shenase_takhsis_objects.exists():
            for obj in shenase_takhsis_objects:
                shenase_takhsis_list.append([
                    Paragraph(format_number(obj.weight) if obj.weight else '-', styles['Right']), 
                    Paragraph(safe_text(obj.code), styles['Right'])
                ])
    except:
        shenase_takhsis_list = [[Paragraph('-', styles['Right']), Paragraph(safe_text(purchase.shenase_takhsis or '-'), styles['Right'])]]
    
    if not shenase_takhsis_list:
        shenase_takhsis_list = [[Paragraph('-', styles['Right']), Paragraph(safe_text(purchase.shenase_takhsis or '-'), styles['Right'])]]
    
    # Add header row
    shenase_takhsis_list.insert(0, [
        Paragraph(process_persian_text('وزن (کیلوگرم)'), styles['Right']), 
        Paragraph(process_persian_text('شناسه تخصیص'), styles['Right'])
    ])
    
    allocation_table = Table(shenase_takhsis_list, colWidths=[doc_width/3, doc_width*2/3])
    allocation_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    return allocation_table

def create_barnameh_table(doc_width, barnamehs, styles, start_idx=0, items_per_page=15):
    """Create barnameh information table with pagination"""
    if not barnamehs:
        # If no barnamehs, return empty table with message
        barnameh_data = [[Paragraph(process_persian_text('هیچ بارنامه‌ای برای این خرید ثبت نشده است.'), styles['Right'])]]
        barnameh_table = Table(barnameh_data, colWidths=[doc_width])
        barnameh_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        return barnameh_table
    
    # Get subset of barnamehs for this page
    end_idx = min(start_idx + items_per_page, len(barnamehs))
    page_barnamehs = barnamehs[start_idx:end_idx]
    
    # Create table headers
    barnameh_data = [
        [
            Paragraph(process_persian_text('ردیف'), styles['Right']),
            Paragraph(process_persian_text('شماره بارنامه'), styles['Right']),
            Paragraph(process_persian_text('سریال'), styles['Right']),
            Paragraph(process_persian_text('وزن (کیلوگرم)'), styles['Right']),
            Paragraph(process_persian_text('تاریخ'), styles['Right']),
            Paragraph(process_persian_text('راننده'), styles['Right']),
            Paragraph(process_persian_text('پلاک'), styles['Right']),
            Paragraph(process_persian_text('گیرنده'), styles['Right']),
            Paragraph(process_persian_text('مقصد'), styles['Right']),
            Paragraph(process_persian_text('وضعیت'), styles['Right'])
        ]
    ]
    
    # Add barnameh data rows
    for i, barnameh in enumerate(page_barnamehs):
        row_idx = i + start_idx + 1  # For numbering
        
        # Determine barnameh status text
        status_text = barnameh.get_status_display() if hasattr(barnameh, 'get_status_display') else barnameh.status
        if status_text == 'BARNAMEH_INCOMPLETE' or status_text == 'incomplete':
            status_text = 'ناتمام'
        elif status_text == 'BARNAMEH_COMPLETE' or status_text == 'complete':
            status_text = 'تکمیل شده'
        elif status_text == 'PURCHASE_CLOSED' or status_text == 'closed':
            status_text = 'بسته شده'
        
        barnameh_number = barnameh.barnameh_number if hasattr(barnameh, 'barnameh_number') else (barnameh.number or '-')
        barnameh_serial = barnameh.serial_number if hasattr(barnameh, 'serial_number') else (barnameh.serial or '-')
        barnameh_weight = barnameh.weight if hasattr(barnameh, 'weight') else (barnameh.tonnage or '-')
        barnameh_date = barnameh.issue_date.strftime('%Y/%m/%d') if hasattr(barnameh, 'issue_date') and barnameh.issue_date else (
            barnameh.barnameh_date.strftime('%Y/%m/%d') if hasattr(barnameh, 'barnameh_date') and barnameh.barnameh_date else '-'
        )
        
        barnameh_data.append([
            Paragraph(str(row_idx), styles['Right']),
            Paragraph(safe_text(barnameh_number), styles['Right']),
            Paragraph(safe_text(barnameh_serial), styles['Right']),
            Paragraph(format_number(barnameh_weight), styles['Right']),
            Paragraph(safe_text(barnameh_date), styles['Right']),
            Paragraph(safe_text(barnameh.driver_name), styles['Right']),
            Paragraph(safe_text(barnameh.vehicle_plate_number if hasattr(barnameh, 'vehicle_plate_number') else barnameh.vehicle_plate), styles['Right']),
            Paragraph(safe_text(barnameh.receiver if hasattr(barnameh, 'receiver') else barnameh.receiver_name), styles['Right']),
            Paragraph(safe_text(barnameh.destination), styles['Right']),
            Paragraph(safe_text(status_text), styles['Right'])
        ])
    
    # Calculate column widths - adjust as needed for your specific needs
    col_widths = [
        doc_width * 0.05,  # ردیف
        doc_width * 0.12,  # شماره بارنامه
        doc_width * 0.12,  # سریال
        doc_width * 0.10,  # وزن
        doc_width * 0.10,  # تاریخ
        doc_width * 0.12,  # راننده
        doc_width * 0.09,  # پلاک
        doc_width * 0.10,  # گیرنده
        doc_width * 0.10,  # مقصد
        doc_width * 0.10,  # وضعیت
    ]
    
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
    
    return barnameh_table

def create_difference_table(doc_width, purchase, styles):
    """Create table for weight/price differences (if any)"""
    if not purchase.extelaf_type:
        return None
    
    extelaf_data = [
        [Paragraph(safe_text(purchase.extelaf_type), styles['Right']), Paragraph(process_persian_text('نوع اختلاف:'), styles['Right'])],
        [Paragraph(format_number(purchase.extelaf_weight), styles['Right']), Paragraph(process_persian_text('وزن اختلاف (کیلوگرم):'), styles['Right'])],
        [Paragraph(format_number(purchase.extelaf_amount), styles['Right']), Paragraph(process_persian_text('مبلغ اختلاف (ریال):'), styles['Right'])],
    ]
    
    extelaf_table = Table(extelaf_data, colWidths=[doc_width*2/3, doc_width/3])
    extelaf_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    return extelaf_table

def create_description_table(doc_width, purchase, styles):
    """Create description table (if description exists)"""
    if not purchase.description:
        return None
    
    desc_data = [
        [Paragraph(safe_text(purchase.description), styles['Right']), Paragraph(process_persian_text('توضیحات:'), styles['Right'])],
    ]
    
    desc_table = Table(desc_data, colWidths=[doc_width*2/3, doc_width/3])
    desc_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    return desc_table

class NumberedCanvas(canvas.Canvas):
    """Specialized canvas for adding page numbers"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        # Add the page number
        page = f"{self._pageNumber}/{page_count}"
        self.setFont("Vazir", 8)
        self.drawRightString(A4[0] - 20 * mm, 20 * mm, process_persian_text(f"صفحه {page}"))

def generate_purchase_pdf(purchase, output=None):
    """
    Generate a professional PDF report for a purchase.
    
    Args:
        purchase: Purchase object with all related data
        output: Optional output file path or BytesIO object
        
    Returns:
        BytesIO object containing the PDF data
    """
    # Register fonts
    try:
        font_path = os.path.join(settings.BASE_DIR, 'ERP', 'static', 'fonts', 'Vazir.ttf')
        pdfmetrics.registerFont(TTFont('Vazir', font_path))
    except:
        # Fallback to default font if Vazir is not available
        BIDI_ENABLED = False
    
    # Create a BytesIO buffer if no output specified
    if output is None:
        output = BytesIO()
    
    # Document dimensions
    doc_width = A4[0] - 40 * mm  # A4 width minus margins
    
    # Get styles
    styles = get_pdf_styles()
    
    # Create the document
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=30 * mm,
    )
    
    # Start building the document
    story = []
    
    # Add main title
    story.append(Paragraph(process_persian_text("گزارش خرید"), styles['CenterTitle']))
    story.append(Spacer(1, 10 * mm))
    
    # Add header information
    story.append(create_header_table(doc_width, purchase, styles))
    story.append(Spacer(1, 10 * mm))
    
    # Add purchase summary section title
    story.append(Paragraph(process_persian_text("اطلاعات خرید"), styles['RightTitle']))
    story.append(Spacer(1, 5 * mm))
    
    # Add customer information
    story.append(Paragraph(process_persian_text("اطلاعات مشتری"), styles['Right']))
    story.append(Spacer(1, 3 * mm))
    story.append(create_customer_info_table(doc_width, purchase, styles))
    story.append(Spacer(1, 10 * mm))
    
    # Add purchase details
    story.append(Paragraph(process_persian_text("جزئیات خرید"), styles['Right']))
    story.append(Spacer(1, 3 * mm))
    story.append(create_purchase_info_table(doc_width, purchase, styles))
    story.append(Spacer(1, 10 * mm))
    
    # Add allocation IDs if available
    story.append(Paragraph(process_persian_text("شناسه‌های تخصیص"), styles['Right']))
    story.append(Spacer(1, 3 * mm))
    story.append(create_allocation_info_table(doc_width, purchase, styles))
    story.append(Spacer(1, 10 * mm))
    
    # Add difference information if available
    extelaf_table = create_difference_table(doc_width, purchase, styles)
    if extelaf_table:
        story.append(Paragraph(process_persian_text("اطلاعات اختلاف"), styles['Right']))
        story.append(Spacer(1, 3 * mm))
        story.append(extelaf_table)
        story.append(Spacer(1, 10 * mm))
    
    # Add description if available
    desc_table = create_description_table(doc_width, purchase, styles)
    if desc_table:
        story.append(Paragraph(process_persian_text("توضیحات"), styles['Right']))
        story.append(Spacer(1, 3 * mm))
        story.append(desc_table)
        story.append(Spacer(1, 10 * mm))
    
    # Add barnameh data
    story.append(Paragraph(process_persian_text("اطلاعات بارنامه‌ها"), styles['RightTitle']))
    story.append(Spacer(1, 5 * mm))
    
    # Get all barnamehs
    barnamehs = []
    try:
        barnamehs = purchase.barnameh_set.all().order_by('id')
    except:
        pass
    
    if not barnamehs:
        # If no barnamehs, just add an empty table with message
        story.append(create_barnameh_table(doc_width, barnamehs, styles))
    else:
        # If we have barnamehs, add the first page to the first page
        max_first_page = min(15, len(barnamehs))
        story.append(create_barnameh_table(doc_width, barnamehs, styles, 0, max_first_page))
        
        # If we have more than 15 barnamehs, add the rest to new pages
        if len(barnamehs) > 15:
            # Add the rest of barnamehs with page breaks
            for i in range(15, len(barnamehs), 15):
                story.append(PageBreak())
                story.append(Paragraph(process_persian_text("اطلاعات بارنامه‌ها (ادامه)"), styles['RightTitle']))
                story.append(Spacer(1, 5 * mm))
                story.append(create_barnameh_table(doc_width, barnamehs, styles, i, 15))
    
    # Add footer
    story.append(Spacer(1, 20 * mm))
    story.append(create_footer_table(doc_width, styles))
    
    # Build the document
    doc.build(story)
    
    # If BytesIO, reset position to start
    if isinstance(output, BytesIO):
        output.seek(0)
    
    return output 