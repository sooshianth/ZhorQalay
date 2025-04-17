from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def logistics_manager_profile_view(request):
    manager = request.user.logistics_manager
    return render(request, 'logistics_manager_profile.html', {'manager': manager, 'user': request.user})

@login_required
def financial_manager_profile_view(request):
    manager = request.user.financial_manager
    return render(request, 'financial_manager_profile.html', {'manager': manager, 'user': request.user})

@login_required
def support_agent_profile_view(request):
    agent = request.user.support_agent
    return render(request, 'support_agent_profile.html', {'agent': agent, 'user': request.user})


