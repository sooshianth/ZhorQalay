from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt  # اضافه شده
from core.PurchaseModel import Purchase, determine_user_role
from core.decorators.decorators import role_required
from .managers_profile_view import get_client_ip
from core._models import SupportAgentTask, SupportAgent
from django.db.models import Q
import logging
logger = logging.getLogger("erp_managers_profile_view")

@role_required('support_agent')
@login_required
@csrf_exempt  # اضافه شده برای تست (در محیط تولید باید حذف شود)
def support_agent_profile_view(request):
    logger.warning(f"Support Agent Profile View accessed by user: {request.user.username}, IP: {get_client_ip(request)}")
    
    agent = request.user.support_agent
    
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        action = request.POST.get('action')
        
        try:
            task = SupportAgentTask.objects.get(id=task_id, support_agent=agent)
            
            if action == 'complete':
                task.is_done = True
                task.is_on_admin = False
                task.save()
                return JsonResponse({'status': 'success', 'message': 'تسک با موفقیت انجام شد'})
                
            elif action == 'refer':
                task.is_on_admin = True
                task.is_done = False
                task.save()
                return JsonResponse({'status': 'success', 'message': 'تسک با موفقیت به مدیریت ارجاع شد'})
                
        except SupportAgentTask.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'تسک مورد نظر یافت نشد'}, status=404)
        except Exception as e:
            logger.error(f"Error in task update: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'خطای سرور'}, status=500)
    
    # بقیه کدهای GET بدون تغییر
    active_tasks = SupportAgentTask.objects.filter(
        support_agent=agent,
        is_done=False,
        is_on_admin=False
    ).order_by(
        '-urgency_level',
        'due_date',
        'created_at'
    )
    
    done_tasks = SupportAgentTask.objects.filter(
        support_agent=agent,
        is_done=True
    ).order_by('-created_at')[:20]
    
    admin_referred_tasks = SupportAgentTask.objects.filter(
        support_agent=agent,
        is_on_admin=True,
        is_done=False
    ).order_by('-created_at')
    
    return render(request, 'support_agent_profile.html', {
        'agent': agent,
        'user': request.user,
        'active_tasks': active_tasks,
        'done_tasks': done_tasks,
        'admin_referred_tasks': admin_referred_tasks
    })

def refer_task_to_admin(request, task_id):
    task = SupportAgentTask.objects.get(id=task_id)
    task.is_on_admin = True
    task.save()

    return redirect('support_agent_profile')

def mark_task_done(request, task_id):
    task = SupportAgentTask.objects.get(id=task_id)
    task.is_done = True
    task.save()

    return redirect('support_agent_profile')