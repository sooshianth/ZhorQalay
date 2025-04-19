from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from .NotificationModel import Notification
from django.core.cache import cache
from datetime import timedelta
import random
import string
import logging

logger = logging.getLogger(__name__)

class SalesAgent(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.DO_NOTHING, related_name='sales_agent')
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    factor_code = models.CharField(max_length=2, unique=True, null=True, blank=True)
    target_monthly_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, 
                                              verbose_name='هدف فروش ماهانه')
    
    class Meta:
        verbose_name = 'کارشناس فروش'
        verbose_name_plural = 'کارشناسان فروش'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['factor_code']),
        ]

    def get_all_customers(self):
        return self.customers.all()
    
    def get_sales_in_period(self, start_date=None, end_date=None, paid_only=True, archived=False):
        if start_date is None:
            start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = timezone.now()
            
        filters = Q(created_at__gte=start_date, created_at__lte=end_date)
        if paid_only:
            filters &= Q(is_paid=True)
        filters &= Q(is_archived=archived)
        
        sales = []
        for customer in self.get_all_customers():
            sales.extend(customer.purchases_made.filter(filters))
            
        return sales

    def get_this_month_sales(self):
        """Get all paid, non-archived sales for the current month."""
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.get_sales_in_period(start_date=start_of_month, end_date=now)

    # Add to SalesAgentModel.py at the top

    def get_this_month_sales_stats(self):
        """Get comprehensive statistics for this month's sales with caching."""
        cache_key = f'sales_agent_{self.id}_monthly_stats_{timezone.now().strftime("%Y%m")}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
            
        # Original calculation code...
        sales = self.get_this_month_sales()
        amount = sum(purchase.amount_paid for purchase in sales)
        weight = sum(purchase.weight for purchase in sales)
        count = len(sales)
        average = amount / count if count > 0 else 0
        
        target_achievement = (amount / self.target_monthly_sales * 100) if self.target_monthly_sales > 0 else 0
        
        result = {
            'amount': amount,
            'weight': weight,
            'count': count,
            'average': average,
            'target_achievement': target_achievement,
        }
        
        # Cache for 1 hour
        cache.set(cache_key, result, 3600)
        
        return result


    def get_potentional_sales(self):
        """Get all non-archived, unpaid sales (potential future revenue)."""
        return self.get_sales_in_period(paid_only=False, archived=False)
    
    def get_all_unpaid_sales(self):
        """Get all unpaid sales regardless of archive status."""
        unpaid_sales = []
        for customer in self.get_all_customers():
            unpaid_sales.extend(customer.purchases_made.filter(is_paid=False))
        return unpaid_sales

    def get_all_active_sales(self):
        """Get all non-archived, paid sales."""
        return self.get_sales_in_period(start_date=None, end_date=None, paid_only=True, archived=False)

    def get_all_archived_sales(self):
        """Get all archived, paid sales."""
        return self.get_sales_in_period(start_date=None, end_date=None, paid_only=True, archived=True)

    def get_tasks_by_status(self, status=None, due_date=None):
        tasks = []
        for customer in self.get_all_customers():
            query = Q()
            if status is not None:
                query &= Q(status=status)
            if due_date is not None:
                query &= Q(due_date__date=due_date)
                
            tasks.extend(customer.tasks.filter(query))
            
        return sorted(tasks, key=lambda task: task.due_date)

    def get_this_month_sales_weight(self):
        return sum([purchase.weight for purchase in self.get_this_month_sales()])

    def get_today_tasks(self):
        """Get all tasks due today."""
        return self.get_tasks_by_status(due_date=timezone.now().date())

    def get_all_undone_tasks(self):
        """Get all incomplete tasks sorted by due date."""
        return self.get_tasks_by_status(status=False)

    def get_all_tasks(self):
        """Get all tasks sorted by due date."""
        return self.get_tasks_by_status()

    def get_overdue_tasks(self):
        """Get all incomplete tasks that are past their due date."""
        now = timezone.now()
        tasks = []
        for customer in self.get_all_customers():
            tasks.extend(customer.tasks.filter(status=False, due_date__lt=now))
        return sorted(tasks, key=lambda task: task.due_date)

    def get_weekly_sales_trend(self, weeks=8):
        """
        Get weekly sales trend for the specified number of past weeks.
        
        Args:
            weeks: Number of weeks to include in the trend
            
        Returns:
            Dictionary mapping week numbers to total weight sold
        """
        from collections import defaultdict
        trend = defaultdict(int)
        
        # Calculate start date (beginning of 'weeks' weeks ago)
        now = timezone.now()
        start_date = now - timedelta(days=now.weekday() + 7 * (weeks - 1))
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get all relevant purchases
        purchases = self.get_sales_in_period(start_date=start_date, end_date=now, paid_only=True)
        
        # Group by week
        for purchase in purchases:
            week = purchase.created_at.isocalendar()[1]  # Week number
            trend[week] += purchase.weight
            
        return dict(trend)

    def get_sales_by_product(self, start_date=None, end_date=None):
        """
        Get sales aggregated by product type.
        
        Returns:
            Dictionary mapping product types to total weight sold
        """
        from collections import defaultdict
        
        product_sales = defaultdict(int)
        sales = self.get_sales_in_period(start_date, end_date)
        
        for purchase in sales:
            if hasattr(purchase, 'product_type') and purchase.product_type:
                product_sales[purchase.product_type] += purchase.weight
                
        return dict(product_sales)

    def check_task_deadlines(self):
        """
        Check for upcoming task deadlines and create notifications.
        Returns the number of new notifications created.
        """
        notification_count = 0
        now = timezone.now()
        
        for task in self.get_all_undone_tasks():
            # Check if task is due within 24 hours
            if task.due_date - now < timedelta(hours=24):
                # Check if notification already exists
                notification_exists = Notification.objects.filter(
                    user=self.user,
                    message__contains=task.description,
                    created_at__gte=now - timedelta(hours=24)
                ).exists()
                
                if not notification_exists:
                    Notification.objects.create(
                        user=self.user,
                        message=f"تسک '{task.description}' تا کمتر از ۲۴ ساعت دیگر به پایان می‌رسد!",
                        is_read=False
                    )
                    notification_count += 1
                    
        return notification_count
    
    # Add to SalesAgentModel.py

    def get_performance_metrics(self, period_days=30):
        """
        Calculate comprehensive performance metrics for this sales agent.
        
        Args:
            period_days: Number of days to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        now = timezone.now()
        start_date = now - timedelta(days=period_days)
        
        # Get sales in the period
        sales = self.get_sales_in_period(start_date=start_date, end_date=now)
        
        # Calculate metrics
        total_sales = len(sales)
        total_weight = sum(s.weight for s in sales)
        total_amount = sum(s.amount_paid for s in sales)
        
        # Get customer metrics
        customers = self.get_all_customers()
        active_customers = set()
        for sale in sales:
            active_customers.add(sale.customer.id)
        
        # Calculate daily averages
        daily_avg_sales = total_sales / period_days if period_days > 0 else 0
        daily_avg_weight = total_weight / period_days if period_days > 0 else 0
        daily_avg_amount = total_amount / period_days if period_days > 0 else 0
        
        # Calculate task completion rate
        completed_tasks = len([t for t in self.get_tasks_by_status(status=True) if t.completed_at and t.completed_at >= start_date])
        total_tasks = len([t for t in self.get_all_tasks() if t.create_time >= start_date])
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate average response time to tasks
        response_times = []
        for task in self.get_tasks_by_status(status=True):
            if task.completed_at and task.create_time and task.completed_at >= start_date:
                response_time = (task.completed_at - task.create_time).total_seconds() / 3600  # hours
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'period_days': period_days,
            'total_sales': total_sales,
            'total_weight': total_weight,
            'total_amount': total_amount,
            'total_customers': len(customers),
            'active_customers': len(active_customers),
            'customer_activation_rate': len(active_customers) / len(customers) * 100 if customers else 0,
            'daily_avg_sales': daily_avg_sales,
            'daily_avg_weight': daily_avg_weight,
            'daily_avg_amount': daily_avg_amount,
            'task_completion_rate': task_completion_rate,
            'avg_response_time_hours': avg_response_time,
        }


    def forecast_sales(self, days_ahead=30):
        """
        Forecast sales for the specified number of days ahead.
        
        Args:
            days_ahead: Number of days to forecast
            
        Returns:
            Dictionary with forecast data
        """
        try:
            import numpy as np
            from sklearn.linear_model import LinearRegression
            
            # Get historical data - last 90 days
            now = timezone.now()
            start_date = now - timedelta(days=90)
            
            # Prepare data by day
            daily_sales = {}
            for i in range(90):
                day = start_date + timedelta(days=i)
                day_str = day.strftime('%Y-%m-%d')
                daily_sales[day_str] = 0
            
            # Fill in actual sales data
            sales = self.get_sales_in_period(start_date=start_date, end_date=now)
            for sale in sales:
                day_str = sale.created_at.strftime('%Y-%m-%d')
                daily_sales[day_str] = daily_sales.get(day_str, 0) + sale.weight
            
            # Convert to arrays for regression
            X = np.array(range(len(daily_sales))).reshape(-1, 1)
            y = np.array(list(daily_sales.values()))
            
            # Train model
            model = LinearRegression()
            model.fit(X, y)
            
            # Predict future
            future_days = np.array(range(len(daily_sales), len(daily_sales) + days_ahead)).reshape(-1, 1)
            predictions = model.predict(future_days)
            
            # Format results
            forecast_data = {}
            for i in range(days_ahead):
                future_date = now + timedelta(days=i+1)
                forecast_data[future_date.strftime('%Y-%m-%d')] = max(0, predictions[i])  # Ensure non-negative
                
            return {
                'daily_forecast': forecast_data,
                'total_forecast': sum(forecast_data.values()),
                'confidence': model.score(X, y) * 100  
            }
            
        except ImportError:
            logger.warning("scikit-learn not installed, using simple moving average for forecast")
            return self._simple_forecast(days_ahead)
        except Exception as e:
            logger.error(f"Error in sales forecast: {str(e)}")
            return self._simple_forecast(days_ahead)
            
    # def _simple_forecast(self, days_ahead=30):
    #     """Simple moving average forecast as fallback."""
    #     now = timezone.now()
    #     start_date = now - timedelta(days=30)
        
    #     sales = self.get_sales_in_period(start_date=start_date, end_date=now)
    #     daily_avg = sum(s.weight for s in sales) / 30
        
    #     forecast_data = {}
    #     for i in range(days_ahead):
    #         future_date = now + timedelta(days=i+1)
    #         forecast_data[future_date.strftime('%Y-%m-%d')] = daily_avg
            
    #     return {
    #         'daily_forecast': forecast_data,
    #         'total_forecast': daily_avg * days_ahead,
    #         'confidence': 50  # Fixed confidence for simple method
    #     }


    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate model fields."""
        if self.phone_number:
            if len(self.phone_number) < 11:
                raise ValidationError('شماره تلفن باید 11 رقم باشد.')
            if not self.phone_number.isdigit():
                raise ValidationError('شماره تلفن باید عدد باشد.')
        if not self.name:
            raise ValidationError('نام نمی‌تواند خالی باشد.')
        if len(self.name) < 3:
            raise ValidationError('نام باید حداقل 3 حرف باشد.')
        if len(self.name) > 100:
            raise ValidationError('نام نمی‌تواند بیشتر از 100 حرف باشد.')
        
    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.factor_code and self.phone_number:
            self.factor_code = self.phone_number[-2:]
        elif not self.factor_code:
            self.factor_code = ''.join(random.choices(string.ascii_uppercase, k=2))
        super().save(*args, **kwargs)
