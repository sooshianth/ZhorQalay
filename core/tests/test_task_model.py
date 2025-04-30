import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.TaskModel import Task


@pytest.mark.unit
class TestTaskModel:
    """Test class for Task model."""
    
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
            return User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                **kwargs
            )
        return create_user
    
    @pytest.fixture
    def task_factory(self, db, user_factory):
        def create_task(
            title="Test Task",
            description="Test Description",
            due_date=None,
            status="pending",
            priority="medium",
            created_by=None,
            assigned_to=None,
            **kwargs
        ):
            if created_by is None:
                created_by = user_factory(username="task_creator")
            
            if assigned_to is None:
                assigned_to = user_factory(username="task_assignee")
            
            if due_date is None:
                due_date = timezone.now() + timedelta(days=7)
            
            return Task.objects.create(
                title=title,
                description=description,
                due_date=due_date,
                status=status,
                priority=priority,
                created_by=created_by,
                assigned_to=assigned_to,
                **kwargs
            )
        return create_task
    
    def test_task_creation(self, task_factory, user_factory):
        """Test basic creation of Task."""
        creator = user_factory(username="creator")
        assignee = user_factory(username="assignee")
        due_date = timezone.now() + timedelta(days=5)
        
        task = task_factory(
            title="Prepare quarterly report",
            description="Compile data and prepare quarterly financial report",
            due_date=due_date,
            status="pending",
            priority="high",
            created_by=creator,
            assigned_to=assignee
        )
        
        assert task.title == "Prepare quarterly report"
        assert task.description == "Compile data and prepare quarterly financial report"
        assert task.due_date == due_date
        assert task.status == "pending"
        assert task.priority == "high"
        assert task.created_by == creator
        assert task.assigned_to == assignee
        assert task.created_at is not None
        
        # Check string representation
        assert str(task) == "Prepare quarterly report"
    
    def test_task_status_update(self, task_factory):
        """Test updating task status."""
        task = task_factory(status="pending")
        assert task.status == "pending"
        
        # Update status
        task.status = "in_progress"
        task.save()
        
        # Verify status update
        updated_task = Task.objects.get(id=task.id)
        assert updated_task.status == "in_progress"
        
        # Update to completed
        task.status = "completed"
        task.save()
        
        # Verify completed status
        completed_task = Task.objects.get(id=task.id)
        assert completed_task.status == "completed"
        
        # If completion_date is automatically set, verify it
        if hasattr(completed_task, 'completion_date'):
            assert completed_task.completion_date is not None
    
    def test_task_priority_choices(self, db, user_factory):
        """Test validation of priority choices."""
        creator = user_factory()
        assignee = user_factory(username="priority_test_assignee")
        
        # Valid priorities should work
        valid_priorities = ["low", "medium", "high"]
        for priority in valid_priorities:
            task = Task.objects.create(
                title=f"Task with {priority} priority",
                description="Test priority validation",
                priority=priority,
                created_by=creator,
                assigned_to=assignee
            )
            assert task.priority == priority
        
        # Invalid priority should fail
        with pytest.raises(Exception) as excinfo:
            Task.objects.create(
                title="Task with invalid priority",
                description="Test priority validation",
                priority="invalid_value",
                created_by=creator,
                assigned_to=assignee
            )
        
        # Check for validation error or integrity error
        assert "invalid" in str(excinfo.value).lower() or "constraint" in str(excinfo.value).lower()
    
    def test_task_status_choices(self, db, user_factory):
        """Test validation of status choices."""
        creator = user_factory()
        assignee = user_factory(username="status_test_assignee")
        
        # Valid statuses should work
        valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
        for status in valid_statuses:
            task = Task.objects.create(
                title=f"Task with {status} status",
                description="Test status validation",
                status=status,
                created_by=creator,
                assigned_to=assignee
            )
            assert task.status == status
        
        # Invalid status should fail
        with pytest.raises(Exception) as excinfo:
            Task.objects.create(
                title="Task with invalid status",
                description="Test status validation",
                status="invalid_value",
                created_by=creator,
                assigned_to=assignee
            )
        
        # Check for validation error or integrity error
        assert "invalid" in str(excinfo.value).lower() or "constraint" in str(excinfo.value).lower()
    
    def test_task_reassignment(self, task_factory, user_factory):
        """Test reassigning a task to a different user."""
        task = task_factory()
        original_assignee = task.assigned_to
        
        # Create a new user to reassign to
        new_assignee = user_factory(username="new_task_assignee")
        
        # Reassign
        task.assigned_to = new_assignee
        task.save()
        
        # Verify the reassignment
        updated_task = Task.objects.get(id=task.id)
        assert updated_task.assigned_to == new_assignee
        assert updated_task.assigned_to != original_assignee
    
    def test_task_with_past_due_date(self, task_factory):
        """Test creating a task with a past due date."""
        past_date = timezone.now() - timedelta(days=1)
        task = task_factory(due_date=past_date)
        
        assert task.due_date == past_date
        
        # Could test a method that checks if a task is overdue
        if hasattr(task, 'is_overdue'):
            assert task.is_overdue() is True
    
    def test_task_without_due_date(self, db, user_factory):
        """Test creating a task without a due date (if the model allows it)."""
        creator = user_factory()
        assignee = user_factory(username="no_due_date_assignee")
        
        try:
            task = Task.objects.create(
                title="Task without due date",
                description="Test description",
                due_date=None,
                status="pending",
                priority="medium",
                created_by=creator,
                assigned_to=assignee
            )
            assert task.due_date is None
        except Exception as e:
            # If due_date is required, this will fail
            assert "due_date" in str(e).lower() and ("null" in str(e).lower() or "required" in str(e).lower())
    
    def test_task_updating_description(self, task_factory):
        """Test updating a task's description."""
        task = task_factory(description="Initial description")
        
        # Update description
        task.description = "Updated task description with more details"
        task.save()
        
        # Verify the update
        updated_task = Task.objects.get(id=task.id)
        assert updated_task.description == "Updated task description with more details"
    
    def test_task_filtering_by_status(self, task_factory):
        """Test filtering tasks by status."""
        # Create tasks with different statuses
        task_factory(title="Pending Task 1", status="pending")
        task_factory(title="Pending Task 2", status="pending")
        task_factory(title="In Progress Task", status="in_progress")
        task_factory(title="Completed Task 1", status="completed")
        task_factory(title="Completed Task 2", status="completed")
        task_factory(title="Cancelled Task", status="cancelled")
        
        # Filter by status
        pending_tasks = Task.objects.filter(status="pending")
        in_progress_tasks = Task.objects.filter(status="in_progress")
        completed_tasks = Task.objects.filter(status="completed")
        cancelled_tasks = Task.objects.filter(status="cancelled")
        
        assert pending_tasks.count() == 2
        assert in_progress_tasks.count() == 1
        assert completed_tasks.count() == 2
        assert cancelled_tasks.count() == 1
    
    def test_task_filtering_by_priority(self, task_factory):
        """Test filtering tasks by priority."""
        # Create tasks with different priorities
        task_factory(title="Low Priority Task 1", priority="low")
        task_factory(title="Low Priority Task 2", priority="low")
        task_factory(title="Medium Priority Task", priority="medium")
        task_factory(title="High Priority Task 1", priority="high")
        task_factory(title="High Priority Task 2", priority="high")
        
        # Filter by priority
        low_priority_tasks = Task.objects.filter(priority="low")
        medium_priority_tasks = Task.objects.filter(priority="medium")
        high_priority_tasks = Task.objects.filter(priority="high")
        
        assert low_priority_tasks.count() == 2
        assert medium_priority_tasks.count() == 1
        assert high_priority_tasks.count() == 2
    
    def test_task_filtering_by_due_date(self, task_factory):
        """Test filtering tasks by due date."""
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        
        # Create tasks with different due dates
        task_factory(title="Overdue Task", due_date=yesterday)
        task_factory(title="Due Today Task", due_date=today)
        task_factory(title="Due Tomorrow Task", due_date=tomorrow)
        task_factory(title="Due Next Week Task", due_date=next_week)
        
        # Filter tasks due today or earlier
        due_today_or_earlier = Task.objects.filter(due_date__lte=today)
        # Filter tasks due in the future
        due_in_future = Task.objects.filter(due_date__gt=today)
        
        assert due_today_or_earlier.count() == 2
        assert due_in_future.count() == 2
    
    def test_task_filtering_by_creator(self, task_factory, user_factory):
        """Test filtering tasks by creator."""
        creator1 = user_factory(username="task_creator1")
        creator2 = user_factory(username="task_creator2")
        
        # Create tasks with different creators
        task_factory(title="Creator1 Task 1", created_by=creator1)
        task_factory(title="Creator1 Task 2", created_by=creator1)
        task_factory(title="Creator2 Task", created_by=creator2)
        
        # Filter by creator
        creator1_tasks = Task.objects.filter(created_by=creator1)
        creator2_tasks = Task.objects.filter(created_by=creator2)
        
        assert creator1_tasks.count() == 2
        assert creator2_tasks.count() == 1
    
    def test_task_filtering_by_assignee(self, task_factory, user_factory):
        """Test filtering tasks by assignee."""
        assignee1 = user_factory(username="task_assignee1")
        assignee2 = user_factory(username="task_assignee2")
        
        # Create tasks with different assignees
        task_factory(title="Assignee1 Task 1", assigned_to=assignee1)
        task_factory(title="Assignee1 Task 2", assigned_to=assignee1)
        task_factory(title="Assignee2 Task", assigned_to=assignee2)
        
        # Filter by assignee
        assignee1_tasks = Task.objects.filter(assigned_to=assignee1)
        assignee2_tasks = Task.objects.filter(assigned_to=assignee2)
        
        assert assignee1_tasks.count() == 2
        assert assignee2_tasks.count() == 1
    
    def test_task_ordering_by_priority(self, task_factory):
        """Test ordering tasks by priority."""
        # Create tasks with different priorities
        task_factory(title="Low Priority Task", priority="low")
        task_factory(title="Medium Priority Task", priority="medium")
        task_factory(title="High Priority Task", priority="high")
        
        # Order by priority (assuming high > medium > low)
        # This test might need to be adjusted based on how priorities are stored in the model
        all_tasks = Task.objects.all().order_by('-priority')
        
        # Verify the order
        assert all_tasks[0].priority == "high" or all_tasks[0].priority == "medium"
        assert all_tasks[-1].priority == "low" or all_tasks[-1].priority == "medium"
    
    def test_task_ordering_by_due_date(self, task_factory):
        """Test ordering tasks by due date."""
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Create tasks with different due dates
        task_factory(title="Due Tomorrow Task", due_date=tomorrow)
        task_factory(title="Due Yesterday Task", due_date=yesterday)
        task_factory(title="Due Today Task", due_date=today)
        
        # Order by due date (ascending)
        ordered_tasks = Task.objects.all().order_by('due_date')
        
        # Verify the order
        assert ordered_tasks[0].title == "Due Yesterday Task"
        assert ordered_tasks[1].title == "Due Today Task"
        assert ordered_tasks[2].title == "Due Tomorrow Task"
    
    def test_cancelling_task(self, task_factory):
        """Test cancelling a task."""
        task = task_factory(status="pending")
        
        # Cancel the task
        task.status = "cancelled"
        task.save()
        
        # Verify it's cancelled
        cancelled_task = Task.objects.get(id=task.id)
        assert cancelled_task.status == "cancelled"
    
    def test_completing_task(self, task_factory):
        """Test completing a task."""
        task = task_factory(status="in_progress")
        
        # Complete the task
        task.status = "completed"
        task.save()
        
        # Verify it's completed
        completed_task = Task.objects.get(id=task.id)
        assert completed_task.status == "completed"
        
        # If a completion timestamp is set, verify it
        if hasattr(completed_task, 'completed_at'):
            assert completed_task.completed_at is not None 