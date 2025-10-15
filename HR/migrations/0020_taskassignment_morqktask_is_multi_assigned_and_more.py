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
        ('HR', '0019_employee_is_manager_morqktask_monthlymorqksummary'),
    ]

    operations = [
        migrations.AddField(
            model_name='morqktask',
            name='is_multi_assigned',
            field=models.BooleanField(default=False, verbose_name='واگذاری چندنفره'),
        ),
        migrations.AlterField(
            model_name='morqktask',
            name='assigned_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='morqk_tasks', to=settings.AUTH_USER_MODEL, verbose_name='واگذار شده به'),
        ),
        migrations.CreateModel(
            name='TaskAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('percentage', models.PositiveIntegerField(help_text='درصد مشارکت این کارمند در انجام وظیفه', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name='درصد مشارکت')),
                ('status', models.CharField(choices=[('TODO', 'انجام نشده'), ('IN_PROGRESS', 'در حال انجام'), ('COMPLETED', 'تکمیل شده'), ('APPROVED', 'تایید شده')], default='TODO', max_length=20, verbose_name='وضعیت')),
                ('started_at', django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name='تاریخ شروع')),
                ('completed_at', django_jalali.db.models.jDateTimeField(blank=True, null=True, verbose_name='تاریخ تکمیل')),
                ('completion_note', models.TextField(blank=True, verbose_name='یادداشت تکمیل')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_assignments', to=settings.AUTH_USER_MODEL, verbose_name='کارمند')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='HR.morqktask', verbose_name='وظیفه')),
            ],
            options={
                'verbose_name': 'تخصیص کارمند به وظیفه',
                'verbose_name_plural': 'تخصیص\u200cهای کارمندان به وظایف',
                'ordering': ['-percentage'],
                'unique_together': {('task', 'employee')},
            },
        ),
    ]

