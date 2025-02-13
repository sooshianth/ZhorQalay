from django import forms
from core.CustomerModel import Customer

class CustomerForm(forms.ModelForm):
    
    class Meta:
        model = Customer
        fields = '__all__'
