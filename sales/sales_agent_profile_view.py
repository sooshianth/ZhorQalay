from core.models import SalesAgent, Customer, Purchase, CargoProduct, CallSession
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import Http404
from django.views import View

class SalesAgentProfileView(View):
    template_name = 'sales_agent_profile.html'

    def get(self, request):
        sales_agent = request.user.sales_agent  

        customers = sales_agent.get_all_customer()

        tasks_today = sales_agent.get_today_tasks()

        active_sales_today = sales_agent.get_all_active_sales().filter(created_at__date=timezone.now().date())

        total_sales_this_month = sales_agent.get_this_month_sales_amount()

        context = {
            'sales_agent': sales_agent,
            'customers': customers,
            'tasks_today': tasks_today,
            'active_sales_today': active_sales_today,
            'total_sales_this_month': total_sales_this_month,
        }

        return render(request, self.template_name, context)