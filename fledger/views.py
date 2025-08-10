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
                        status='approved'  # تغییر: تراکنش‌های پرداخت هزینه بلافاصله تأیید می‌شوند
                    )

                    # اگر تاریخ پرداخت ثبت شده بود، به عنوان approved_at موقت ذخیره نمی‌کنیم؛ فقط در توضیحات اشاره می‌کنیم
                    paid_at = form.cleaned_data.get('paid_at')
                    if paid_at:
                        new_transaction.description = f"{new_transaction.description or ''}\nتاریخ انجام پرداخت: {paid_at}"
                        new_transaction.save()

                    messages.success(request, f'پرداخت {payment_amount:,} ریال با موفقیت ثبت شد.')
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
        invoice_form = InvoiceForm()
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
                    # ویرایش فاکتور
                    invoice_form.save()
                    
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


