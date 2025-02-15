# views.py
from django.shortcuts import render, redirect
from django.views.generic import FormView
from django.contrib import messages
from core.models import Customer
from .customer_form import CustomerSearchForm, CustomerCreateForm

class CustomerSearchView(FormView):
    form_class = CustomerSearchForm
    template_name = 'customers/search.html'
    
    def form_valid(self, form):
        phone = form.cleaned_data['phone_number']
        try:
            customer = Customer.objects.get(phone_number=phone)
            return render(self.request, 'customers/customer_detail.html', {'customer': customer})
        except Customer.DoesNotExist:
            self.request.session['phone_number'] = phone  # ذخیره شماره برای فرم بعدی
            return redirect('customer_create')

class CustomerCreateView(FormView):
    form_class = CustomerCreateForm
    template_name = 'customers/create.html'
    
    def get_initial(self):
        initial = super().get_initial()
        initial['phone_number'] = self.request.session.get('phone_number', '')
        return initial
    
    def form_valid(self, form):
        try:
            customer = form.save(commit=False)
            customer.sales_agent = self.request.user.salesagent  # فرض بر اینکه کاربر مرتبط هست
            customer.save()
            messages.success(self.request, 'مشتری با موفقیت ثبت شد')
            return redirect('customer_detail', pk=customer.pk)
        except Exception as e:
            messages.error(self.request, f'خطا در ثبت: {str(e)}')
            return redirect('customer_search')