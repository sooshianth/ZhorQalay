from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from core._models import LogisticsManager, FinancialManager

@login_required
def logistics_manager_profile_view(request):
    manager = request.user.logistics_manager
    return render(request, 'logistics_manager_profile.html', {'manager': manager, 'user': request.user})

@login_required
def financial_manager_profile_view(request):
    manager = request.user.financial_manager
    return render(request, 'financial_manager_profile.html', {'manager': manager, 'user': request.user})