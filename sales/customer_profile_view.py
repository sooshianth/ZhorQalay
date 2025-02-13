from django.shortcuts import render, redirect, get_object_or_404
from .forms import CustomerForm  # Ensure the correct import path
from core.CustomerModel import Customer

def create_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():  
            form.save()
            return redirect('customer_list')  # Replace 'customer_list' with the appropriate URL name
    else:
        form = CustomerForm()
    return render(request, 'customer_form.html', {'form': form})  # Replace 'customer_form.html' with the appropriate template name

def edit_customer(request, pk):
    customer = get_object_or_404(Customer, pk = pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():  
            form.save()
            return redirect('customer_list')  # Replace 'customer_list' with the appropriate URL name
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customer_form.html', {'form': form}) 
