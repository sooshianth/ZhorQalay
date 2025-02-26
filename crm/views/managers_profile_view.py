from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.LogisticsManagerModel import LogisticsManager
from core.FinancialManagerModel import FinancialManager
from core.PurchaseModel import Purchase

@login_required
def logistics_manager_profile_view(request):
    manager = request.user.logistics_manager
    
    # Add these methods to the LogisticsManager instance
    def get_bazaargahed_purchases(logistics_manager):
        """Return all purchases that are bazaargahed (approved in bazaargah)"""
        return Purchase.objects.filter(
            is_bazaargahed=True,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')
    
    def get_takhsised_purchases(logistics_manager):
        """Return all purchases that are takhsised (allocated)"""
        return Purchase.objects.filter(
            is_takhsised=True,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')
    
    def get_other_active_purchases(logistics_manager):
        """Return all other active purchases that are neither bazaargahed nor takhsised"""
        return Purchase.objects.filter(
            is_bazaargahed=False,
            is_takhsised=False,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')
    
    # Attach these methods to the manager instance
    manager.get_bazaargahed_purchases = lambda: get_bazaargahed_purchases(manager)
    manager.get_takhsised_purchases = lambda: get_takhsised_purchases(manager)
    manager.get_other_active_purchases = lambda: get_other_active_purchases(manager)
    
    return render(request, 'logistics_manager_profile.html', {'manager': manager, 'user': request.user})

@login_required
def financial_manager_profile_view(request):
    manager = request.user.financial_manager
    return render(request, 'financial_manager_profile.html', {'manager': manager, 'user': request.user})