import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from chat.MessageModel import Message
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.test import Client, RequestFactory
from django.db import models
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.unit
class TestChatModels:
    """Test class for Chat application models."""
    
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
    def message_factory(self, db, user_factory):
        def create_message(
            sender=None,
            receiver=None,
            message="Test message",
            is_global=False,
            is_read=False,
            is_deleted=False,
            is_edited=False,
            is_pinned=False,
            file_url=None,
            file_type=None,
            reply_to=None,
            **kwargs
        ):
            if sender is None:
                sender = user_factory(username="sender")
                
            if receiver is None:
                receiver = user_factory(username="receiver")
                
            return Message.objects.create(
                sender=sender,
                receiver=receiver,
                message=message,
                is_global=is_global,
                is_read=is_read,
                is_deleted=is_deleted,
                is_edited=is_edited,
                is_pinned=is_pinned,
                file_url=file_url,
                file_type=file_type,
                reply_to=reply_to,
                **kwargs
            )
        return create_message
    
    def test_message_creation(self, message_factory, user_factory):
        """Test basic Message model creation."""
        sender = user_factory(username="test_sender")
        receiver = user_factory(username="test_receiver")
        
        message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Hello, this is a test message",
            is_global=False
        )
        
        assert message.sender == sender
        assert message.receiver == receiver
        assert message.message == "Hello, this is a test message"
        assert message.is_global is False
        assert message.is_read is False
        assert message.is_deleted is False
        assert message.is_edited is False
        assert message.is_pinned is False
        assert message.file_url is None
        assert message.file_type is None
        assert message.reply_to is None
        assert message.timestamp is not None
    
    def test_global_message(self, message_factory, user_factory):
        """Test creating a global message."""
        sender = user_factory(username="admin")
        receiver = user_factory(username="user1")
        
        global_message = message_factory(
            sender=sender,
            receiver=receiver,
            message="System announcement: Maintenance tonight",
            is_global=True
        )
        
        assert global_message.is_global is True
        assert global_message.sender == sender
        assert global_message.receiver == receiver
    
    def test_file_attachment(self, message_factory, user_factory):
        """Test creating a message with file attachment."""
        sender = user_factory(username="sender_with_file")
        receiver = user_factory(username="receiver_of_file")
        
        file_message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Please check the attached document",
            file_url="https://example.com/files/document.pdf",
            file_type="application/pdf"
        )
        
        assert file_message.file_url == "https://example.com/files/document.pdf"
        assert file_message.file_type == "application/pdf"
    
    def test_reply_to_message(self, message_factory, user_factory):
        """Test replying to a message."""
        sender = user_factory(username="original_sender")
        receiver = user_factory(username="original_receiver")
        
        # Create original message
        original_message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Original message"
        )
        
        # Create reply
        reply_message = message_factory(
            sender=receiver,  # The receiver becomes the sender
            receiver=sender,  # The sender becomes the receiver
            message="Reply to original",
            reply_to=original_message
        )
        
        assert reply_message.reply_to == original_message
        assert reply_message.sender == receiver
        assert reply_message.receiver == sender
    
    def test_message_ordering(self, message_factory, user_factory):
        """Test that messages are ordered by timestamp."""
        sender = user_factory(username="chat_user1")
        receiver = user_factory(username="chat_user2")
        
        # Create messages in reverse chronological order
        message3 = message_factory(sender=sender, receiver=receiver, message="Message 3")
        message2 = message_factory(sender=sender, receiver=receiver, message="Message 2")
        message1 = message_factory(sender=sender, receiver=receiver, message="Message 1")
        
        # Get all messages ordered by timestamp
        messages = Message.objects.filter(
            sender=sender, 
            receiver=receiver
        ).order_by('timestamp')
        
        # Check that they're in the correct order
        messages_list = list(messages)
        assert messages_list[0].message == "Message 1"
        assert messages_list[1].message == "Message 2"
        assert messages_list[2].message == "Message 3"
    
    def test_message_mark_as_read(self, message_factory, user_factory):
        """Test marking a message as read."""
        sender = user_factory(username="notification_sender")
        receiver = user_factory(username="notification_receiver")
        
        message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Please read this",
            is_read=False
        )
        
        # Initially unread
        assert message.is_read is False
        
        # Mark as read
        message.is_read = True
        message.save()
        
        # Confirm it's read
        updated_message = Message.objects.get(id=message.id)
        assert updated_message.is_read is True
    
    def test_message_deletion(self, message_factory, user_factory):
        """Test soft deletion of messages."""
        sender = user_factory(username="deletion_sender")
        receiver = user_factory(username="deletion_receiver")
        
        message = message_factory(
            sender=sender,
            receiver=receiver,
            message="This will be deleted",
            is_deleted=False
        )
        
        # Initially not deleted
        assert message.is_deleted is False
        
        # Soft delete
        message.is_deleted = True
        message.save()
        
        # Confirm it's marked as deleted
        deleted_message = Message.objects.get(id=message.id)
        assert deleted_message.is_deleted is True
    
    def test_message_editing(self, message_factory, user_factory):
        """Test editing messages."""
        sender = user_factory(username="editor")
        receiver = user_factory(username="recipient")
        
        message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Original content",
            is_edited=False
        )
        
        # Edit the message
        message.message = "Edited content"
        message.is_edited = True
        message.save()
        
        # Check the changes
        edited_message = Message.objects.get(id=message.id)
        assert edited_message.message == "Edited content"
        assert edited_message.is_edited is True
    
    def test_message_pinning(self, message_factory, user_factory):
        """Test pinning messages."""
        sender = user_factory(username="pin_sender")
        receiver = user_factory(username="pin_receiver")
        
        message = message_factory(
            sender=sender,
            receiver=receiver,
            message="Important announcement",
            is_pinned=False
        )
        
        # Pin the message
        message.is_pinned = True
        message.save()
        
        # Check it's pinned
        pinned_message = Message.objects.get(id=message.id)
        assert pinned_message.is_pinned is True
        
        # Get all pinned messages
        pinned_messages = Message.objects.filter(is_pinned=True)
        assert message in pinned_messages
    
    def test_user_conversation_query(self, message_factory, user_factory):
        """Test querying conversations between users."""
        user1 = user_factory(username="conversation_user1")
        user2 = user_factory(username="conversation_user2")
        
        # Create messages back and forth
        message_factory(sender=user1, receiver=user2, message="Hi there")
        message_factory(sender=user2, receiver=user1, message="Hello back")
        message_factory(sender=user1, receiver=user2, message="How are you?")
        
        # Query the conversation (both directions)
        conversation = Message.objects.filter(
            (models.Q(sender=user1) & models.Q(receiver=user2)) |
            (models.Q(sender=user2) & models.Q(receiver=user1))
        ).order_by('timestamp')
        
        assert conversation.count() == 3
        assert conversation[0].message == "Hi there"
        assert conversation[1].message == "Hello back"
        assert conversation[2].message == "How are you?"
    
    def test_unread_messages_count(self, message_factory, user_factory):
        """Test counting unread messages for a user."""
        sender = user_factory(username="notification_sender")
        receiver = user_factory(username="notification_receiver")
        
        # Create several messages, some read, some unread
        message_factory(sender=sender, receiver=receiver, message="Read message 1", is_read=True)
        message_factory(sender=sender, receiver=receiver, message="Unread message 1", is_read=False)
        message_factory(sender=sender, receiver=receiver, message="Read message 2", is_read=True)
        message_factory(sender=sender, receiver=receiver, message="Unread message 2", is_read=False)
        message_factory(sender=sender, receiver=receiver, message="Unread message 3", is_read=False)
        
        # Count unread messages
        unread_count = Message.objects.filter(receiver=receiver, is_read=False).count()
        
        assert unread_count == 3


@pytest.mark.integration
class TestChatViews:
    """Test class for Chat application views."""
    
    @pytest.fixture
    def client(self):
        return Client()
    
    @pytest.fixture
    def authenticated_client(self, client, user_factory):
        user = user_factory(username="auth_user")
        client.force_login(user)
        return client, user
    
    @pytest.fixture
    def factory(self):
        return RequestFactory()
    
    def test_send_message_view(self, authenticated_client, user_factory):
        """Test the send message view."""
        client, sender = authenticated_client
        receiver = user_factory(username="message_receiver")
        
        url = reverse('send_message')
        data = {
            'receiver_id': receiver.id,
            'message': 'Hello from test',
            'is_global': False
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check message was created in database
        messages = Message.objects.filter(sender=sender, receiver=receiver)
        assert messages.count() == 1
        assert messages.first().message == 'Hello from test'
    
    def test_get_messages_view(self, authenticated_client, user_factory, message_factory):
        """Test the get messages view."""
        client, user1 = authenticated_client
        user2 = user_factory(username="conversation_partner")
        
        # Create some messages between users
        message_factory(sender=user1, receiver=user2, message="Message 1")
        message_factory(sender=user2, receiver=user1, message="Reply 1")
        message_factory(sender=user1, receiver=user2, message="Message 2")
        
        url = reverse('get_messages')
        data = {'user_id': user2.id}
        
        response = client.get(url, data)
        
        assert response.status_code == 200
        
        # Parse JSON response
        messages = response.json()
        
        assert len(messages) == 3
        assert messages[0]['message'] == "Message 1"
        assert messages[1]['message'] == "Reply 1"
        assert messages[2]['message'] == "Message 2"
    
    def test_get_conversations_view(self, authenticated_client, user_factory, message_factory):
        """Test the get conversations view."""
        client, current_user = authenticated_client
        
        # Create multiple users who have conversations with current_user
        user1 = user_factory(username="chat_partner1")
        user2 = user_factory(username="chat_partner2")
        user3 = user_factory(username="chat_partner3")
        
        # Create messages with different users
        message_factory(sender=current_user, receiver=user1, message="Hi user1")
        message_factory(sender=user1, receiver=current_user, message="Hi back")
        
        message_factory(sender=current_user, receiver=user2, message="Hi user2")
        
        message_factory(sender=user3, receiver=current_user, message="Hello from user3")
        
        url = reverse('get_conversations')
        
        response = client.get(url)
        
        assert response.status_code == 200
        
        # Parse JSON response
        conversations = response.json()
        
        # We expect 3 conversations (with user1, user2, and user3)
        assert len(conversations) == 3
        
        # Check conversation partners are included
        conversation_partners = [conv['user']['username'] for conv in conversations]
        assert 'chat_partner1' in conversation_partners
        assert 'chat_partner2' in conversation_partners
        assert 'chat_partner3' in conversation_partners
    
    def test_mark_as_read_view(self, authenticated_client, user_factory, message_factory):
        """Test marking messages as read."""
        client, receiver = authenticated_client
        sender = user_factory(username="message_sender")
        
        # Create an unread message
        message = message_factory(
            sender=sender, 
            receiver=receiver, 
            message="Please read this",
            is_read=False
        )
        
        url = reverse('mark_message_read')
        data = {'message_id': message.id}
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check message was marked as read
        updated_message = Message.objects.get(id=message.id)
        assert updated_message.is_read is True
    
    def test_delete_message_view(self, authenticated_client, user_factory, message_factory):
        """Test soft deleting a message."""
        client, sender = authenticated_client
        receiver = user_factory(username="message_receiver")
        
        # Create a message
        message = message_factory(
            sender=sender, 
            receiver=receiver, 
            message="This will be deleted",
            is_deleted=False
        )
        
        url = reverse('delete_message')
        data = {'message_id': message.id}
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check message was marked as deleted
        updated_message = Message.objects.get(id=message.id)
        assert updated_message.is_deleted is True
    
    def test_edit_message_view(self, authenticated_client, user_factory, message_factory):
        """Test editing a message."""
        client, sender = authenticated_client
        receiver = user_factory(username="edit_receiver")
        
        # Create a message
        message = message_factory(
            sender=sender, 
            receiver=receiver, 
            message="Original content",
            is_edited=False
        )
        
        url = reverse('edit_message')
        data = {
            'message_id': message.id,
            'new_content': 'Edited content'
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check message was edited
        updated_message = Message.objects.get(id=message.id)
        assert updated_message.message == 'Edited content'
        assert updated_message.is_edited is True
    
    def test_pin_message_view(self, authenticated_client, user_factory, message_factory):
        """Test pinning a message."""
        client, user = authenticated_client
        receiver = user_factory(username="pin_receiver")
        
        # Create a message
        message = message_factory(
            sender=user, 
            receiver=receiver, 
            message="Important message",
            is_pinned=False
        )
        
        url = reverse('pin_message')
        data = {'message_id': message.id}
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check message was pinned
        updated_message = Message.objects.get(id=message.id)
        assert updated_message.is_pinned is True
    
    def test_upload_file_view(self, authenticated_client, user_factory):
        """Test uploading a file with a message."""
        client, sender = authenticated_client
        receiver = user_factory(username="file_receiver")
        
        url = reverse('upload_file')
        
        # Mock file upload
        with patch('chat.views.handle_uploaded_file') as mock_handler:
            mock_handler.return_value = 'https://example.com/uploads/test.pdf'
            
            # Create test file data
            data = {
                'receiver_id': receiver.id,
                'message': 'Here is the file',
                'file': SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
            }
            
            response = client.post(url, data)
            
            assert response.status_code == 200
            
            # Check message was created with file
            messages = Message.objects.filter(sender=sender, receiver=receiver)
            assert messages.count() == 1
            assert messages.first().file_url == 'https://example.com/uploads/test.pdf'
            assert messages.first().file_type == 'application/pdf'
    
    def test_search_messages_view(self, authenticated_client, user_factory, message_factory):
        """Test searching messages."""
        client, user = authenticated_client
        other_user = user_factory(username="search_partner")
        
        # Create messages with searchable content
        message_factory(sender=user, receiver=other_user, message="This contains keyword apple")
        message_factory(sender=other_user, receiver=user, message="Another message about apple pie")
        message_factory(sender=user, receiver=other_user, message="This is about oranges")
        
        url = reverse('search_messages')
        data = {'query': 'apple'}
        
        response = client.get(url, data)
        
        assert response.status_code == 200
        
        # Parse JSON response
        results = response.json()
        
        # Should find the two messages containing "apple"
        assert len(results) == 2
        assert "apple" in results[0]['message'].lower()
        assert "apple" in results[1]['message'].lower()
    
    def test_get_unread_count_view(self, authenticated_client, user_factory, message_factory):
        """Test getting unread message count."""
        client, receiver = authenticated_client
        sender = user_factory(username="unread_sender")
        
        # Create some unread messages
        message_factory(sender=sender, receiver=receiver, message="Unread 1", is_read=False)
        message_factory(sender=sender, receiver=receiver, message="Unread 2", is_read=False)
        message_factory(sender=sender, receiver=receiver, message="Read 1", is_read=True)
        
        url = reverse('get_unread_count')
        
        response = client.get(url)
        
        assert response.status_code == 200
        
        # Parse JSON response
        data = response.json()
        
        assert data['unread_count'] == 2
    
    def test_user_search_view(self, authenticated_client, user_factory):
        """Test searching for users to start a conversation."""
        client, current_user = authenticated_client
        
        # Create some users
        user_factory(username="john_doe", first_name="John", last_name="Doe")
        user_factory(username="jane_smith", first_name="Jane", last_name="Smith")
        user_factory(username="john_smith", first_name="John", last_name="Smith")
        
        url = reverse('search_users')
        data = {'query': 'john'}
        
        response = client.get(url, data)
        
        assert response.status_code == 200
        
        # Parse JSON response
        results = response.json()
        
        # Should find the two users with "john" in their name
        assert len(results) == 2
        usernames = [user['username'] for user in results]
        assert 'john_doe' in usernames
        assert 'john_smith' in usernames
    
    def test_global_announcement_view(self, authenticated_client, user_factory):
        """Test creating a global announcement (admin only)."""
        client, admin_user = authenticated_client
        
        # Make the user an admin
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        
        # Create some regular users
        user1 = user_factory(username="user1")
        user2 = user_factory(username="user2")
        user3 = user_factory(username="user3")
        
        url = reverse('send_global_announcement')
        data = {'message': 'System will be down for maintenance tonight'}
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        
        # Check that a message was created for each user
        for user in [user1, user2, user3]:
            messages = Message.objects.filter(
                sender=admin_user,
                receiver=user,
                is_global=True,
                message='System will be down for maintenance tonight'
            )
            assert messages.count() == 1 