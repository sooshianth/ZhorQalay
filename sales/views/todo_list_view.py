from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from core._models import ToDoItem

@login_required
def task_dashboard_view(request):
    tasks = ToDoItem.objects.filter(user=request.user, is_completed=False).order_by('due_date')[:5]
    context = {
        'tasks': tasks,
    }
    return render(request, 'task_dashboard.html', context)

@login_required
def create_task_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        due_date = request.POST.get('due_date')
        priority = request.POST.get('priority')

        if title and due_date:
            ToDoItem.objects.create(
                user=request.user,
                title=title,
                description=description,
                due_date=due_date,
                priority=priority,
                is_completed=False
            )
            return HttpResponseRedirect(reverse('task_dashboard'))

    return render(request, 'create_task.html')

@login_required
def completed_tasks_view(request):
    tasks = ToDoItem.objects.filter(user=request.user, is_completed=True).order_by('-created_at')
    return render(request, 'completed_tasks.html', {'tasks': tasks})

@login_required
def change_task_status(request, task_id):
    if request.method == 'POST':
        task = ToDoItem.objects.get(id=task_id, user=request.user)
        task.is_completed = True
        task.save()
        return HttpResponseRedirect(reverse('task_dashboard'))
    return HttpResponseRedirect(reverse('task_dashboard'))