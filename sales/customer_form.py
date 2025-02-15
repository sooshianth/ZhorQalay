from django import forms
from core.models import Customer

class CustomerSearchForm(forms.Form):
    phone_number = forms.CharField(
        label='شماره تلفن',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '09xxxxxxxxx',
            'class': 'form-control persian-number'
        })
    )

class CustomerCreateForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'phone_number', 'name', 'city', 
            'field_of_activity', 'purchase_preferences',
            'product_preferences', 'contact_start_time',
            'contact_end_time', 'social_media', 'added_description',
            'sms_preference', 'quota'
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'readonly': 'readonly',
                'class': 'form-control persian-number'
            }),
            'contact_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'contact_end_time': forms.TimeInput(attrs={'type': 'time'}),
        }