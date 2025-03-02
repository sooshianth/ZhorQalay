from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _ 
from .CustomerModel import Customer


class CallSession(models.Model):
    CALL_TYPE = [
        ('incoming','ورودی'),
        ('outgoing','خروجی'),
    ]
    CALL_STATUS = [
        ('successful','موفق'),
        ('pending','در انتظار'),
        ('failed','ناموفق'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name=_('مشتری'), related_name='calls')
    type = models.CharField(_('نوع تماس'), max_length=10, choices=CALL_TYPE)
    status = models.CharField(_('وضعیت'), max_length=15, choices=CALL_STATUS)
    date = jmodels.jDateTimeField(_('تاریخ تماس') , auto_now_add=True)
    note = models.TextField(_('یادداشت '), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _('تماس')
        verbose_name_plural = _('تماس‌ها')

    def __str__(self):
        return f"{self.customer.name} - {self.date}"
    
    def clean(self):
        if self.type not in dict(self.CALL_TYPE).keys():
            raise ValidationError(_('نوع تماس نامعتبر است.'))
        
        if self.status not in dict(self.CALL_STATUS).keys():
            raise ValidationError(_('وضعیت تماس نامعتبر است.'))
        
        if self.note and len(self.note) > 255:
            raise ValidationError(_('طول یادداشت نباید بیشتر از 255 کاراکتر باشد.'))
        
        super().clean()

