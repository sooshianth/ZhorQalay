from django.shortcuts import render, redirect
from core._models import VaredKonandeh
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from django.db.models import Q

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def vared_konandeh_list(request):
    """
    لیست واردکنندگان
    """
    user_role = determine_user_role(request.user)
    
    # جستجو
    query = request.GET.get('q', '')
    vared_konandehs = VaredKonandeh.objects.all()
    
    if query:
        vared_konandehs = vared_konandehs.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query) |
            Q(website__icontains=query)
        )
    
    return render(request, 'vared_konandeh_list.html', {
        'vared_konandehs': vared_konandehs,
        'user_role': user_role,
        'query': query
    })

@role_required('admin', 'logistics_manager')
@login_required
def vared_konandeh_add(request):
    """
    افزودن واردکننده جدید
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        website = request.POST.get('website')
        balance = request.POST.get('balance', 0)
        
        VaredKonandeh.objects.create(
            name=name,
            phone_number=phone_number,
            email=email,
            website=website,
            balance=balance
        )
        
        return redirect('vared_konandeh_list')
    
    return render(request, 'vared_konandeh_add.html')

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_vared_konandehs(request):
    """
    ویرایش گروهی واردکنندگان
    """
    if request.method == 'POST':
        selected_vared_konandeh_ids = request.POST.getlist('selected_vared_konandeh_ids')
        
        if not selected_vared_konandeh_ids:
            return redirect('vared_konandeh_list')
        
        # Get vared_konandehs by IDs
        selected_vared_konandehs = VaredKonandeh.objects.filter(id__in=selected_vared_konandeh_ids)
        
        # Check if updates are required
        if request.POST.get('update_phone'):
            phone_number = request.POST.get('phone_number')
            for vared_konandeh in selected_vared_konandehs:
                vared_konandeh.phone_number = phone_number
                vared_konandeh.save()
        
        if request.POST.get('update_email'):
            email = request.POST.get('email')
            for vared_konandeh in selected_vared_konandehs:
                vared_konandeh.email = email
                vared_konandeh.save()
        
        if request.POST.get('update_website'):
            website = request.POST.get('website')
            for vared_konandeh in selected_vared_konandehs:
                vared_konandeh.website = website
                vared_konandeh.save()
        
        if request.POST.get('update_balance'):
            balance = request.POST.get('balance')
            for vared_konandeh in selected_vared_konandehs:
                vared_konandeh.balance = balance
                vared_konandeh.save()
        
        return redirect('vared_konandeh_list')
    
    # Get vared_konandehs IDs from query parameters
    selected_vared_konandeh_ids = request.GET.getlist('ids')
    
    if not selected_vared_konandeh_ids:
        return redirect('vared_konandeh_list')
    
    selected_vared_konandehs = VaredKonandeh.objects.filter(id__in=selected_vared_konandeh_ids)
    
    return render(request, 'bulk_edit_vared_konandehs.html', {
        'selected_vared_konandehs': selected_vared_konandehs,
        'selected_vared_konandeh_ids': selected_vared_konandeh_ids
    }) 