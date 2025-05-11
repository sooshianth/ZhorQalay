from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from core._models import ToDoItem, TaskCategory, TaskReminder

@login_required
def task_dashboard_view(request):
    # Get pending tasks for today's focus
    pending_tasks = ToDoItem.objects.filter(
        user=request.user, 
        status__in=['pending', 'in_progress'],
        is_completed=False
    ).order_by('-priority', 'due_date', 'due_time')
    
    # Show overdue tasks first
    today = timezone.localdate()
    overdue_tasks = pending_tasks.filter(due_date__lt=today)
    due_today_tasks = pending_tasks.filter(due_date=today)
    upcoming_tasks = pending_tasks.filter(Q(due_date__gt=today) | Q(due_date=None))[:5]
    
    # Recently completed tasks
    recently_completed = ToDoItem.objects.filter(
        user=request.user, 
        status='completed',
        is_completed=True
    ).order_by('-completed_at')[:5]
    
    # Get all categories for sidebar
    categories = TaskCategory.objects.filter(
        tasks__user=request.user
    ).annotate(
        task_count=Count('tasks', filter=Q(tasks__is_completed=False))
    ).filter(task_count__gt=0).order_by('name')
    
    # Task count by priority
    priority_counts = {
        'urgent': pending_tasks.filter(priority='urgent').count(),
        'high': pending_tasks.filter(priority='high').count(),
        'medium': pending_tasks.filter(priority='medium').count(),
        'low': pending_tasks.filter(priority='low').count(),
    }
    
    # Get all unique tags
    all_tasks = ToDoItem.objects.filter(user=request.user)
    tags = set()
    for task in all_tasks:
        if task.tags:
            tags.update(task.get_tags_list())
    
    context = {
        'overdue_tasks': overdue_tasks,
        'due_today_tasks': due_today_tasks,
        'upcoming_tasks': upcoming_tasks,
        'recently_completed': recently_completed,
        'categories': categories,
        'priority_counts': priority_counts,
        'tags': sorted(tags),
        'total_pending': pending_tasks.count(),
        'total_completed': recently_completed.count(),
    }
    return render(request, 'task_dashboard.html', context)

@login_required
def task_list_view(request):
    # Get filter parameters
    category_id = request.GET.get('category')
    status = request.GET.get('status', 'active')  # Default to active tasks
    priority = request.GET.get('priority')
    tag = request.GET.get('tag')
    search = request.GET.get('search')
    
    # Base queryset - user's tasks
    tasks = ToDoItem.objects.filter(user=request.user)
    
    # Apply filters
    if status == 'active':
        tasks = tasks.filter(status__in=['pending', 'in_progress'])
    elif status == 'completed':
        tasks = tasks.filter(status='completed')
    elif status == 'deferred':
        tasks = tasks.filter(status='deferred')
    elif status == 'canceled':
        tasks = tasks.filter(status='canceled')
    elif status != 'all':  # If not 'all', filter by specific status
        tasks = tasks.filter(status=status)
    
    if category_id:
        tasks = tasks.filter(category_id=category_id)
    
    if priority:
        tasks = tasks.filter(priority=priority)
    
    if tag:
        tasks = tasks.filter(tags__icontains=tag)
    
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(notes__icontains=search)
        )
    
    # Order tasks
    order_by = request.GET.get('order_by', '-priority')
    if order_by == 'due_date':
        tasks = tasks.order_by('due_date', 'due_time', '-priority')
    elif order_by == '-due_date':
        tasks = tasks.order_by('-due_date', '-due_time', '-priority')
    elif order_by in ['title', '-title', 'created_at', '-created_at', 'priority', '-priority']:
        tasks = tasks.order_by(order_by)
    else:
        tasks = tasks.order_by('-priority', 'due_date', 'due_time')
    
    # Pagination
    paginator = Paginator(tasks, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all categories for filters
    categories = TaskCategory.objects.filter(
        tasks__user=request.user
    ).distinct().order_by('name')
    
    # Get all unique tags for filters
    all_tags = set()
    for task in ToDoItem.objects.filter(user=request.user):
        if task.tags:
            all_tags.update(task.get_tags_list())
    
    context = {
        'page_obj': page_obj,
        'tasks': page_obj.object_list,
        'categories': categories,
        'tags': sorted(all_tags),
        'active_category': category_id,
        'active_status': status,
        'active_priority': priority,
        'active_tag': tag,
        'search_query': search,
        'order_by': order_by,
    }
    return render(request, 'task_list.html', context)

@login_required
def task_detail_view(request, task_id):
    task = get_object_or_404(ToDoItem, id=task_id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(ToDoItem.STATUS_CHOICES):
                task.status = new_status
                task.save()
                messages.success(request, 'وضعیت تسک با موفقیت بروزرسانی شد.')
                
        elif action == 'update_priority':
            new_priority = request.POST.get('priority')
            if new_priority in dict(ToDoItem.PRIORITY_CHOICES):
                task.priority = new_priority
                task.save()
                messages.success(request, 'اولویت تسک با موفقیت بروزرسانی شد.')
                
        return redirect('task_detail', task_id=task.id)
    
    context = {
        'task': task,
        'tags': task.get_tags_list(),
        'status_choices': ToDoItem.STATUS_CHOICES,
        'priority_choices': ToDoItem.PRIORITY_CHOICES,
    }
    return render(request, 'task_detail.html', context)

@login_required
def create_task_view(request):
    categories = TaskCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'medium')
        status = request.POST.get('status', 'pending')
        category_id = request.POST.get('category')
        tags = request.POST.get('tags')
        notes = request.POST.get('notes')
        due_date = request.POST.get('due_date')
        due_time = request.POST.get('due_time')
        color = request.POST.get('color')
        remind_before = request.POST.get('remind_before', 0)
        
        if not title:
            messages.error(request, 'عنوان تسک الزامی است.')
            return render(request, 'create_task.html', {'categories': categories})
        
        task = ToDoItem.objects.create(
            user=request.user,
            title=title,
            description=description,
            priority=priority,
            status=status,
            category_id=category_id if category_id else None,
            tags=tags,
            notes=notes,
            due_date=due_date if due_date else None,
            due_time=due_time if due_time else None,
            color=color,
            remind_before=remind_before
        )
        
        # Create reminder if needed
        if due_date and due_time and int(remind_before) > 0:
            due_datetime = timezone.datetime.combine(
                task.due_date,
                task.due_time
            )
            reminder_time = due_datetime - timezone.timedelta(minutes=int(remind_before))
            TaskReminder.objects.create(
                task=task,
                reminder_time=reminder_time
            )
        
        messages.success(request, 'تسک با موفقیت ایجاد شد.')
        return redirect('task_dashboard')
    
    return render(request, 'create_task.html', {'categories': categories})

@login_required
def edit_task_view(request, task_id):
    task = get_object_or_404(ToDoItem, id=task_id, user=request.user)
    categories = TaskCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority')
        status = request.POST.get('status')
        category_id = request.POST.get('category')
        tags = request.POST.get('tags')
        notes = request.POST.get('notes')
        due_date = request.POST.get('due_date')
        due_time = request.POST.get('due_time')
        color = request.POST.get('color')
        remind_before = request.POST.get('remind_before', 0)
        
        if not title:
            messages.error(request, 'عنوان تسک الزامی است.')
            return render(request, 'edit_task.html', {'task': task, 'categories': categories})
        
        task.title = title
        task.description = description
        task.priority = priority
        task.status = status
        task.category_id = category_id if category_id else None
        task.tags = tags
        task.notes = notes
        task.due_date = due_date if due_date else None
        task.due_time = due_time if due_time else None
        task.color = color
        task.remind_before = remind_before
        task.save()
        
        # Update reminder
        TaskReminder.objects.filter(task=task).delete()
        if due_date and due_time and int(remind_before) > 0:
            due_datetime = timezone.datetime.combine(
                task.due_date,
                task.due_time
            )
            reminder_time = due_datetime - timezone.timedelta(minutes=int(remind_before))
            TaskReminder.objects.create(
                task=task,
                reminder_time=reminder_time
            )
        
        messages.success(request, 'تسک با موفقیت بروزرسانی شد.')
        return redirect('task_detail', task_id=task.id)
    
    context = {
        'task': task,
        'categories': categories,
        'tags': ','.join(task.get_tags_list()),
    }
    return render(request, 'edit_task.html', context)

@require_POST
@login_required
def change_task_status(request, task_id):
    task = get_object_or_404(ToDoItem, id=task_id, user=request.user)
    new_status = request.POST.get('status')
    
    if new_status in dict(ToDoItem.STATUS_CHOICES):
        task.status = new_status
        task.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'status': task.status,
                'status_display': dict(ToDoItem.STATUS_CHOICES)[task.status],
                'is_completed': task.is_completed
            })
    
    redirect_url = request.POST.get('redirect_url') or reverse('task_dashboard')
    return HttpResponseRedirect(redirect_url)

@login_required
def completed_tasks_view(request):
    tasks = ToDoItem.objects.filter(user=request.user, status='completed').order_by('-completed_at')
    return render(request, 'completed_tasks.html', {'tasks': tasks})

@login_required
def manage_categories_view(request):
    categories = TaskCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            color = request.POST.get('color', '#3498db')
            icon = request.POST.get('icon', 'fa-tasks')
            
            if name:
                TaskCategory.objects.create(name=name, color=color, icon=icon)
                messages.success(request, 'دسته‌بندی با موفقیت ایجاد شد.')
            else:
                messages.error(request, 'نام دسته‌بندی الزامی است.')
        
        elif action == 'update':
            category_id = request.POST.get('category_id')
            name = request.POST.get('name')
            color = request.POST.get('color')
            icon = request.POST.get('icon')
            
            if category_id and name:
                category = get_object_or_404(TaskCategory, id=category_id)
                category.name = name
                category.color = color
                category.icon = icon
                category.save()
                messages.success(request, 'دسته‌بندی با موفقیت بروزرسانی شد.')
        
        elif action == 'delete':
            category_id = request.POST.get('category_id')
            if category_id:
                category = get_object_or_404(TaskCategory, id=category_id)
                category.delete()
                messages.success(request, 'دسته‌بندی با موفقیت حذف شد.')
        
        return redirect('manage_categories')
    
    return render(request, 'manage_categories.html', {'categories': categories})

@login_required
def task_analytics_view(request):
    # Tasks by status
    all_tasks = ToDoItem.objects.filter(user=request.user)
    status_counts = {
        status: all_tasks.filter(status=status).count()
        for status, _ in ToDoItem.STATUS_CHOICES
    }
    
    # Tasks by priority
    priority_counts = {
        priority: all_tasks.filter(priority=priority).count()
        for priority, _ in ToDoItem.PRIORITY_CHOICES
    }
    
    # Tasks by category
    category_counts = []
    categories = TaskCategory.objects.filter(tasks__user=request.user).distinct()
    for category in categories:
        count = all_tasks.filter(category=category).count()
        category_counts.append({
            'name': category.name,
            'count': count,
            'color': category.color
        })
    
    # Tasks by month (last 6 months)
    today = timezone.now().date()
    months = []
    for i in range(5, -1, -1):
        start_date = (today.replace(day=1) - timezone.timedelta(days=i*30)).replace(day=1)
        if i > 0:
            end_date = (today.replace(day=1) - timezone.timedelta(days=(i-1)*30)).replace(day=1) - timezone.timedelta(days=1)
        else:
            end_date = today
        
        completed = all_tasks.filter(completed_at__date__range=[start_date, end_date]).count()
        created = all_tasks.filter(created_at__date__range=[start_date, end_date]).count()
        
        months.append({
            'month': start_date.strftime('%Y-%m'),
            'month_name': start_date.strftime('%B %Y'),
            'completed': completed,
            'created': created
        })
    
    context = {
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'category_counts': category_counts,
        'monthly_stats': months,
        'total_tasks': all_tasks.count(),
        'completed_tasks': all_tasks.filter(status='completed').count(),
        'overdue_tasks': sum(1 for task in all_tasks.filter(status__in=['pending', 'in_progress']) if task.is_overdue()),
    }
    
    return render(request, 'task_analytics.html', context)

@require_POST
@login_required
def toggle_task_status(request):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    
    task_id = request.POST.get('task_id')
    if not task_id:
        return JsonResponse({'success': False, 'error': 'Task ID required'}, status=400)
    
    try:
        task = ToDoItem.objects.get(id=task_id, user=request.user)
    except ToDoItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    
    # Toggle between completed and pending
    if task.status == 'completed':
        task.status = 'pending'
    else:
        task.status = 'completed'
    
    task.save()
    
    return JsonResponse({
        'success': True,
        'status': task.status,
        'is_completed': task.is_completed,
        'completed_at': task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else None
    })

@login_required
def search_tasks(request):
    query = request.GET.get('q', '')
    
    if len(query) < 3:
        return JsonResponse({'results': [], 'error': 'جستجو باید حداقل ۳ کاراکتر باشد'})
    
    tasks = ToDoItem.objects.filter(
        user=request.user).filter(
        Q(title__icontains=query) | 
        Q(description__icontains=query) |
        Q(tags__icontains=query)
    ).order_by('-priority', 'due_date')[:10]
    
    results = [{
        'id': task.id,
        'title': task.title,
        'priority': task.priority,
        'status': task.status,
        'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else '',
        'is_completed': task.is_completed,
        'url': reverse('task_detail', args=[task.id])
    } for task in tasks]
    
    return JsonResponse({'results': results})