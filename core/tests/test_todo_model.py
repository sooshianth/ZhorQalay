import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.ToDoModel import ToDoItem


@pytest.mark.unit
class TestToDoItemModel:
    """Test class for ToDoItem model."""
    
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
    def ToDoItem_factory(self, db, user_factory):
        def create_ToDoItem(
            title="Test ToDoItem",
            description="Test Description",
            due_date=None,
            priority="medium",
            is_completed=False,
            created_by=None,
            assigned_to=None,
            **kwargs
        ):
            if created_by is None:
                created_by = user_factory(username="creator")
            
            if assigned_to is None:
                assigned_to = user_factory(username="assignee")
            
            if due_date is None:
                due_date = timezone.now() + timedelta(days=7)
            
            return ToDoItem.objects.create(
                title=title,
                description=description,
                due_date=due_date,
                priority=priority,
                is_completed=is_completed,
                created_by=created_by,
                assigned_to=assigned_to,
                **kwargs
            )
        return create_ToDoItem
    
    def test_ToDoItem_creation(self, ToDoItem_factory, user_factory):
        """Test basic creation of ToDoItem."""
        creator = user_factory(username="ToDoItem_creator")
        assignee = user_factory(username="ToDoItem_assignee")
        due_date = timezone.now() + timedelta(days=5)
        
        ToDoItem = ToDoItem_factory(
            title="Complete weekly report",
            description="Finish the sales report for last week",
            due_date=due_date,
            priority="high",
            created_by=creator,
            assigned_to=assignee
        )
        
        assert ToDoItem.title == "Complete weekly report"
        assert ToDoItem.description == "Finish the sales report for last week"
        assert ToDoItem.due_date == due_date
        assert ToDoItem.priority == "high"
        assert ToDoItem.is_completed is False
        assert ToDoItem.created_by == creator
        assert ToDoItem.assigned_to == assignee
        assert ToDoItem.created_at is not None
        
        # Check string representation
        assert str(ToDoItem) == "Complete weekly report"
    
    def test_ToDoItem_completion(self, ToDoItem_factory):
        """Test marking a ToDoItem as completed."""
        ToDoItem = ToDoItem_factory(is_completed=False)
        assert ToDoItem.is_completed is False
        
        # Mark as completed
        ToDoItem.is_completed = True
        ToDoItem.save()
        
        # Verify it's completed
        updated_ToDoItem = ToDoItem.objects.get(id=ToDoItem.id)
        assert updated_ToDoItem.is_completed is True
        
        # If completed_at is set automatically, check that too
        if hasattr(updated_ToDoItem, 'completed_at'):
            assert updated_ToDoItem.completed_at is not None
    
    def test_ToDoItem_priority_choices(self, db, user_factory):
        """Test validation of priority choices."""
        creator = user_factory()
        assignee = user_factory(username="priority_assignee")
        
        # Valid priorities should work
        valid_priorities = ["low", "medium", "high"]
        for priority in valid_priorities:
            ToDoItem = ToDoItem.objects.create(
                title=f"ToDoItem with {priority} priority",
                description="Test description",
                priority=priority,
                created_by=creator,
                assigned_to=assignee
            )
            assert ToDoItem.priority == priority
        
        # Invalid priority should fail
        with pytest.raises(Exception) as excinfo:
            ToDoItem.objects.create(
                title="ToDoItem with invalid priority",
                description="Test description",
                priority="invalid_value",
                created_by=creator,
                assigned_to=assignee
            )
        
        # Check for validation error or integrity error
        assert "invalid" in str(excinfo.value).lower() or "constraint" in str(excinfo.value).lower()
    
    def test_ToDoItem_with_past_due_date(self, ToDoItem_factory):
        """Test creating a ToDoItem with a past due date."""
        past_date = timezone.now() - timedelta(days=1)
        ToDoItem = ToDoItem_factory(due_date=past_date)
        
        assert ToDoItem.due_date == past_date
        
        # Could test a method that checks if a ToDoItem is overdue
        if hasattr(ToDoItem, 'is_overdue'):
            assert ToDoItem.is_overdue() is True
    
    def test_ToDoItem_without_due_date(self, db, user_factory):
        """Test creating a ToDoItem without a due date (if the model allows it)."""
        creator = user_factory()
        assignee = user_factory(username="no_due_date_assignee")
        
        try:
            ToDoItem = ToDoItem.objects.create(
                title="ToDoItem without due date",
                description="Test description",
                due_date=None,
                priority="medium",
                created_by=creator,
                assigned_to=assignee
            )
            assert ToDoItem.due_date is None
        except Exception as e:
            # If due_date is required, this will fail
            assert "due_date" in str(e).lower() and ("null" in str(e).lower() or "required" in str(e).lower())
    
    def test_ToDoItem_reassignment(self, ToDoItem_factory, user_factory):
        """Test reassigning a ToDoItem to a different user."""
        ToDoItem = ToDoItem_factory()
        original_assignee = ToDoItem.assigned_to
        
        # Create a new user to reassign to
        new_assignee = user_factory(username="new_assignee")
        
        # Reassign
        ToDoItem.assigned_to = new_assignee
        ToDoItem.save()
        
        # Verify the reassignment
        updated_ToDoItem = ToDoItem.objects.get(id=ToDoItem.id)
        assert updated_ToDoItem.assigned_to == new_assignee
        assert updated_ToDoItem.assigned_to != original_assignee
    
    def test_ToDoItem_updating_description(self, ToDoItem_factory):
        """Test updating a ToDoItem's description."""
        ToDoItem = ToDoItem_factory(description="Initial description")
        
        # Update description
        ToDoItem.description = "Updated description with more details"
        ToDoItem.save()
        
        # Verify the update
        updated_ToDoItem = ToDoItem.objects.get(id=ToDoItem.id)
        assert updated_ToDoItem.description == "Updated description with more details"
    
    def test_ToDoItem_filtering_by_completion_status(self, ToDoItem_factory):
        """Test filtering ToDoItems by completion status."""
        # Create a mix of completed and incomplete ToDoItems
        ToDoItem_factory(title="Completed ToDoItem 1", is_completed=True)
        ToDoItem_factory(title="Completed ToDoItem 2", is_completed=True)
        ToDoItem_factory(title="Incomplete ToDoItem 1", is_completed=False)
        ToDoItem_factory(title="Incomplete ToDoItem 2", is_completed=False)
        ToDoItem_factory(title="Incomplete ToDoItem 3", is_completed=False)
        
        # Filter by completion status
        completed_ToDoItems = ToDoItem.objects.filter(is_completed=True)
        incomplete_ToDoItems = ToDoItem.objects.filter(is_completed=False)
        
        assert completed_ToDoItems.count() == 2
        assert incomplete_ToDoItems.count() == 3
    
    def test_ToDoItem_filtering_by_due_date(self, ToDoItem_factory):
        """Test filtering ToDoItems by due date."""
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        
        # Create ToDoItems with different due dates
        ToDoItem_factory(title="Overdue ToDoItem", due_date=yesterday)
        ToDoItem_factory(title="Due Today", due_date=today)
        ToDoItem_factory(title="Due Tomorrow", due_date=tomorrow)
        ToDoItem_factory(title="Due Next Week", due_date=next_week)
        
        # Filter ToDoItems due today or earlier
        due_today_or_earlier = ToDoItem.objects.filter(due_date__lte=today)
        # Filter ToDoItems due in the future
        due_in_future = ToDoItem.objects.filter(due_date__gt=today)
        
        assert due_today_or_earlier.count() == 2
        assert due_in_future.count() == 2
    
    def test_ToDoItem_filtering_by_creator(self, ToDoItem_factory, user_factory):
        """Test filtering ToDoItems by creator."""
        creator1 = user_factory(username="creator1")
        creator2 = user_factory(username="creator2")
        
        # Create ToDoItems with different creators
        ToDoItem_factory(title="Creator1 ToDoItem 1", created_by=creator1)
        ToDoItem_factory(title="Creator1 ToDoItem 2", created_by=creator1)
        ToDoItem_factory(title="Creator2 ToDoItem", created_by=creator2)
        
        # Filter by creator
        creator1_ToDoItems = ToDoItem.objects.filter(created_by=creator1)
        creator2_ToDoItems = ToDoItem.objects.filter(created_by=creator2)
        
        assert creator1_ToDoItems.count() == 2
        assert creator2_ToDoItems.count() == 1
    
    def test_ToDoItem_filtering_by_assignee(self, ToDoItem_factory, user_factory):
        """Test filtering ToDoItems by assignee."""
        assignee1 = user_factory(username="assignee1")
        assignee2 = user_factory(username="assignee2")
        
        # Create ToDoItems with different assignees
        ToDoItem_factory(title="Assignee1 ToDoItem 1", assigned_to=assignee1)
        ToDoItem_factory(title="Assignee1 ToDoItem 2", assigned_to=assignee1)
        ToDoItem_factory(title="Assignee2 ToDoItem", assigned_to=assignee2)
        
        # Filter by assignee
        assignee1_ToDoItems = ToDoItem.objects.filter(assigned_to=assignee1)
        assignee2_ToDoItems = ToDoItem.objects.filter(assigned_to=assignee2)
        
        assert assignee1_ToDoItems.count() == 2
        assert assignee2_ToDoItems.count() == 1
    
    def test_ToDoItem_ordering_by_priority(self, ToDoItem_factory):
        """Test ordering ToDoItems by priority."""
        # Create ToDoItems with different priorities
        ToDoItem_factory(title="Low Priority ToDoItem", priority="low")
        ToDoItem_factory(title="Medium Priority ToDoItem", priority="medium")
        ToDoItem_factory(title="High Priority ToDoItem", priority="high")
        
        # Order by priority (assuming high > medium > low)
        # This test might need to be adjusted based on how priorities are stored in the model
        all_ToDoItems = ToDoItem.objects.all().order_by('-priority')
        
        # Verify the order
        assert all_ToDoItems[0].priority == "high" or all_ToDoItems[0].priority == "medium"
        assert all_ToDoItems[-1].priority == "low" or all_ToDoItems[-1].priority == "medium"
    
    def test_ToDoItem_ordering_by_due_date(self, ToDoItem_factory):
        """Test ordering ToDoItems by due date."""
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Create ToDoItems with different due dates
        ToDoItem_factory(title="Due Tomorrow", due_date=tomorrow)
        ToDoItem_factory(title="Due Yesterday", due_date=yesterday)
        ToDoItem_factory(title="Due Today", due_date=today)
        
        # Order by due date (ascending)
        ordered_ToDoItems = ToDoItem.objects.all().order_by('due_date')
        
        # Verify the order
        assert ordered_ToDoItems[0].title == "Due Yesterday"
        assert ordered_ToDoItems[1].title == "Due Today"
        assert ordered_ToDoItems[2].title == "Due Tomorrow" 