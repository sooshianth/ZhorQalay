from django.shortcuts import render, redirect
from core._models import Barbary
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from django.db.models import Q

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def barbary_list(request):
    """
    لیست باربری‌ها
    """
    user_role = determine_user_role(request.user)
    
    # جستجو
    query = request.GET.get('q', '')
    barbaries = Barbary.objects.all()
    
    if query:
        barbaries = barbaries.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query) |
            Q(description__icontains=query)
        )
    
    return render(request, 'barbary_list.html', {
        'barbaries': barbaries,
        'user_role': user_role,
        'query': query
    })

@role_required('admin', 'logistics_manager')
@login_required
def barbary_add(request):
    """
    افزودن باربری جدید
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        description = request.POST.get('description')
        
        Barbary.objects.create(
            name=name,
            phone_number=phone_number,
            email=email,
            description=description
        )
        
        return redirect('barbary_list')
    
    return render(request, 'barbary_add.html')

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_barbaries(request):
    """
    ویرایش گروهی باربری‌ها
    """
    if request.method == 'POST':
        selected_barbary_ids = request.POST.getlist('selected_barbary_ids')
        
        if not selected_barbary_ids:
            return redirect('barbary_list')
        
        # Get barbaries by IDs
        selected_barbaries = Barbary.objects.filter(id__in=selected_barbary_ids)
        
        # Check if updates are required
        if request.POST.get('update_phone'):
            phone_number = request.POST.get('phone_number')
            for barbary in selected_barbaries:
                barbary.phone_number = phone_number
                barbary.save()
        
        if request.POST.get('update_email'):
            email = request.POST.get('email')
            for barbary in selected_barbaries:
                barbary.email = email
                barbary.save()
        
        if request.POST.get('update_description'):
            description = request.POST.get('description')
            for barbary in selected_barbaries:
                barbary.description = description
                barbary.save()
        
        return redirect('barbary_list')
    
    # Get barbaries IDs from query parameters
    selected_barbary_ids = request.GET.getlist('ids')
    
    if not selected_barbary_ids:
        return redirect('barbary_list')
    
    selected_barbaries = Barbary.objects.filter(id__in=selected_barbary_ids)
    
    return render(request, 'bulk_edit_barbaries.html', {
        'selected_barbaries': selected_barbaries,
        'selected_barbary_ids': selected_barbary_ids
    }) 