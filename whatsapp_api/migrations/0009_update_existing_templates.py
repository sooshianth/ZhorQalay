# Generated manually for updating existing templates

from django.db import migrations

def update_template_types(apps, schema_editor):
    """
    بروزرسانی انواع قالب‌های موجود
    """
    WhatsappTemplate = apps.get_model('whatsapp_api', 'WhatsappTemplate')
    
    # تمام قالب‌های موجود را به نوع 'purchase' تبدیل می‌کنیم
    WhatsappTemplate.objects.all().update(template_type='purchase')

def reverse_update_template_types(apps, schema_editor):
    """
    برگرداندن تغییرات
    """
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_api', '0008_update_template_types'),
    ]

    operations = [
        migrations.RunPython(update_template_types, reverse_update_template_types),
    ] 