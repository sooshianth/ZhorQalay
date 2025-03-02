from django import forms
from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import CaptchaField


class SalesAgentLoginForm(AuthenticationForm):
    # captcha = CaptchaField(label='کد امنیتی')

    # def clean_captcha(self):
    #     captcha = self.cleaned_data.get('captcha')
    #     if not captcha:
    #         raise forms.ValidationError('لطفا کد را وارد کنید')
    #     return captcha
    pass
    
class LogisticsManagerLoginForm(AuthenticationForm):
    # captcha = CaptchaField(label='کد امنیتی')

    # def clean_captcha(self):
    #     captcha = self.cleaned_data.get('captcha')
    #     if not captcha:
    #         raise forms.ValidationError('لطفا کد را وارد کنید')
    #     return captcha
    pass

class FinancialManagerLoginForm(AuthenticationForm):
    # captcha = CaptchaField(label='کد امنیتی')
    
    # def clean_captcha(self):
    #     captcha = self.cleaned_data.get('captcha')
    #     if not captcha:
    #         raise forms.ValidationError('لطفا کد را وارد کنید')
    #     return captcha
    pass