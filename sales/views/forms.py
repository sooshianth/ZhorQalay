from django import forms
from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import CaptchaField

class SalesAgentLoginForm(AuthenticationForm):
    captcha = CaptchaField()

class LogisticsManagerLoginForm(AuthenticationForm):
    captcha = CaptchaField()

class FinancialManagerLoginForm(AuthenticationForm):
    captcha = CaptchaField()