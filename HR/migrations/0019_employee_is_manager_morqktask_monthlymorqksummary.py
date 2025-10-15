# Generated manually

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_jalali.db.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('HR', '0018_attendanceconfiguration'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='is_manager',
            field=models.BooleanField(default=False, verbose_name='مدیر است'),
        ),
        migrations.CreateModel(
            name='MorqkTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان وظیفه')),
                ('description', models.TextField(blank=True, verbose_name='شرح وظیفه')),
                ('morqk_value', models.DecimalField(choices=[(0.5, '0.5'), (1, '1'), (2, '2'), (3, '3'), (5, '5'), (8, '8'), (13, '13'), (20, '20'), (40, '40')], decimal_places=1, max_digits=5, validators=[django.core.validators.MinValueValidator(0.5)], verbose_name='مقدار مرغک')),
                ('status', models.CharField(choices=[('TODO', 'انجام نشده'), ('IN_PROGRESS', 'در حال انجام'), ('PENDING_APPROVAL', 'در انتظار تایید'), ('APPROVED', 'تایید شده'), ('REJECTED', 'رد شده')], default='TODO', max_length=20, verbose_name='وضعیت')),
                ('created_at', django_jalali.db.models.jDateTimeField(default=django.utils.timezone.now, verbose_name='تاریخ ایجاد')),
                ('due_date', django_jalali.db.models.jDateField(blank=True, null=True, verbose_name='مهلت انجام')),
                ('completed_at', django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name='تاریخ تکمیل')),
                ('approved_at', django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name='تاریخ تایید')),
                ('completion_note', models.TextField(blank=True, help_text='توضیحات کارمند هنگام تکمیل وظیفه', verbose_name='یادداشت تکمیل')),
                ('approval_note', models.TextField(blank=True, help_text='نظر مدیر هنگام تایید/رد', verbose_name='یادداشت تایید')),
                ('rejection_note', models.TextField(blank=True, help_text='دلیل رد توسط مدیر', verbose_name='دلیل رد')),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_morqk_tasks', to=settings.AUTH_USER_MODEL, verbose_name='تایید شده توسط')),
                ('assigned_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='morqk_tasks', to=settings.AUTH_USER_MODEL, verbose_name='واگذار شده به')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_morqk_tasks', to=settings.AUTH_USER_MODEL, verbose_name='ایجاد شده توسط')),
            ],
            options={
                'verbose_name': 'وظیفه مرغک',
                'verbose_name_plural': 'وظایف مرغک',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MonthlyMorqkSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(max_length=7, verbose_name='ماه (YYYY-MM)')),
                ('total_approved_morqk', models.DecimalField(decimal_places=1, default=0, max_digits=8, verbose_name='مجموع مرغک تایید شده')),
                ('total_tasks', models.PositiveIntegerField(default=0, verbose_name='تعداد کل وظایف')),
                ('completed_tasks', models.PositiveIntegerField(default=0, verbose_name='تعداد وظایف تکمیل شده')),
                ('approved_tasks', models.PositiveIntegerField(default=0, verbose_name='تعداد وظایف تایید شده')),
                ('last_updated', django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='کارمند')),
            ],
            options={
                'verbose_name': 'خلاصه ماهانه مرغک',
                'verbose_name_plural': 'خلاصه‌های ماهانه مرغک',
                'ordering': ['-month', 'employee'],
                'unique_together': {('employee', 'month')},
            },
        ),
    ]

