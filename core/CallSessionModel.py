from django.db import models
from django.core.exceptions import ValidationError
from . import CustomerModel

class CallSession(models.Model):
    
    CALL_TYPE = [
        {'incoming','ورودی'},
        {'outgoing','خروجی'},
    ]

    CALL_STATUS = [
        {'successful','موفق'},
        {'pending','در انتظار'},
        {'failed','ناموفق'},
    ]

    #مشتری
    customer = models.ForeignKey(CustomerModel, on_delete=models.CASCADE)

    #نوع تماس
    type = models.CharField(_('نوع تماس'), max_length=10, choices=CALL_TYPE)

    #وضعیت تماس
    status = models.CharField(_('وضعیت'), max_length=15, choices=CALL_STATUS)

    #زمان انجام شدن آن تماس
    date = models.DateTimeField(_('تاریخ تماس') , auto_now_add=True)

    #یادداشت در صورت لزوم
    notes = models.TimeField(_('یادداشت ها'), blank=True, null=True)

    class Meta:
        verbos_name = _('تماس')
        verbos_name_plural = _('تماس ها')

    def __str__(self):
        return f"{self.customer.name} - {self.date}"