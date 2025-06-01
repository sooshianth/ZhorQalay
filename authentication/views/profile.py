from django.shortcuts import render

def profile_view(request):
    return render(request, 'authentication/profile.html', {'user': request.user})

