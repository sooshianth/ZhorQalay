from django.shortcuts import render

# Create your views here.

def table_filter_demo(request):
    """
    نمایش صفحه نمونه برای فیلتر جداول
    """
    return render(request, 'table_filter/demo.html')
