from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.contrib import messages
from core.forms.forms import SalesAgentLoginForm

def sales_agent_login_view(request):
    if request.user.is_authenticated:
        return redirect('sales_agent_profile')

    # Check if we're in the verification step
    verification_step = 'phone_number' in request.session and request.session.get('phone_number')

    if request.method == "POST":
        form = SalesAgentLoginForm(data=request.POST, verification_step=verification_step)
        if form.is_valid():
            phone_number = form.cleaned_data.get('phone_number')
            verification_code = form.cleaned_data.get('verification_code')
            
            # If we have a verification code, attempt to verify OTP
            if verification_code:
                if form.verify_otp(request):
                    # Clear session data after successful login
                    if 'phone_number' in request.session:
                        del request.session['phone_number']
                    return redirect('sales_agent_profile')
                else:
                    messages.error(request, "کد تایید اشتباه است. لطفا مجددا تلاش کنید.")
            # Otherwise, send an OTP
            else:
                try:
                    form.send_otp()
                    # Store partially filled form data in session for the next step
                    request.session['phone_number'] = phone_number
                    messages.success(request, "کد تایید به شماره موبایل شما ارسال شد.")
                    # Set verification_step to True to show the verification code field
                    verification_step = True
                    # Return immediately with the new step
                    return render(request, "sales_agent_login.html", {
                        'form': SalesAgentLoginForm(initial={'phone_number': phone_number}, verification_step=True),
                        'verification_step': True
                    })
                except Exception as e:
                    messages.error(request, str(e))
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        # Pre-fill form with saved phone number if available
        initial_data = {}
        if 'phone_number' in request.session:
            initial_data['phone_number'] = request.session.get('phone_number')
        form = SalesAgentLoginForm(initial=initial_data, verification_step=verification_step)

    return render(request, "sales_agent_login.html", {
        'form': form,
        'verification_step': verification_step
    })