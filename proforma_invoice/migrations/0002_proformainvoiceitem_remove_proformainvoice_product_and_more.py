# Generated manually

import django.core.validators
import django.db.models.deletion
import django_jalali.db.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proforma_invoice', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # حذف فیلدهای محصول از ProformaInvoice
        migrations.RemoveField(
            model_name='proformainvoice',
            name='product',
        ),
        migrations.RemoveField(
            model_name='proformainvoice',
            name='product_name',
        ),
        migrations.RemoveField(
            model_name='proformainvoice',
            name='product_description',
        ),
        migrations.RemoveField(
            model_name='proformainvoice',
            name='quantity',
        ),
        migrations.RemoveField(
            model_name='proformainvoice',
            name='unit',
        ),
        migrations.RemoveField(
            model_name='proformainvoice',
            name='unit_price',
        ),
        
        # ایجاد مدل ProformaInvoiceItem با GenericForeignKey
        migrations.CreateModel(
            name='ProformaInvoiceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('product_name', models.CharField(max_length=200, verbose_name='نام محصول')),
                ('product_description', models.TextField(blank=True, null=True, verbose_name='توضیحات محصول')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name='مقدار')),
                ('unit', models.CharField(choices=[('kg', 'کیلوگرم'), ('ton', 'تن'), ('bag', 'کیسه')], default='kg', max_length=10, verbose_name='واحد')),
                ('unit_price', models.DecimalField(decimal_places=0, max_digits=15, validators=[django.core.validators.MinValueValidator(0)], verbose_name='قیمت واحد (ریال)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='ترتیب')),
                ('content_type', models.ForeignKey(blank=True, limit_choices_to={'model__in': ('cargoproduct', 'nonbazargahproduct')}, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
                ('proforma', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='proforma_invoice.proformainvoice', verbose_name='پیش فاکتور')),
            ],
            options={
                'verbose_name': 'آیتم پیش فاکتور',
                'verbose_name_plural': 'آیتم\u200cهای پیش فاکتور',
                'ordering': ['order', 'id'],
            },
        ),
    ]

