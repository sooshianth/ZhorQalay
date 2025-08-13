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
from core.CargoProductModel import VaredKonandeh, CargoProduct
from fledger.models import Wallet, Transaction, LedgerEntry
from fledger.forms import TransactionForm, TransactionEditForm, HazinahForm, HazinahPaymentForm, InvoiceForm, InvoiceItemFormSet
from major.models.Hazinah import Hazinah
from major.models.Invoice import Invoice
from major.models.InvoiceItem import InvoiceItem
from bki_barnameh.models.BarnamehModel import Barnameh


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
    
    # ثبت‌های دفتر - فقط خریدهایی که آدرس ارسال شده باشد
    ledger_entries = LedgerEntry.objects.filter(
        varedkonandeh=wallet.varedkonandeh,
        purchase__is_address_sent__in=['1', 'True']  # پشتیبانی از هر دو فرمت
    ).order_by('-created_at')[:20]
    
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
        form = TransactionForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    new_transaction = form.save(commit=False)
                    new_transaction.created_by = request.user
                    new_transaction.status = 'pending'
                    # اطمینان از اینکه amount یک integer است
                    new_transaction.amount = int(new_transaction.amount)
                    new_transaction.save()
                    
                    messages.success(request, f'تراکنش {new_transaction.get_transaction_type_display()} با موفقیت ایجاد شد.')
                    return redirect('fledger:wallet_detail', wallet_id=new_transaction.wallet.id)
                    
            except Exception as e:
                messages.error(request, f'خطا در ایجاد تراکنش: {str(e)}')
        else:
            messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
    else:
        form = TransactionForm()
    
    context = {'form': form}
    return render(request, 'fledger/create_transaction.html', context)


@role_required('admin', 'financial_manager')
@require_POST
def approve_transaction(request, transaction_id):
    """
    تایید تراکنش
    """
    try:
        trans = get_object_or_404(Transaction, id=transaction_id)
        
        print(f"📝 Approving transaction {transaction_id} by user {request.user}")
        print(f"📊 Transaction status: {trans.status}")
        
        if trans.status == 'pending':
            # اگر تراکنش مربوط به پرداخت هزینه است، فقط ادمین مجاز به تایید است
            if trans.transaction_type == 'Hazinah' and not (request.user.is_superuser or request.user.is_staff):
                messages.error(request, 'فقط ادمین مجاز به تایید پرداخت هزینه است.')
                return redirect('fledger:wallet_detail', wallet_id=trans.wallet.id) if trans.wallet else redirect('fledger:transaction_list')

            with transaction.atomic():
                trans.status = 'approved'
                trans.approved_by = request.user
                trans.approved_at = timezone.now()
                trans.save()  # این خودکار calculate_balance را فراخوانی می‌کند
                
                messages.success(request, f'✅ تراکنش شماره {trans.id} با موفقیت تایید شد.')
                print(f"✅ Transaction {transaction_id} approved successfully")
        else:
            messages.warning(request, 'این تراکنش قبلاً تایید یا لغو شده است.')
            print(f"⚠️ Transaction {transaction_id} already processed: {trans.status}")
        
        return redirect('fledger:wallet_detail', wallet_id=trans.wallet.id)
        
    except Exception as e:
        print(f"❌ Error approving transaction {transaction_id}: {str(e)}")
        messages.error(request, f'خطا در تایید تراکنش: {str(e)}')
        return redirect('fledger:transaction_list')


@role_required('admin', 'financial_manager')
@require_POST
def reject_transaction(request, transaction_id):
    """
    لغو تراکنش
    """
    try:
        trans = get_object_or_404(Transaction, id=transaction_id)
        
        print(f"🚫 Rejecting transaction {transaction_id} by user {request.user}")
        print(f"📊 Transaction status: {trans.status}")
        
        if trans.status == 'pending':
            with transaction.atomic():
                trans.status = 'rejected'
                trans.approved_by = request.user
                trans.approved_at = timezone.now()
                trans.save()
                
                messages.success(request, f'❌ تراکنش شماره {trans.id} لغو شد.')
                print(f"🚫 Transaction {transaction_id} rejected successfully")
        else:
            messages.warning(request, 'این تراکنش قبلاً تایید یا لغو شده است.')
            print(f"⚠️ Transaction {transaction_id} already processed: {trans.status}")
        
        return redirect('fledger:wallet_detail', wallet_id=trans.wallet.id)
        
    except Exception as e:
        print(f"❌ Error rejecting transaction {transaction_id}: {str(e)}")
        messages.error(request, f'خطا در لغو تراکنش: {str(e)}')
        return redirect('fledger:transaction_list')


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
    
    return redirect('fledger:fledger_dashboard')


@role_required('admin', 'financial_manager')
@require_POST
def sync_purchases_to_ledger(request):
    """
    همگام‌سازی خریدها با دفتر کل
    """
    try:
        synced_count = 0
        cleaned_count = 0
        
        # حذف LedgerEntry هایی که برای خریدهای بدون آدرس ارسال شده ایجاد شده‌اند
        invalid_entries = LedgerEntry.objects.exclude(purchase__is_address_sent__in=['1', 'True'])
        cleaned_count = invalid_entries.count()
        invalid_entries.delete()
        
        # همگام‌سازی خریدهای معتبر
        purchases = Purchase.objects.filter(
            cargo__isnull=False,
            cargo__vared_konandeh__isnull=False,
            is_canceled=False,
            is_archived=False,
            is_address_sent__in=['1', 'True']  # فقط خریدهایی که آدرس ارسال شده
        )
        
        for purchase in purchases:
            entry = LedgerEntry.create_or_update_entry(purchase)
            if entry:
                synced_count += 1
                
        messages.success(request, f'{synced_count} خرید با دفتر کل همگام‌سازی شد. {cleaned_count} ثبت نامعتبر حذف شد.')
        
    except Exception as e:
        messages.error(request, f'خطا در همگام‌سازی: {str(e)}')
    
    return redirect('fledger:fledger_dashboard')


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
    index_filter = request.GET.get('index_filter', 'all')
    
    # فقط خریدهایی که آدرس ارسال شده باشد نمایش داده شوند
    entries = LedgerEntry.objects.select_related('varedkonandeh', 'purchase').filter(
        purchase__is_address_sent__in=['1', 'True']  # پشتیبانی از هر دو فرمت
    )
    
    if search_query:
        entries = entries.filter(
            Q(varedkonandeh__name__icontains=search_query) |
            Q(purchase__invoice_id__icontains=search_query) |
            Q(purchase__purchase_number__icontains=search_query)
        )
    
    if index_filter != 'all':
        entries = entries.filter(wallet_index_used=index_filter)
    
    # محاسبه آمار کلی
    all_entries = entries  # کل ثبت‌های فیلتر شده
    total_amount = all_entries.aggregate(total=Sum('total_amount'))['total'] or 0
    total_weight = all_entries.aggregate(total=Sum('weight'))['total'] or 0
    unique_vendors = all_entries.values('varedkonandeh').distinct().count()
    
    # صفحه‌بندی
    paginator = Paginator(entries, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'index_filter': index_filter,
        'total_entries': entries.count(),
        'total_amount': total_amount,
        'total_weight': total_weight,
        'unique_vendors': unique_vendors,
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
def edit_transaction(request, transaction_id):
    """
    ویرایش تراکنش
    """
    transaction_obj = get_object_or_404(Transaction, id=transaction_id)
    
    # فقط تراکنش‌های در انتظار قابل ویرایش هستند
    if transaction_obj.status != 'pending':
        messages.error(request, 'فقط تراکنش‌های در انتظار تایید قابل ویرایش هستند.')
        return redirect('fledger:wallet_detail', wallet_id=transaction_obj.wallet.id)
    
    if request.method == 'POST':
        form = TransactionEditForm(request.POST, request.FILES, instance=transaction_obj)
        
        # Debug: نمایش اطلاعات POST
        print(f"🔍 POST data: {request.POST}")
        print(f"📁 FILES data: {request.FILES}")
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_transaction = form.save()
                    
                print(f"✅ Transaction {transaction_id} updated successfully")
                messages.success(request, 'تراکنش با موفقیت ویرایش شد.')
                return redirect('fledger:wallet_detail', wallet_id=transaction_obj.wallet.id)
                    
            except Exception as e:
                print(f"❌ Error updating transaction {transaction_id}: {str(e)}")
                messages.error(request, f'خطا در ویرایش تراکنش: {str(e)}')
        else:
            # Debug: نمایش خطاهای فرم
            print(f"❌ Form validation failed for transaction {transaction_id}")
            print(f"📝 Form errors: {form.errors}")
            print(f"📝 Form non-field errors: {form.non_field_errors}")
            
            # ایجاد پیغام خطای تفصیلی
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        error_messages.append(f"خطای عمومی: {error}")
                    else:
                        field_label = form[field].label if hasattr(form[field], 'label') else field
                        error_messages.append(f"{field_label}: {error}")
            
            if error_messages:
                messages.error(request, "خطاهای فرم: " + " | ".join(error_messages))
            else:
                messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
    else:
        form = TransactionEditForm(instance=transaction_obj)
        print(f"🔍 Editing transaction {transaction_id} - current data: amount={transaction_obj.amount}, type={transaction_obj.transaction_type}")
    
    context = {
        'form': form,
        'transaction': transaction_obj,
        'wallet': transaction_obj.wallet,
    }
    
    return render(request, 'fledger/edit_transaction.html', context)


@role_required('admin', 'financial_manager')
@require_POST
def delete_transaction(request, transaction_id):
    """
    حذف تراکنش
    """
    transaction_obj = get_object_or_404(Transaction, id=transaction_id)
    
    # فقط تراکنش‌های در انتظار یا لغو شده قابل حذف هستند
    if transaction_obj.status == 'approved':
        messages.error(request, 'تراکنش‌های تایید شده قابل حذف نیستند.')
        return redirect('fledger:wallet_detail', wallet_id=transaction_obj.wallet.id)
    
    wallet_id = transaction_obj.wallet.id
    transaction_obj.delete()
    
    messages.success(request, 'تراکنش با موفقیت حذف شد.')
    return redirect('fledger:wallet_detail', wallet_id=wallet_id)


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


# ==================== ویوهای مدیریت هزینه‌ها ====================

@role_required('admin', 'financial_manager')
def hazinah_list(request):
    """لیست هزینه‌ها"""
    
    # فیلترهای جستجو
    search_query = request.GET.get('search', '')
    cost_type_filter = request.GET.get('cost_type', '')
    approval_status_filter = request.GET.get('approval_status', '')
    
    # کوئری پایه
    hazinah_list = Hazinah.objects.select_related(
        'created_by', 'approved_by'
    ).prefetch_related('transactions')
    
    # اضافه کردن اطلاعات تأیید برای هر هزینه
    for hazinah in hazinah_list:
        hazinah.can_be_approved_by = hazinah.can_be_approved_by(request.user)
    
    # اعمال فیلترها
    if search_query:
        hazinah_list = hazinah_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if cost_type_filter:
        hazinah_list = hazinah_list.filter(cost_type=cost_type_filter)
    
    if approval_status_filter:
        hazinah_list = hazinah_list.filter(approval_status=approval_status_filter)
    
    # مرتب‌سازی
    hazinah_list = hazinah_list.order_by('-created_at')
    
    # صفحه‌بندی
    paginator = Paginator(hazinah_list, 20)
    page_number = request.GET.get('page')
    hazinah_page = paginator.get_page(page_number)
    
    # آمار کلی و مالی
    total_count = Hazinah.objects.count()
    pending_count = Hazinah.objects.filter(approval_status='pending').count()
    approved_count = Hazinah.objects.filter(approval_status__in=['approved', 'auto_approved']).count()
    rejected_count = Hazinah.objects.filter(approval_status='rejected').count()
    financial_approved_count = Hazinah.objects.filter(approval_status='financial_approved').count()
    
    # آمار مالی
    total_amount = Hazinah.objects.aggregate(total=Sum('final_amount'))['total'] or 0
    pending_amount = Hazinah.objects.filter(approval_status='pending').aggregate(total=Sum('final_amount'))['total'] or 0
    approved_amount = Hazinah.objects.filter(approval_status__in=['approved', 'auto_approved']).aggregate(total=Sum('final_amount'))['total'] or 0
    
    # آمار پرداخت
    total_paid_transactions = Transaction.objects.filter(
        hazinah__isnull=False, 
        status='approved'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    remaining_amount = approved_amount - total_paid_transactions
    
    context = {
        'hazinah_page': hazinah_page,
        'search_query': search_query,
        'cost_type_filter': cost_type_filter,
        'approval_status_filter': approval_status_filter,
        'cost_type_choices': Hazinah.COST_TYPES,
        'approval_status_choices': Hazinah.APPROVAL_STATUS,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'financial_approved_count': financial_approved_count,
        'total_amount': total_amount,
        'pending_amount': pending_amount,
        'approved_amount': approved_amount,
        'total_paid_transactions': total_paid_transactions,
        'remaining_amount': remaining_amount,
    }
    
    return render(request, 'fledger/hazinah_list.html', context)


@role_required('admin', 'financial_manager')
def hazinah_detail(request, hazinah_id):
    """جزئیات هزینه"""
    hazinah = get_object_or_404(
        Hazinah.objects.select_related(
            'created_by', 'approved_by'
        ).prefetch_related(
            'transactions__wallet__varedkonandeh',
            'invoice_set__items'
        ),
        id=hazinah_id
    )
    
    # تراکنش‌های مربوط به این هزینه
    transactions = hazinah.transactions.all().order_by('-created_at')
    
    # آمار پرداخت - استفاده از property های مدل
    total_paid = hazinah.total_transactions_amount
    remaining_amount = hazinah.remaining_amount
    
    # اطلاعات تأیید
    approval_info = hazinah.get_approval_info()
    can_approve = hazinah.can_be_approved_by(request.user)
    
    context = {
        'hazinah': hazinah,
        'transactions': transactions,
        'total_paid': total_paid,
        'remaining_amount': remaining_amount,
        'payment_percentage': (total_paid / hazinah.final_amount * 100) if hazinah.final_amount and hazinah.final_amount > 0 else 0,
        'approval_info': approval_info,
        'can_approve': can_approve,
    }
    
    return render(request, 'fledger/hazinah_detail.html', context)


@role_required('admin', 'financial_manager')
def create_hazinah(request):
    """ایجاد هزینه جدید"""
    if request.method == 'POST':
        hazinah_form = HazinahForm(request.POST, request.FILES)
        
        if hazinah_form.is_valid():
            try:
                hazinah = hazinah_form.save(commit=False)
                hazinah.created_by = request.user
                
                # اگر مبلغ وارد نشده، آن را صفر قرار دهید
                if not hazinah.amount:
                    hazinah.amount = 0
                
                hazinah.save()
                
                messages.success(request, 'هزینه با موفقیت ثبت شد. حالا می‌توانید فاکتورهای مربوطه را اضافه کنید.')
                return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
                    
            except Exception as e:
                messages.error(request, f'خطا در ثبت هزینه: {str(e)}')
    else:
        hazinah_form = HazinahForm()
    
    context = {
        'hazinah_form': hazinah_form,
        'title': 'ثبت هزینه جدید'
    }
    
    return render(request, 'fledger/create_hazinah.html', context)


@role_required('admin', 'financial_manager')
def edit_hazinah(request, hazinah_id):
    """ویرایش هزینه"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    # فقط هزینه‌های در انتظار تأیید قابل ویرایش هستند
    if hazinah.approval_status != 'pending':
        messages.error(request, 'فقط هزینه‌های در انتظار تأیید قابل ویرایش هستند.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    if request.method == 'POST':
        form = HazinahForm(request.POST, request.FILES, instance=hazinah)
        if form.is_valid():
            form.save()
            messages.success(request, 'هزینه با موفقیت بروزرسانی شد.')
            return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    else:
        form = HazinahForm(instance=hazinah)
    
    context = {
        'form': form,
        'hazinah': hazinah,
        'title': 'ویرایش هزینه'
    }
    
    return render(request, 'fledger/edit_hazinah.html', context)


@role_required('admin', 'financial_manager')
@require_POST
def approve_hazinah(request, hazinah_id):
    """تأیید هزینه"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    if not hazinah.can_be_approved():
        messages.error(request, 'این هزینه قابل تأیید نیست.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    if not hazinah.can_be_approved_by(request.user):
        messages.error(request, 'شما مجاز به تأیید این هزینه نیستید.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    approval_notes = request.POST.get('approval_notes', '')
    
    try:
        hazinah.approve(request.user, approval_notes)
        
        if hazinah.approval_status == 'financial_approved':
            messages.success(request, 'هزینه توسط مدیر مالی تأیید شد. در انتظار تأیید ادمین.')
        else:
            messages.success(request, 'هزینه با موفقیت تأیید شد.')
            
    except Exception as e:
        messages.error(request, f'خطا در تأیید هزینه: {str(e)}')
    
    return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)


@role_required('admin', 'financial_manager')
@require_POST
def reject_hazinah(request, hazinah_id):
    """رد هزینه"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    if not hazinah.can_be_approved():
        messages.error(request, 'این هزینه قابل رد نیست.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    rejection_notes = request.POST.get('rejection_notes', '')
    
    try:
        hazinah.reject(request.user, rejection_notes)
        messages.success(request, 'هزینه رد شد.')
    except Exception as e:
        messages.error(request, f'خطا در رد هزینه: {str(e)}')
    
    return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)


@role_required('admin', 'financial_manager')
def pay_hazinah(request, hazinah_id):
    """پرداخت هزینه (ایجاد تراکنش)"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    # بررسی اینکه آیا هزینه قابل پرداخت است
    if not hazinah.can_be_paid():
        messages.error(request, 'این هزینه قابل پرداخت نیست. هزینه باید تأیید شده باشد.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    # محاسبه مبلغ باقی‌مانده
    remaining_amount = hazinah.remaining_amount
    
    if remaining_amount <= 0:
        messages.info(request, 'این هزینه به طور کامل پرداخت شده است.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    if request.method == 'POST':
        form = HazinahPaymentForm(request.POST, request.FILES, hazinah=hazinah)
        if form.is_valid():
            payment_amount = form.cleaned_data['amount']
            
            try:
                with transaction.atomic():
                    # ایجاد تراکنش (نیاز به تأیید ادمین). بدون کیف پول و روش پرداخت در فرم.
                    new_transaction = Transaction.objects.create(
                        wallet=None,
                        transaction_type='Hazinah',
                        amount=payment_amount,
                        description=form.cleaned_data['description'],
                        file=form.cleaned_data['attachment'],
                        hazinah=hazinah,
                        payment_method=None,
                        created_by=request.user,
                        status='pending'  # تراکنش‌های پرداخت هزینه نیاز به تایید دارند
                    )

                    # اگر تاریخ پرداخت ثبت شده بود، به عنوان approved_at موقت ذخیره نمی‌کنیم؛ فقط در توضیحات اشاره می‌کنیم
                    paid_at = form.cleaned_data.get('paid_at')
                    if paid_at:
                        new_transaction.description = f"{new_transaction.description or ''}\nتاریخ انجام پرداخت: {paid_at}"
                        new_transaction.save()

                    messages.success(request, f'پرداخت {payment_amount:,} ریال با موفقیت ثبت شد و در انتظار تایید است.')
                    return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)

            except Exception as e:
                messages.error(request, f'خطا در ثبت پرداخت: {str(e)}')
    else:
        # پیش‌فرض مبلغ پرداخت برابر با مبلغ باقی‌مانده
        initial_data = {'amount': remaining_amount}
        form = HazinahPaymentForm(initial=initial_data, hazinah=hazinah)
    
    context = {
        'form': form,
        'hazinah': hazinah,
        'remaining_amount': remaining_amount,
    }
    
    return render(request, 'fledger/pay_hazinah.html', context)


@role_required('admin', 'financial_manager')
@require_POST
def delete_hazinah(request, hazinah_id):
    """حذف هزینه"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    # بررسی اینکه هزینه تراکنش نداشته باشد
    if hazinah.has_transactions:
        messages.error(request, 'هزینه‌هایی که تراکنش دارند قابل حذف نیستند.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    try:
        hazinah_title = hazinah.title
        hazinah.delete()
        messages.success(request, f'هزینه "{hazinah_title}" با موفقیت حذف شد.')
        return redirect('fledger:hazinah_list')
    except Exception as e:
        messages.error(request, f'خطا در حذف هزینه: {str(e)}')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)


# ==================== View های مربوط به فاکتورها ====================

@role_required('admin', 'financial_manager')
def invoice_list(request):
    """لیست تمام فاکتورها"""
    search_query = request.GET.get('search', '')
    invoice_type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    
    invoices = Invoice.objects.select_related('hazinah', 'income').prefetch_related('items').all()
    
    # فیلتر جستجو
    if search_query:
        invoices = invoices.filter(
            Q(invoice_id__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(hazinah__title__icontains=search_query) |
            Q(income__title__icontains=search_query)
        )
    
    # فیلتر نوع فاکتور
    if invoice_type_filter:
        invoices = invoices.filter(type=invoice_type_filter)
    
    # فیلتر وضعیت (بر اساس وضعیت تأیید هزینه/درآمد مرتبط)
    if status_filter == 'approved':
        invoices = invoices.filter(
            Q(hazinah__approval_status='approved') |
            Q(income__approval_status='approved')
        )
    elif status_filter == 'pending':
        invoices = invoices.filter(
            Q(hazinah__approval_status__in=['pending', 'auto_approved']) |
            Q(income__approval_status__in=['pending', 'auto_approved'])
        )
    elif status_filter == 'rejected':
        invoices = invoices.filter(
            Q(hazinah__approval_status='rejected') |
            Q(income__approval_status='rejected')
        )
    
    # مرتب‌سازی بر اساس تاریخ ایجاد (جدیدترین‌ها اول)
    invoices = invoices.order_by('-created_at')
    
    # صفحه‌بندی
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # آمار فاکتورها
    total_invoices = Invoice.objects.count()
    expense_invoices = Invoice.objects.filter(type='Hazinah').count()
    income_invoices = Invoice.objects.filter(type='Income').count()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'invoice_type_filter': invoice_type_filter,
        'status_filter': status_filter,
        'total_invoices': total_invoices,
        'expense_invoices': expense_invoices,
        'income_invoices': income_invoices,
    }
    
    return render(request, 'fledger/invoice_list.html', context)


@role_required('admin', 'financial_manager')
def add_invoice_to_hazinah(request, hazinah_id):
    """افزودن فاکتور جدید به هزینه"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    
    # بررسی اینکه هزینه از نوع خرید محصول باشد
    if hazinah.cost_type != 'product_purchase':
        messages.error(request, 'فقط برای هزینه‌های خرید محصول می‌توان فاکتور اضافه کرد.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    # بررسی وضعیت هزینه - اجازه افزودن فاکتور به هزینه‌های pending یا auto_approved
    if hazinah.approval_status not in ['pending', 'auto_approved']:
        messages.error(request, 'فقط هزینه‌های در انتظار تأیید یا تأیید شده خودکار قابل ویرایش هستند.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, request.FILES)
        invoice_formset = InvoiceItemFormSet(request.POST)
        
        if invoice_form.is_valid() and invoice_formset.is_valid():
            try:
                with transaction.atomic():
                    # ایجاد فاکتور
                    invoice = invoice_form.save(commit=False)
                    invoice.hazinah = hazinah
                    invoice.type = 'Hazinah'
                    # در صورتی که هزینه مشخص شده، فیلد income را خالی کن
                    invoice.income = None
                    invoice.save()
                    
                    # ایجاد آیتم‌های فاکتور
                    invoice_formset.instance = invoice
                    invoice_formset.save()
                    
                    # بروزرسانی مبلغ هزینه
                    hazinah.update_amount_from_invoices()
                    
                    messages.success(request, 'فاکتور با موفقیت اضافه شد.')
                    return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
                    
            except Exception as e:
                messages.error(request, f'خطا در افزودن فاکتور: {str(e)}')
    else:
        # پیش‌تعیین نوع فاکتور به عنوان هزینه و انتخاب هزینه مربوطه
        initial_data = {
            'type': 'Hazinah',
            'hazinah': hazinah
        }
        invoice_form = InvoiceForm(initial=initial_data)
        invoice_formset = InvoiceItemFormSet()
    
    context = {
        'hazinah': hazinah,
        'invoice_form': invoice_form,
        'invoice_formset': invoice_formset,
        'title': f'افزودن فاکتور به هزینه: {hazinah.title}'
    }
    
    return render(request, 'fledger/add_invoice.html', context)


@role_required('admin', 'financial_manager')
def edit_invoice(request, hazinah_id, invoice_id):
    """ویرایش فاکتور"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    invoice = get_object_or_404(Invoice, id=invoice_id, hazinah=hazinah)
    
    # بررسی اینکه هزینه از نوع خرید محصول باشد
    if hazinah.cost_type != 'product_purchase':
        messages.error(request, 'فقط برای هزینه‌های خرید محصول می‌توان فاکتور ویرایش کرد.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    # بررسی وضعیت هزینه - اجازه ویرایش فاکتور برای هزینه‌های pending یا auto_approved
    if hazinah.approval_status not in ['pending', 'auto_approved']:
        messages.error(request, 'فقط هزینه‌های در انتظار تأیید یا تأیید شده خودکار قابل ویرایش هستند.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, request.FILES, instance=invoice)
        invoice_formset = InvoiceItemFormSet(request.POST, instance=invoice)
        
        if invoice_form.is_valid() and invoice_formset.is_valid():
            try:
                with transaction.atomic():
                    # ویرایش فاکتور - اطمینان از اینکه نوع هزینه باقی می‌ماند
                    updated_invoice = invoice_form.save(commit=False)
                    updated_invoice.hazinah = hazinah
                    updated_invoice.type = 'Hazinah'
                    updated_invoice.income = None  # اطمینان از خالی بودن فیلد درآمد
                    updated_invoice.save()
                    
                    # ویرایش آیتم‌های فاکتور
                    invoice_formset.save()
                    
                    # بروزرسانی مبلغ هزینه
                    hazinah.update_amount_from_invoices()
                    
                    messages.success(request, 'فاکتور با موفقیت ویرایش شد.')
                    return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
                    
            except Exception as e:
                messages.error(request, f'خطا در ویرایش فاکتور: {str(e)}')
    else:
        invoice_form = InvoiceForm(instance=invoice)
        invoice_formset = InvoiceItemFormSet(instance=invoice)
    
    context = {
        'hazinah': hazinah,
        'invoice': invoice,
        'invoice_form': invoice_form,
        'invoice_formset': invoice_formset,
        'title': f'ویرایش فاکتور: {invoice.invoice_id}'
    }
    
    return render(request, 'fledger/edit_invoice.html', context)


@role_required('admin', 'financial_manager')
def delete_invoice(request, hazinah_id, invoice_id):
    """حذف فاکتور"""
    hazinah = get_object_or_404(Hazinah, id=hazinah_id)
    invoice = get_object_or_404(Invoice, id=invoice_id, hazinah=hazinah)
    
    # بررسی اینکه هزینه از نوع خرید محصول باشد
    if hazinah.cost_type != 'product_purchase':
        messages.error(request, 'فقط برای هزینه‌های خرید محصول می‌توان فاکتور حذف کرد.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    # بررسی وضعیت هزینه - اجازه حذف فاکتور برای هزینه‌های pending یا auto_approved
    if hazinah.approval_status not in ['pending', 'auto_approved']:
        messages.error(request, 'فقط هزینه‌های در انتظار تأیید یا تأیید شده خودکار قابل ویرایش هستند.')
        return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    # بررسی اینکه آیا این آخرین فاکتور است
    if hazinah.invoices.count() <= 1:
        messages.warning(request, 'با حذف این فاکتور، هزینه بدون فاکتور خواهد شد و مبلغ آن به صفر تبدیل می‌شود.')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                invoice_id_str = invoice.invoice_id
                invoice.delete()
                
                # بروزرسانی مبلغ هزینه
                hazinah.amount = hazinah.calculate_amount_from_invoices()
                hazinah.save()
                
                messages.success(request, f'فاکتور "{invoice_id_str}" با موفقیت حذف شد.')
                return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
                
        except Exception as e:
            messages.error(request, f'خطا در حذف فاکتور: {str(e)}')
            return redirect('fledger:hazinah_detail', hazinah_id=hazinah.id)
    
    context = {
        'hazinah': hazinah,
        'invoice': invoice,
        'title': f'حذف فاکتور: {invoice.invoice_id}'
    }
    
    return render(request, 'fledger/delete_invoice.html', context)


@role_required('admin', 'financial_manager')
def invoice_detail(request, invoice_id):
    """مشاهده جزئیات فاکتور"""
    invoice = get_object_or_404(
        Invoice.objects.select_related('hazinah', 'income').prefetch_related('items__cargo_product', 'items__non_bazargah_product'),
        id=invoice_id
    )
    
    context = {
        'invoice': invoice,
        'title': f'جزئیات فاکتور: {invoice.invoice_id}'
    }
    
    return render(request, 'fledger/invoice_detail.html', context)


@role_required('admin', 'financial_manager')
def create_invoice(request):
    """ایجاد فاکتور جدید (مستقل)"""
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, request.FILES)
        invoice_formset = InvoiceItemFormSet(request.POST)
        
        if invoice_form.is_valid() and invoice_formset.is_valid():
            try:
                with transaction.atomic():
                    # ایجاد فاکتور
                    invoice = invoice_form.save()
                    
                    # ایجاد آیتم‌های فاکتور
                    for form in invoice_formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            item = form.save(commit=False)
                            item.invoice = invoice
                            item.save()
                    
                    # بروزرسانی مبلغ هزینه/درآمد مرتبط در صورت نیاز
                    if invoice.hazinah and invoice.hazinah.cost_type == 'product_purchase':
                        invoice.hazinah.amount = invoice.hazinah.calculate_amount_from_invoices()
                        invoice.hazinah.save()
                    
                    messages.success(request, f'فاکتور "{invoice.invoice_id}" با موفقیت ایجاد شد.')
                    return redirect('fledger:invoice_detail', invoice_id=invoice.id)
                    
            except Exception as e:
                messages.error(request, f'خطا در ایجاد فاکتور: {str(e)}')
        else:
            # نمایش خطاهای validation
            if not invoice_form.is_valid():
                for field, errors in invoice_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{invoice_form[field].label if field != "__all__" else "خطای عمومی"}: {error}')
            
            if not invoice_formset.is_valid():
                for form_errors in invoice_formset.errors:
                    for field, errors in form_errors.items():
                        for error in errors:
                            if error:  # فقط خطاهای غیر خالی
                                messages.error(request, f'آیتم فاکتور - {field}: {error}')
    else:
        invoice_form = InvoiceForm()
        invoice_formset = InvoiceItemFormSet()
    
    context = {
        'invoice_form': invoice_form,
        'invoice_formset': invoice_formset,
        'title': 'ایجاد فاکتور جدید'
    }
    
    return render(request, 'fledger/create_invoice.html', context)


# ==================== داشبورد لجستیک ====================

@role_required('admin', 'logistics_manager')
def logistics_dashboard(request):
    """
    داشبورد اختصاصی مدیر لجستیک برای رصد خرید و فروش
    """
    from major.models.Invoice import Invoice
    from major.models.InvoiceItem import InvoiceItem
    from django_jalali.db import models as jmodels
    from datetime import datetime
    import jdatetime
    
    # دریافت فیلترهای زمانی از درخواست
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    expense_start_date_str = request.GET.get('expense_start_date', '')
    expense_end_date_str = request.GET.get('expense_end_date', '')
    
    # تبدیل تاریخ‌های جلالی به datetime برای فیلتر کردن
    start_date = None
    end_date = None
    expense_start_date = None
    expense_end_date = None
    
    if start_date_str:
        try:
            start_date = jdatetime.datetime.strptime(start_date_str, '%Y/%m/%d').date()
        except:
            start_date = None
    
    if end_date_str:
        try:
            end_date = jdatetime.datetime.strptime(end_date_str, '%Y/%m/%d').date()
        except:
            end_date = None
    
    if expense_start_date_str:
        try:
            expense_start_date = jdatetime.datetime.strptime(expense_start_date_str, '%Y/%m/%d').date()
        except:
            expense_start_date = None
    
    if expense_end_date_str:
        try:
            expense_end_date = jdatetime.datetime.strptime(expense_end_date_str, '%Y/%m/%d').date()
        except:
            expense_end_date = None
    
    # لیست کوتاژ‌های فعال (همه)
    active_cargos = CargoProduct.objects.filter(status=True).select_related('vared_konandeh').order_by('-last_modified')
    
    # آمار کلی کوتاژ‌ها
    total_active_cargos = CargoProduct.objects.filter(status=True).count()
    total_inactive_cargos = CargoProduct.objects.filter(status=False).count()
    
    # فیلتر کردن هزینه‌ها بر اساس تاریخ
    product_purchase_expenses_query = Hazinah.objects.filter(
        cost_type='product_purchase',
        approval_status__in=['approved', 'auto_approved']
    )
    
    if expense_start_date:
        product_purchase_expenses_query = product_purchase_expenses_query.filter(
            expense_date__gte=expense_start_date
        )
    
    if expense_end_date:
        product_purchase_expenses_query = product_purchase_expenses_query.filter(
            expense_date__lte=expense_end_date
        )
    
    product_purchase_expenses = product_purchase_expenses_query.select_related('approved_by').prefetch_related('invoice_set').order_by('-created_at')
    
    # فیلتر کردن بارنامه‌ها بر اساس تاریخ
    bazargah_bills_query = Barnameh.objects.filter(
        type='Bazargah',
        purchase__isnull=False
    )
    
    if start_date:
        bazargah_bills_query = bazargah_bills_query.filter(
            barnameh_created_at__gte=start_date
        )
    
    if end_date:
        bazargah_bills_query = bazargah_bills_query.filter(
            barnameh_created_at__lte=end_date
        )
    
    bazargah_bills = bazargah_bills_query.select_related('purchase', 'purchase__cargo').order_by('-barnameh_created_at')
    
    non_bazargah_bills_query = Barnameh.objects.filter(
        type='Non_Bazargah',
        non_bazargah_purchase__isnull=False
    )
    
    if start_date:
        non_bazargah_bills_query = non_bazargah_bills_query.filter(
            barnameh_created_at__gte=start_date
        )
    
    if end_date:
        non_bazargah_bills_query = non_bazargah_bills_query.filter(
            barnameh_created_at__lte=end_date
        )
    
    non_bazargah_bills = non_bazargah_bills_query.select_related('non_bazargah_purchase', 'non_bazargah_purchase__product').order_by('-barnameh_created_at')
    
    # پردازش هزینه‌ها و استخراج اطلاعات از فاکتورها
    processed_expenses = []
    total_bazargah_expenses = 0
    total_non_bazargah_expenses = 0
    total_bazargah_weight = 0
    total_non_bazargah_weight = 0
    
    for expense in product_purchase_expenses:
        expense_data = {
            'expense': expense,
            'bazargah_items': [],
            'non_bazargah_items': [],
            'total_bazargah_amount': 0,
            'total_non_bazargah_amount': 0,
            'total_bazargah_weight': 0,
            'total_non_bazargah_weight': 0,
            'invoice_count': 0
        }
        
        # بررسی فاکتورهای مرتبط
        for invoice in expense.invoice_set.all():
            expense_data['invoice_count'] += 1
            
            # بررسی آیتم‌های فاکتور
            for item in invoice.items.all():
                if item.product_type == 'Bazargah' and item.cargo_product:
                    item_total = item.get_total_price()
                    item_weight = item.amount or 0
                    
                    expense_data['bazargah_items'].append({
                        'product': item.cargo_product,
                        'weight': item_weight,
                        'price': item.price,
                        'total_amount': item_total,
                        'invoice': invoice
                    })
                    
                    expense_data['total_bazargah_amount'] += item_total
                    expense_data['total_bazargah_weight'] += item_weight
                    total_bazargah_expenses += item_total
                    total_bazargah_weight += item_weight
                    
                elif item.product_type == 'NonBazargah' and item.non_bazargah_product:
                    item_total = item.get_total_price()
                    item_weight = item.amount or 0
                    
                    expense_data['non_bazargah_items'].append({
                        'product': item.non_bazargah_product,
                        'weight': item_weight,
                        'price': item.price,
                        'total_amount': item_total,
                        'invoice': invoice
                    })
                    
                    expense_data['total_non_bazargah_amount'] += item_total
                    expense_data['total_non_bazargah_weight'] += item_weight
                    total_non_bazargah_expenses += item_total
                    total_non_bazargah_weight += item_weight
        
        processed_expenses.append(expense_data)
    
    # آمار بارنامه‌ها (درآمدها)
    total_bazargah_bill_weight = 0
    total_bazargah_bill_revenue = 0
    
    bazargah_bills_with_revenue = []
    for bill in bazargah_bills:
        weight = bill.tonnage or 0
        total_bazargah_bill_weight += weight
        revenue = bill.total_sales_amount or 0
        total_bazargah_bill_revenue += revenue
        bazargah_bills_with_revenue.append(bill)
    
    total_non_bazargah_bill_weight = 0
    total_non_bazargah_bill_revenue = 0
    
    non_bazargah_bills_with_revenue = []
    for bill in non_bazargah_bills:
        weight = bill.tonnage or 0
        total_non_bazargah_bill_weight += weight
        revenue = bill.get_total_sales_amount() or 0
        total_non_bazargah_bill_revenue += revenue
        non_bazargah_bills_with_revenue.append(bill)
    
    # هزینه‌های عمومی (سایر انواع هزینه) - با فیلتر زمانی
    recent_expenses_query = Hazinah.objects.filter(
        approval_status__in=['approved', 'auto_approved']
    ).exclude(cost_type='product_purchase')
    
    if expense_start_date:
        recent_expenses_query = recent_expenses_query.filter(
            expense_date__gte=expense_start_date
        )
    
    if expense_end_date:
        recent_expenses_query = recent_expenses_query.filter(
            expense_date__lte=expense_end_date
        )
    
    recent_expenses = recent_expenses_query.order_by('-created_at')
    
    # بررسی درخواست خروجی اکسل
    export_type = request.GET.get('export', '')
    
    if export_type == 'expenses':
        return export_expenses_to_excel(request, processed_expenses, expense_start_date, expense_end_date)
    elif export_type == 'barnamehs':
        return export_barnamehs_to_excel(request, bazargah_bills, non_bazargah_bills, start_date, end_date)
    
    context = {
        # کوتاژ‌ها
        'active_cargos': active_cargos,
        'total_active_cargos': total_active_cargos,
        'total_inactive_cargos': total_inactive_cargos,
        
        # هزینه‌های خرید محصول با جزئیات
        'processed_expenses': processed_expenses,
        'total_bazargah_expenses': total_bazargah_expenses,
        'total_non_bazargah_expenses': total_non_bazargah_expenses,
        'total_bazargah_weight': total_bazargah_weight,
        'total_non_bazargah_weight': total_non_bazargah_weight,
        
        # بارنامه‌های بازارگاهی
        'bazargah_bills': bazargah_bills_with_revenue,
        'total_bazargah_bill_weight': total_bazargah_bill_weight,
        'total_bazargah_bill_revenue': total_bazargah_bill_revenue,
        
        # بارنامه‌های غیر بازارگاهی
        'non_bazargah_bills': non_bazargah_bills_with_revenue,
        'total_non_bazargah_bill_weight': total_non_bazargah_bill_weight,
        'total_non_bazargah_bill_revenue': total_non_bazargah_bill_revenue,
        
        # هزینه‌های عمومی
        'recent_expenses': recent_expenses,
        
        # آمار کلی
        'total_expenses_count': len(processed_expenses),
        'total_barnamehs_count': len(bazargah_bills) + len(non_bazargah_bills),
        
        # فیلترهای زمانی
        'start_date': start_date_str,
        'end_date': end_date_str,
        'expense_start_date': expense_start_date_str,
        'expense_end_date': expense_end_date_str,
    }
    
    return render(request, 'fledger/logistics_dashboard.html', context)


def export_expenses_to_excel(request, processed_expenses, start_date, end_date):
    """
    خروجی اکسل از هزینه‌های خرید محصول
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from django.http import HttpResponse
    import jdatetime
    
    # ایجاد فایل اکسل
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "هزینه‌ها"
    
    # تنظیم جهت راست به چپ برای کل شیت
    ws.sheet_view.rightToLeft = True
    
    # تنظیم ستون‌ها
    headers = [
        'عنوان هزینه', 'تاریخ هزینه', 'نوع محصول', 'کوتاژ/محصول', 'کشور/توضیحات', 'وزن/مقدار', 'فی واحد (ریال)', 'مبلغ کل (ریال)', 'شماره فاکتور'
    ]
    
    # استایل‌های هدر
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", textRotation=0)
    
    # اضافه کردن هدرها
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # تنظیم عرض ستون‌ها
    column_widths = [25, 15, 20, 25, 20, 15, 20, 20, 20]
    for col, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    
    # اضافه کردن داده‌ها
    row = 2
    for expense_data in processed_expenses:
        expense = expense_data['expense']
        
        # آیتم‌های بازارگاهی
        for item in expense_data['bazargah_items']:
            ws.cell(row=row, column=1, value=expense.title)
            ws.cell(row=row, column=2, value=expense.expense_date.strftime('%Y/%m/%d') if expense.expense_date else '')
            ws.cell(row=row, column=3, value='بازارگاهی')
            ws.cell(row=row, column=4, value=item['product'].cottage if item['product'].cottage else '')
            ws.cell(row=row, column=5, value=item['product'].get_country_display() if hasattr(item['product'], 'get_country_display') else '')
            ws.cell(row=row, column=6, value=item['weight'])
            ws.cell(row=row, column=7, value=item['price'])
            ws.cell(row=row, column=8, value=item['total_amount'])
            ws.cell(row=row, column=9, value=item['invoice'].invoice_id if item['invoice'].invoice_id else '')
            
            # تنظیم جهت راست به چپ برای سلول‌ها
            for col in range(1, 10):
                cell = ws.cell(row=row, column=col)
                cell.alignment = Alignment(horizontal="right", vertical="center")
            
            row += 1
        
        # آیتم‌های غیر بازارگاهی
        for item in expense_data['non_bazargah_items']:
            ws.cell(row=row, column=1, value=expense.title)
            ws.cell(row=row, column=2, value=expense.expense_date.strftime('%Y/%m/%d') if expense.expense_date else '')
            ws.cell(row=row, column=3, value='خارج بازارگاه')
            ws.cell(row=row, column=4, value=item['product'].name if item['product'].name else '')
            ws.cell(row=row, column=5, value=item['product'].description if hasattr(item['product'], 'description') and item['product'].description else '')
            ws.cell(row=row, column=6, value=item['weight'])
            ws.cell(row=row, column=7, value=item['price'])
            ws.cell(row=row, column=8, value=item['total_amount'])
            ws.cell(row=row, column=9, value=item['invoice'].invoice_id if item['invoice'].invoice_id else '')
            
            # تنظیم جهت راست به چپ برای سلول‌ها
            for col in range(1, 10):
                cell = ws.cell(row=row, column=col)
                cell.alignment = Alignment(horizontal="right", vertical="center")
            
            row += 1
    
    # ایجاد نام فایل منحصر به فرد و توصیفی
    current_jalali = jdatetime.datetime.now()
    timestamp = current_jalali.strftime('%Y%m%d_%H%M%S')
    filename = f"هزینه_های_خرید_محصول_{timestamp}"
    
    if start_date:
        if isinstance(start_date, str) and start_date.strip():
            start_date_clean = start_date.replace('/', '').replace('-', '')
            filename += f"_از_{start_date_clean}"
        elif hasattr(start_date, 'strftime'):
            start_date_clean = start_date.strftime('%Y%m%d')
            filename += f"_از_{start_date_clean}"
    if end_date:
        if isinstance(end_date, str) and end_date.strip():
            end_date_clean = end_date.replace('/', '').replace('-', '')
            filename += f"_تا_{end_date_clean}"
        elif hasattr(end_date, 'strftime'):
            end_date_clean = end_date.strftime('%Y%m%d')
            filename += f"_تا_{end_date_clean}"
    
    date = timezone.now().strftime('%Y%m%d_%H%M')
    filename = f"expenses_{date}.xlsx"
    
    # پاسخ HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response


def export_barnamehs_to_excel(request, bazargah_bills, non_bazargah_bills, start_date, end_date):
    """
    خروجی اکسل از بارنامه‌ها
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from django.http import HttpResponse
    import jdatetime
    
    # ایجاد فایل اکسل
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "بارنامه‌ها"
    
    # تنظیم جهت راست به چپ برای کل شیت
    ws.sheet_view.rightToLeft = True
    
    # تنظیم ستون‌ها
    headers = [
        'شماره بارنامه', 'نوع', 'کوتاژ/محصول', 'مشتری', 'وزن/مقدار',
        'فی فروش (ریال)', 'کل درآمد (ریال)', 'تاریخ صدور', 'وضعیت'
    ]
    
    # استایل‌های هدر
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", textRotation=0)
    
    # اضافه کردن هدرها
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # تنظیم عرض ستون‌ها
    column_widths = [20, 15, 25, 25, 15, 20, 20, 15, 20]
    for col, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    
    # اضافه کردن داده‌ها
    row = 2
    
    # بارنامه‌های بازارگاهی
    for bill in bazargah_bills:
        ws.cell(row=row, column=1, value=bill.number or '')
        ws.cell(row=row, column=2, value='بازارگاهی')
        ws.cell(row=row, column=3, value=bill.purchase.cargo.name if bill.purchase and bill.purchase.cargo else '')
        ws.cell(row=row, column=4, value=bill.get_buyer_name() or '')
        ws.cell(row=row, column=5, value=bill.tonnage or 0)
        ws.cell(row=row, column=6, value=bill.get_customer_price() or 0)
        ws.cell(row=row, column=7, value=bill.total_sales_amount or 0)
        ws.cell(row=row, column=8, value=bill.barnameh_created_at.strftime('%Y/%m/%d') if bill.barnameh_created_at else '')
        ws.cell(row=row, column=9, value='فعال' if bill.status == 'SENT_TO_BKI' else 'غیرفعال')
        
        # تنظیم جهت راست به چپ برای سلول‌ها
        for col in range(1, 10):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(horizontal="right", vertical="center")
        
        row += 1
    
    # بارنامه‌های غیر بازارگاهی
    for bill in non_bazargah_bills:
        ws.cell(row=row, column=1, value=bill.number or '')
        ws.cell(row=row, column=2, value='خارج بازارگاه')
        ws.cell(row=row, column=3, value=bill.non_bazargah_purchase.product.name if bill.non_bazargah_purchase and bill.non_bazargah_purchase.product else '')
        ws.cell(row=row, column=4, value=bill.get_buyer_name() or '')
        ws.cell(row=row, column=5, value=bill.tonnage or 0)
        ws.cell(row=row, column=6, value=bill.get_customer_price() or 0)
        ws.cell(row=row, column=7, value=bill.total_sales_amount or 0)
        ws.cell(row=row, column=8, value=bill.barnameh_created_at.strftime('%Y/%m/%d') if bill.barnameh_created_at else '')
        ws.cell(row=row, column=9, value='فعال' if bill.status == 'SENT_TO_BKI' else 'غیرفعال')
        
        # تنظیم جهت راست به چپ برای سلول‌ها
        for col in range(1, 10):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(horizontal="right", vertical="center")
        
        row += 1
    
    # ایجاد نام فایل منحصر به فرد و توصیفی
    current_jalali = jdatetime.datetime.now()
    timestamp = current_jalali.strftime('%Y%m%d_%H%M%S')
    filename = f"بارنامه_ها_{timestamp}"
    
    if start_date:
        if isinstance(start_date, str) and start_date.strip():
            start_date_clean = start_date.replace('/', '').replace('-', '')
            filename += f"_از_{start_date_clean}"
        elif hasattr(start_date, 'strftime'):
            start_date_clean = start_date.strftime('%Y%m%d')
            filename += f"_از_{start_date_clean}"
    if end_date:
        if isinstance(end_date, str) and end_date.strip():
            end_date_clean = end_date.replace('/', '').replace('-', '')
            filename += f"_تا_{end_date_clean}"
        elif hasattr(end_date, 'strftime'):
            end_date_clean = end_date.strftime('%Y%m%d')
            filename += f"_تا_{end_date_clean}"

    date = timezone.now().strftime('%Y%m%d_%H%M')
    filename = f"barnamehs_{date}.xlsx"

    # پاسخ HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response
