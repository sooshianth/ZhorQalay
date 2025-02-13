from core.models import SalesAgent, Customer, Purchase, CargoProduct, CallSession
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404

def customer_list(request):
    sales_agent = request.user
    customers = Customer.objects.filter(sales_agent = sales_agent)
    return render(request, 'customer_list.html', {'customers' : customers})

def customer_detail(request, pk):
    sales_agent = request.user  
    customer = get_object_or_404(Customer, pk=pk)

    if customer.sales_agent != sales_agent:
        raise Http404("شما اجازه دسترسی به این مشتری را ندارید!")

    return render(request, 'customers/customer_detail.html', {'customer': customer})

def task_list(request, pk):
    sales_agent = SalesAgent.objects.get(pk = pk)
    tasks =  sales_agent.get_today_tasks
    return render(request, 'task_list.html', {'tasks' : tasks})

def active_purchases(request):
    sales_agent = SalesAgent.objects.get(pk = pk)
    purchases = sales_agent.get_all_active_sales
    return render(request, 'active_purchases', {'purchases' : purchases})
