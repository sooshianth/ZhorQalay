from django.shortcuts import render

def home_view(request):
    context = {
        'title': 'Home Page',
        'message': 'Welcome to the Home Page!'
    }
    return render(request, 'home.html', context)