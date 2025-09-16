#!/usr/bin/env python
"""
Test script to verify queue categorization functionality
"""
import os
import sys
import django

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.CustomerModel import Customer
from calls.models import CallQueue
from django.contrib.auth.models import User

def test_customer_categorization():
    """Test if numbers are correctly categorized as customer or manual"""
    
    # Get or create a test user
    user, created = User.objects.get_or_create(username='test_user', defaults={'email': 'test@example.com'})
    
    # Test phone numbers
    test_numbers = [
        '09123456789',  # This might be an existing customer
        '09999999999',  # This should be manual (unlikely to exist)
    ]
    
    session_id = 'test_session_123'
    
    # Clean up any existing test data
    CallQueue.objects.filter(session_id=session_id).delete()
    
    print("Testing phone number categorization:")
    print("-" * 50)
    
    for number in test_numbers:
        # Clean the number (same logic as in views)
        clean_number = ''.join(c for c in number if c.isdigit())
        if clean_number.startswith('0'):
            clean_number = clean_number[1:]
        if clean_number.startswith('98'):
            clean_number = clean_number[2:]
            
        # Check if customer exists
        customer = Customer.get_customer_by_phone(clean_number)
        
        # Determine source
        source = 'customer' if customer else 'manual'
        
        print(f"Number: {number}")
        print(f"Clean: {clean_number}")
        print(f"Customer found: {customer.name if customer else 'None'}")
        print(f"Source: {source}")
        print()
        
        # Add to queue
        queue_item, created = CallQueue.objects.get_or_create(
            session_id=session_id,
            phone_number=clean_number,
            defaults={
                'customer': customer,
                'source': source,
                'added_by': user
            }
        )
        
        if created:
            print(f"✓ Added {clean_number} to queue as {source}")
        else:
            print(f"! {clean_number} already in queue")
        print()
    
    # Check queue statistics
    queue_items = CallQueue.objects.filter(session_id=session_id)
    total_count = queue_items.count()
    customer_count = queue_items.filter(source='customer').count()
    manual_count = queue_items.filter(source='manual').count()
    
    print("Queue Statistics:")
    print(f"Total: {total_count}")
    print(f"Customers: {customer_count}")
    print(f"Manual: {manual_count}")
    
    # Clean up
    CallQueue.objects.filter(session_id=session_id).delete()
    if created:
        user.delete()

if __name__ == '__main__':
    test_customer_categorization()
