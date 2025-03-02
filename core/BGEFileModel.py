from django.db import models
from django_jalali.db import models as jmodels
from .CargoProductModel import CargoProduct
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import os


class BGEFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='users_bge_files')
    cargo = models.ForeignKey(CargoProduct, on_delete=models.DO_NOTHING, related_name='cargos_bge_files')
    file = models.FileField(upload_to='excel_files/',)
    created_at = jmodels.jDateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False, verbose_name=_('تأیید شده'))

    class Meta:
        verbose_name = _('فایل اکسل بازارگاه')
        verbose_name_plural = _('فایل‌های اکسل بازارگاه')

    def __str__(self):
        return self.file.name
    
    def change_file_name(self, new_name):
        old_path = self.file.path
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        os.rename(old_path, new_path)
        self.file.name = os.path.join('excel_files', new_name)
        # self.file.path = new_path
        self.save()

    def return_path(self):
        return self.file.path