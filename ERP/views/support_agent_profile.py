# support_agent_profile.py (updated)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.PurchaseModel import Purchase, determine_user_role
from core.decorators.decorators import role_required
from .managers_profile_view import get_client_ip
from core._models import SupportAgentTask, SupportAgent, AdminTask
from django.db.models import Q
from django_jalali.db import models as jmodels
from django.utils import timezone
import logging
logger = logging.getLogger("erp_managers_profile_view")

@role_required('support_agent', 'admin')
@login_required
@csrf_exempt
def support_agent_profile_view(request):
    logger.warning(f"Support Agent Profile View accessed by user: {request.user.username}, IP: {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        action = request.POST.get('action')
        feedback = request.POST.get('feedback', '')
        task_type = request.POST.get('task_type', 'support')  # support یا admin
        
        try:
            if task_type == 'admin' and user_role == 'admin':
                # پردازش تسک‌های مدیریت
                admin_task = AdminTask.objects.get(id=task_id)
                
                if action == 'complete':
                    admin_task.is_done = True
                    admin_task.admin_feedback = feedback
                    admin_task.completed_at = timezone.now()
                    admin_task.save()
                    
                    # به‌روزرسانی تسک کارشناس پشتیبانی مربوطه
                    support_task = admin_task.referred_from_task
                    support_task.is_done = True
                    support_task.feedback = f"تسک توسط مدیریت تکمیل شد: {feedback}"
                    support_task.save()
                    
                    return JsonResponse({'status': 'success', 'message': 'تسک مدیریت با موفقیت تکمیل شد'})
                    
            elif task_type == 'support' and user_role == 'support_agent':
                # پردازش تسک‌های کارشناس پشتیبانی
                agent = request.user.support_agent
                task = SupportAgentTask.objects.get(id=task_id, support_agent=agent)
                
                if action == 'complete':
                    task.is_done = True
                    task.is_on_admin = False
                    task.feedback = feedback
                    task.save()
                    return JsonResponse({'status': 'success', 'message': 'تسک با موفقیت انجام شد'})
                    
                elif action == 'refer':
                    # ایجاد تسک مدیریت از تسک کارشناس پشتیبانی
                    admin_task = AdminTask.create_from_support_task(task, feedback)
                    
                    # به‌روزرسانی وضعیت تسک کارشناس پشتیبانی
                    task.is_on_admin = True
                    task.is_done = False
                    task.feedback = feedback
                    task.save()
                    
                    logger.info(f"Task {task.id} referred to admin. Admin task created with ID: {admin_task.id}")
                    
                    return JsonResponse({
                        'status': 'success', 
                        'message': 'تسک با موفقیت به مدیریت ارجاع شد',
                        'admin_task_id': admin_task.id
                    })
            else:
                return JsonResponse({'status': 'error', 'message': 'دسترسی غیرمجاز'}, status=403)
                
        except (SupportAgentTask.DoesNotExist, AdminTask.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'تسک مورد نظر یافت نشد'}, status=404)
        except Exception as e:
            logger.error(f"Error in task update: {str(e)}")
            return JsonResponse({'status': 'error', 'message': f'خطای سرور: {str(e)}'}, status=500)
    
    # دریافت داده‌ها بر اساس نقش کاربر
    if user_role == 'support_agent':
        agent = request.user.support_agent
        
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
        
        # تسک‌های مدیریت ایجاد شده از این کارشناس
        admin_tasks = AdminTask.objects.filter(
            referred_from_agent=agent
        ).order_by('-created_at')[:20]
        
        admin_completed_tasks = []
        
    elif user_role == 'admin':
        # برای ادمین، نمایش همه تسک‌های مدیریت
        active_tasks = []
        done_tasks = []
        admin_referred_tasks = []
        
        # تسک‌های مدیریت فعال
        admin_tasks = AdminTask.objects.filter(
            is_done=False
        ).order_by(
            '-urgency_level',
            'due_date',
            'created_at'
        )
        
        # تسک‌های مدیریت تکمیل شده
        admin_completed_tasks = AdminTask.objects.filter(
            is_done=True
        ).order_by('-completed_at')[:20]
    
    return render(request, 'support_agent_profile.html', {
        'user_role': user_role,
        'agent': getattr(request.user, 'support_agent', None),
        'user': request.user,
        'active_tasks': active_tasks,
        'done_tasks': done_tasks,
        'admin_referred_tasks': admin_referred_tasks,
        'admin_tasks': admin_tasks,
        'admin_completed_tasks': admin_completed_tasks
    })