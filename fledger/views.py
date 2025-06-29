from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone

from core.decorators.decorators import role_required
from core.PurchaseModel import Purchase
from core.CargoProductModel import VaredKonandeh
from fledger.models import Wallet, Transaction, LedgerEntry


# if wallet_index is 0, then the weight should be calculated based on the order_weight of the purchase else it should be calculated based on the delivery_weight of the purchase

@role_required('admin', 'financial_manager')
def fledger_dashboard(request):
    """
    داشبورد اصلی مدیریت کیف پول
    """
    # آمار کلی
    total_wallets = Wallet.objects.count()
    total_transactions = Transaction.objects.filter(status='approved').count()
    total_balance = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0
    pending_transactions = Transaction.objects.filter(status='pending').count()
    
    # واردکنندگان با بیشترین بدهی (منفی ترین موجودی)
    top_debtors = Wallet.objects.filter(balance__lt=0).order_by('balance')[:5]
    
    # واردکنندگان با بیشترین موجودی مثبت
    top_creditors = Wallet.objects.filter(balance__gt=0).order_by('-balance')[:5]
    
    # تراکنش‌های اخیر
    recent_transactions = Transaction.objects.filter(status='approved').order_by('-created_at')[:10]
    
    context = {
        'total_wallets': total_wallets,
        'total_transactions': total_transactions,
        'total_balance': total_balance,
        'pending_transactions': pending_transactions,
        'top_debtors': top_debtors,
        'top_creditors': top_creditors,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'fledger/dashboard.html', context)


@role_required('admin', 'financial_manager')
def wallet_list(request):
    """
    لیست کیف پول‌ها
    """
    search_query = request.GET.get('search', '')
    balance_filter = request.GET.get('balance_filter', 'all')
    
    wallets = Wallet.objects.select_related('varedkonandeh').all()
    
    if search_query:
        wallets = wallets.filter(
            Q(varedkonandeh__name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if balance_filter == 'positive':
        wallets = wallets.filter(balance__gt=0)
    elif balance_filter == 'negative':
        wallets = wallets.filter(balance__lt=0)
    elif balance_filter == 'zero':
        wallets = wallets.filter(balance=0)
    
    # صفحه‌بندی
    paginator = Paginator(wallets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'balance_filter': balance_filter,
    }
    
    return render(request, 'fledger/wallet_list.html', context)


@role_required('admin', 'financial_manager')
def wallet_detail(request, wallet_id):
    """
    جزئیات کیف پول واردکننده
    """
    wallet = get_object_or_404(Wallet, id=wallet_id)
    
    # محاسبه مجدد موجودی
    wallet.calculate_balance()
    
    # تراکنش‌های کیف پول
    transactions = wallet.transactions.all().order_by('-created_at')
    
    # خلاصه خریدها
    purchase_summary = wallet.get_purchase_summary()
    
    # ثبت‌های دفتر
    ledger_entries = LedgerEntry.objects.filter(varedkonandeh=wallet.varedkonandeh).order_by('-created_at')[:20]
    
    context = {
        'wallet': wallet,
        'transactions': transactions,
        'purchase_summary': purchase_summary,
        'ledger_entries': ledger_entries,
    }
    
    return render(request, 'fledger/wallet_detail.html', context)


@role_required('admin', 'financial_manager')
def create_transaction(request):
    """
    ایجاد تراکنش جدید
    """
    if request.method == 'POST':
        wallet_id = request.POST.get('wallet_id')
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        description = request.POST.get('description', '')
        file = request.FILES.get('file')
        
        try:
            wallet = get_object_or_404(Wallet, id=wallet_id)
            
            with transaction.atomic():
                new_transaction = Transaction.objects.create(
                    wallet=wallet,
                    transaction_type=transaction_type,
                    amount=float(amount),
                    description=description,
                    file=file,
                    created_by=request.user,
                    status='pending'
                )
                
                messages.success(request, f'تراکنش {new_transaction.get_transaction_type_display()} با موفقیت ایجاد شد.')
                
        except Exception as e:
            messages.error(request, f'خطا در ایجاد تراکنش: {str(e)}')
            
        return redirect('fledger:wallet_detail', wallet_id=wallet_id)
    
    # GET request - نمایش فرم
    wallets = Wallet.objects.select_related('varedkonandeh').all()
    context = {'wallets': wallets}
    return render(request, 'fledger/create_transaction.html', context)


@role_required('admin', 'financial_manager')
@require_POST
def approve_transaction(request, transaction_id):
    """
    تایید تراکنش
    """
    trans = get_object_or_404(Transaction, id=transaction_id)
    
    if trans.status == 'pending':
        trans.status = 'approved'
        trans.approved_by = request.user
        trans.approved_at = timezone.now()
        trans.save()  # این خودکار calculate_balance را فراخوانی می‌کند
        
        messages.success(request, f'تراکنش شماره {trans.id} تایید شد.')
    else:
        messages.warning(request, 'این تراکنش قبلاً تایید یا لغو شده است.')
    
    return redirect('fledger:wallet_detail', wallet_id=trans.wallet.id)


@role_required('admin', 'financial_manager')
@require_POST
def reject_transaction(request, transaction_id):
    """
    لغو تراکنش
    """
    trans = get_object_or_404(Transaction, id=transaction_id)
    
    if trans.status == 'pending':
        trans.status = 'rejected'
        trans.approved_by = request.user
        trans.approved_at = timezone.now()
        trans.save()
        
        messages.success(request, f'تراکنش شماره {trans.id} لغو شد.')
    else:
        messages.warning(request, 'این تراکنش قبلاً تایید یا لغو شده است.')
    
    return redirect('fledger:wallet_detail', wallet_id=trans.wallet.id)


@role_required('admin', 'financial_manager')
@require_POST
def recalculate_all_wallets(request):
    """
    محاسبه مجدد موجودی تمام کیف پول‌ها
    """
    try:
        updated_count = 0
        for wallet in Wallet.objects.all():
            wallet.calculate_balance()
            updated_count += 1
            
        messages.success(request, f'موجودی {updated_count} کیف پول بروزرسانی شد.')
        
    except Exception as e:
        messages.error(request, f'خطا در بروزرسانی: {str(e)}')
    
    return redirect('fledger:dashboard')


@role_required('admin', 'financial_manager')
@require_POST
def sync_purchases_to_ledger(request):
    """
    همگام‌سازی خریدها با دفتر کل
    """
    try:
        synced_count = 0
        purchases = Purchase.objects.filter(
            cargo__isnull=False,
            cargo__vared_konandeh__isnull=False,
            is_canceled=False,
            is_archived=False
        )
        
        for purchase in purchases:
            entry = LedgerEntry.create_or_update_entry(purchase)
            if entry:
                synced_count += 1
                
        messages.success(request, f'{synced_count} خرید با دفتر کل همگام‌سازی شد.')
        
    except Exception as e:
        messages.error(request, f'خطا در همگام‌سازی: {str(e)}')
    
    return redirect('fledger:dashboard')


@role_required('admin', 'financial_manager')
def transaction_list(request):
    """
    لیست تراکنش‌ها
    """
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    
    transactions = Transaction.objects.select_related('wallet', 'wallet__varedkonandeh').all()
    
    if status_filter != 'all':
        transactions = transactions.filter(status=status_filter)
        
    if type_filter != 'all':
        transactions = transactions.filter(transaction_type=type_filter)
        
    if search_query:
        transactions = transactions.filter(
            Q(wallet__varedkonandeh__name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # صفحه‌بندی
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_query': search_query,
    }
    
    return render(request, 'fledger/transaction_list.html', context)


@role_required('admin', 'financial_manager')
def ledger_entries(request):
    """
    نمایش ثبت‌های دفتر کل
    """
    search_query = request.GET.get('search', '')
    
    entries = LedgerEntry.objects.select_related('varedkonandeh', 'purchase').all()
    
    if search_query:
        entries = entries.filter(
            Q(varedkonandeh__name__icontains=search_query) |
            Q(purchase__invoice_id__icontains=search_query)
        )
    
    # صفحه‌بندی
    paginator = Paginator(entries, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'fledger/ledger_entries.html', context)


def calculate_weight(purchase):
    """
    محاسبه وزن بر اساس wallet_index
    """
    if purchase.wallet_index == '0':
        return purchase.order_weight or 0
    else:
        return purchase.delivered_weight or 0


@role_required('admin', 'financial_manager')  
def ajax_get_varedkonandeh_info(request, varedkonandeh_id):
    """
    دریافت اطلاعات واردکننده برای AJAX
    """
    try:
        varedkonandeh = get_object_or_404(VaredKonandeh, id=varedkonandeh_id)
        
        # کیف پول واردکننده
        wallet, created = Wallet.objects.get_or_create(
            varedkonandeh=varedkonandeh,
            defaults={'description': f'کیف پول {varedkonandeh.name}'}
        )
        
        if created:
            wallet.calculate_balance()
        
        # خلاصه اطلاعات
        purchase_summary = wallet.get_purchase_summary()
        
        data = {
            'name': varedkonandeh.name,
            'phone': varedkonandeh.phone_number or '',
            'email': varedkonandeh.email or '',
            'balance': float(wallet.balance),
            'total_purchases': purchase_summary['total_purchases'],
            'total_debt': purchase_summary['total_order_amount'],
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    


