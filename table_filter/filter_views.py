from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import QuerySet, Count
from django.shortcuts import render
from .utils import (
    TableFilterProcessor, ColumnTypeDetector, FilterConfigurationManager,
    UserFilterStateManager, get_model_from_table_name
)
from .models import TableFilterConfiguration, UserTableFilterState, TableFilterStats
import json


@login_required
@require_http_methods(["GET"])
def get_table_configuration(request, table_name):
    """دریافت تنظیمات فیلتر جدول"""
    try:
        config_manager = FilterConfigurationManager(table_name)
        configurations = config_manager.get_table_configuration()
        
        config_data = []
        for config in configurations:
            config_data.append({
                'column_id': config.column_id,
                'column_name': config.column_name,
                'column_type': config.column_type,
                'is_filterable': config.is_filterable,
                'is_sortable': config.is_sortable,
                'is_visible': config.is_visible,
                'column_order': config.column_order,
                'choices': config.choices_list if config.column_type == 'choice' else None,
            })
        
        return JsonResponse({
            'success': True,
            'configurations': config_data
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def apply_table_filter(request):
    """اعمال فیلتر روی جدول"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        filter_config = data.get('filter_config', {})
        sort_config = data.get('sort_config', {})
        page = data.get('page', 1)
        page_size = data.get('page_size', 50)
        save_state = data.get('save_state', True)
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        # دریافت مدل مربوطه
        model = get_model_from_table_name(table_name)
        if not model:
            return JsonResponse({
                'success': False,
                'error': 'مدل مربوط به جدول یافت نشد'
            }, status=404)
        
        # ایجاد queryset اولیه
        queryset = model.objects.all()
        
        # اعمال فیلتر
        processor = TableFilterProcessor(queryset, table_name)
        
        if filter_config:
            queryset = processor.apply_filters(filter_config)
        
        if sort_config:
            queryset = processor.apply_sorting(sort_config)
        
        # ذخیره وضعیت کاربر
        if save_state:
            state_manager = UserFilterStateManager(request.user, table_name)
            state_manager.save_filter_state(filter_config, sort_config)
        
        # ثبت آمار استفاده
        for column_id, filter_data in filter_config.items():
            if filter_data and filter_data.get('values'):
                for value in filter_data['values']:
                    TableFilterStats.record_usage(table_name, column_id, value, request.user)
        
        # صفحه‌بندی
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # تبدیل نتایج به JSON
        results = []
        for obj in page_obj:
            obj_data = {}
            for field in model._meta.fields:
                value = getattr(obj, field.name)
                if value is not None:
                    if hasattr(value, 'strftime'):  # تاریخ
                        obj_data[field.name] = value.strftime('%Y-%m-%d')
                    elif isinstance(value, bool):  # بولین
                        obj_data[field.name] = 'بله' if value else 'خیر'
                    else:
                        obj_data[field.name] = str(value)
                else:
                    obj_data[field.name] = ''
            
            obj_data['id'] = obj.id
            results.append(obj_data)
        
        return JsonResponse({
            'success': True,
            'results': results,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': page_size
            },
            'filter_applied': bool(filter_config),
            'sort_applied': bool(sort_config)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_column_values(request, table_name, column_id):
    """دریافت مقادیر منحصر به فرد یک ستون"""
    try:
        # دریافت مدل
        model = get_model_from_table_name(table_name)
        if not model:
            return JsonResponse({
                'success': False,
                'error': 'مدل مربوط به جدول یافت نشد'
            }, status=404)
        
        # پارامترهای فیلتر فعلی (برای نمایش مقادیر فیلتر شده)
        current_filters = request.GET.get('current_filters')
        if current_filters:
            try:
                current_filters = json.loads(current_filters)
                # حذف فیلتر ستون فعلی از فیلترهای موجود
                current_filters.pop(column_id, None)
            except:
                current_filters = {}
        else:
            current_filters = {}
        
        # ایجاد queryset
        queryset = model.objects.all()
        
        # اعمال فیلترهای فعلی (به جز ستون فعلی)
        if current_filters:
            processor = TableFilterProcessor(queryset, table_name)
            queryset = processor.apply_filters(current_filters)
        
        # دریافت مقادیر ستون
        processor = TableFilterProcessor(queryset, table_name)
        column_values = processor.get_column_values(column_id, limit=500)
        
        return JsonResponse({
            'success': True,
            'values': column_values,
            'total_count': len(column_values)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def save_user_filter_state(request):
    """ذخیره وضعیت فیلتر کاربر"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        filter_state = data.get('filter_state', {})
        sort_state = data.get('sort_state', {})
        column_visibility = data.get('column_visibility', {})
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        state_manager = UserFilterStateManager(request.user, table_name)
        state_manager.save_filter_state(filter_state, sort_state, column_visibility)
        
        return JsonResponse({
            'success': True,
            'message': 'وضعیت فیلتر ذخیره شد'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_user_filter_state(request, table_name):
    """دریافت وضعیت فیلتر کاربر"""
    try:
        state_manager = UserFilterStateManager(request.user, table_name)
        filter_state, sort_state, column_visibility = state_manager.get_filter_state()
        
        return JsonResponse({
            'success': True,
            'filter_state': filter_state,
            'sort_state': sort_state,
            'column_visibility': column_visibility
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def clear_user_filter_state(request, table_name):
    """پاک کردن وضعیت فیلتر کاربر"""
    try:
        state_manager = UserFilterStateManager(request.user, table_name)
        state_manager.clear_filter_state()
        
        return JsonResponse({
            'success': True,
            'message': 'وضعیت فیلتر پاک شد'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_column_configuration(request):
    """بروزرسانی تنظیمات ستون"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        column_id = data.get('column_id')
        updates = data.get('updates', {})
        
        if not all([table_name, column_id]):
            return JsonResponse({
                'success': False,
                'error': 'نام جدول و شناسه ستون الزامی است'
            }, status=400)
        
        # بروزرسانی تنظیمات
        config = TableFilterConfiguration.objects.get(
            table_name=table_name,
            column_id=column_id
        )
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.save()
        
        return JsonResponse({
            'success': True,
            'message': 'تنظیمات ستون بروزرسانی شد'
        })
    
    except TableFilterConfiguration.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'تنظیمات ستون یافت نشد'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def bulk_update_column_visibility(request):
    """بروزرسانی گروهی نمایش ستون‌ها"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        column_visibility = data.get('column_visibility', {})
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        config_manager = FilterConfigurationManager(table_name)
        
        for column_id, is_visible in column_visibility.items():
            config_manager.toggle_column_visibility(column_id, is_visible)
        
        return JsonResponse({
            'success': True,
            'message': 'نمایش ستون‌ها بروزرسانی شد'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_column_order(request):
    """بروزرسانی ترتیب ستون‌ها"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        column_orders = data.get('column_orders', {})
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        config_manager = FilterConfigurationManager(table_name)
        config_manager.update_column_order(column_orders)
        
        return JsonResponse({
            'success': True,
            'message': 'ترتیب ستون‌ها بروزرسانی شد'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_table_stats(request, table_name):
    """دریافت آمار جدول"""
    try:
        model = get_model_from_table_name(table_name)
        if not model:
            return JsonResponse({
                'success': False,
                'error': 'مدل مربوط به جدول یافت نشد'
            }, status=404)
        
        queryset = model.objects.all()
        processor = TableFilterProcessor(queryset, table_name)
        stats = processor.get_table_stats()
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def detect_column_type(request, table_name, column_id):
    """تشخیص نوع ستون"""
    try:
        model = get_model_from_table_name(table_name)
        if not model:
            return JsonResponse({
                'success': False,
                'error': 'مدل مربوط به جدول یافت نشد'
            }, status=404)
        
        # تشخیص نوع بر اساس مدل
        field_type = ColumnTypeDetector.detect_field_type(model, column_id)
        
        # در صورت نیاز، تشخیص بر اساس نمونه داده‌ها
        if field_type == 'text':
            try:
                sample_values = list(
                    model.objects.exclude(**{f'{column_id}__isnull': True})
                    .values_list(column_id, flat=True)[:10]
                )
                if sample_values:
                    field_type = ColumnTypeDetector.detect_by_sample_data(sample_values)
            except:
                pass
        
        return JsonResponse({
            'success': True,
            'column_type': field_type
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_filter_stats(request, table_name):
    """دریافت آمار استفاده از فیلترها"""
    try:
        # آمار استفاده کاربر فعلی
        user_stats = TableFilterStats.objects.filter(
            table_name=table_name,
            user=request.user
        ).order_by('-usage_count', '-last_used')[:20]
        
        # آمار عمومی محبوب‌ترین فیلترها
        popular_stats = TableFilterStats.objects.filter(
            table_name=table_name
        ).values('column_id', 'filter_value').annotate(
            total_usage=Count('usage_count')
        ).order_by('-total_usage')[:10]
        
        user_data = []
        for stat in user_stats:
            user_data.append({
                'column_id': stat.column_id,
                'filter_value': stat.filter_value,
                'usage_count': stat.usage_count,
                'last_used': stat.last_used.isoformat()
            })
        
        popular_data = []
        for stat in popular_stats:
            popular_data.append({
                'column_id': stat['column_id'],
                'filter_value': stat['filter_value'],
                'total_usage': stat['total_usage']
            })
        
        return JsonResponse({
            'success': True,
            'user_stats': user_data,
            'popular_stats': popular_data
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def setup_table_configuration(request):
    """تنظیم اولیه پیکربندی جدول"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        model_name = data.get('model_name')  # optional: app_label.model_name
        columns = data.get('columns', [])
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        # تلاش برای یافتن مدل
        model = None
        if model_name:
            model = get_model_from_table_name(model_name)
        else:
            model = get_model_from_table_name(table_name)
        
        config_manager = FilterConfigurationManager(table_name)
        
        created_configs = []
        for i, column_info in enumerate(columns):
            column_id = column_info.get('id')
            column_name = column_info.get('name', column_id)
            
            if not column_id:
                continue
            
            config = config_manager.get_or_create_column_config(
                column_id=column_id,
                column_name=column_name,
                model_class=model
            )
            
            # تنظیم ترتیب
            config.column_order = i
            config.save()
            
            created_configs.append({
                'column_id': config.column_id,
                'column_name': config.column_name,
                'column_type': config.column_type,
                'column_order': config.column_order
            })
        
        return JsonResponse({
            'success': True,
            'message': f'پیکربندی جدول {table_name} با موفقیت انجام شد',
            'configurations': created_configs
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def reset_column_order(request):
    """بازگشت به ترتیب پیش‌فرض ستون‌ها"""
    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        
        if not table_name:
            return JsonResponse({
                'success': False,
                'error': 'نام جدول الزامی است'
            }, status=400)
        
        # بازنشانی ترتیب ستون‌ها به حالت پیش‌فرض
        configs = TableFilterConfiguration.objects.filter(
            table_name=table_name
        ).order_by('id')  # یا هر ترتیب پیش‌فرض دیگری
        
        for i, config in enumerate(configs):
            config.column_order = i
            config.is_visible = True  # نمایش همه ستون‌ها
            config.save()
        
        return JsonResponse({
            'success': True,
            'message': 'ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# صفحات ساده
@login_required
def table_filter_demo(request):
    """صفحه دمو سیستم فیلتر جدول"""
    return render(request, 'table_filter/demo.html')


@login_required
def table_filter_documentation(request):
    """مستندات سیستم فیلتر جدول"""
    return render(request, 'table_filter/documentation.html')


# =================== PRESET MANAGEMENT ===================

@login_required
@require_http_methods(["GET"])
def get_filter_presets(request, table_name):
    """دریافت پیش‌تنظیمات فیلتر"""
    try:
        from .models import TableFilterPreset
        
        # پیش‌تنظیمات کاربر
        user_presets = TableFilterPreset.objects.filter(
            table_name=table_name,
            user=request.user
        ).order_by('name')
        
        # پیش‌تنظیمات عمومی
        public_presets = TableFilterPreset.objects.filter(
            table_name=table_name,
            is_public=True
        ).exclude(user=request.user).order_by('name')
        
        user_data = []
        for preset in user_presets:
            user_data.append({
                'id': preset.id,
                'name': preset.name,
                'description': preset.description,
                'is_default': preset.is_default,
                'filter_config': preset.filter_config,
                'created_at': preset.created_at.isoformat()
            })
        
        public_data = []
        for preset in public_presets:
            public_data.append({
                'id': preset.id,
                'name': preset.name,
                'description': preset.description,
                'user': preset.user.username,
                'filter_config': preset.filter_config,
                'created_at': preset.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'user_presets': user_data,
            'public_presets': public_data
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def save_filter_preset(request):
    """ذخیره پیش‌تنظیم فیلتر"""
    try:
        from .models import TableFilterPreset
        
        data = json.loads(request.body)
        table_name = data.get('table_name')
        name = data.get('name')
        description = data.get('description', '')
        filter_config = data.get('filter_config', {})
        is_public = data.get('is_public', False)
        is_default = data.get('is_default', False)
        
        if not all([table_name, name]):
            return JsonResponse({
                'success': False,
                'error': 'نام جدول و نام پیش‌تنظیم الزامی است'
            }, status=400)
        
        # بررسی تکراری نبودن نام
        if TableFilterPreset.objects.filter(
            table_name=table_name,
            user=request.user,
            name=name
        ).exists():
            return JsonResponse({
                'success': False,
                'error': 'پیش‌تنظیمی با این نام قبلاً ذخیره شده است'
            }, status=400)
        
        # اگر این پیش‌تنظیم پیش‌فرض شود، بقیه را غیرپیش‌فرض کن
        if is_default:
            TableFilterPreset.objects.filter(
                table_name=table_name,
                user=request.user,
                is_default=True
            ).update(is_default=False)
        
        preset = TableFilterPreset.objects.create(
            table_name=table_name,
            user=request.user,
            name=name,
            description=description,
            filter_config=filter_config,
            is_public=is_public,
            is_default=is_default
        )
        
        return JsonResponse({
            'success': True,
            'message': 'پیش‌تنظیم ذخیره شد',
            'preset_id': preset.id
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_filter_preset(request, preset_id):
    """حذف پیش‌تنظیم فیلتر"""
    try:
        from .models import TableFilterPreset
        
        preset = TableFilterPreset.objects.get(
            id=preset_id,
            user=request.user
        )
        preset.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'پیش‌تنظیم حذف شد'
        })
    
    except TableFilterPreset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'پیش‌تنظیم یافت نشد'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def apply_filter_preset(request, preset_id):
    """اعمال پیش‌تنظیم فیلتر"""
    try:
        from .models import TableFilterPreset
        
        preset = TableFilterPreset.objects.get(
            id=preset_id
        )
        
        # بررسی دسترسی (کاربر خودش یا عمومی)
        if preset.user != request.user and not preset.is_public:
            return JsonResponse({
                'success': False,
                'error': 'شما مجوز دسترسی به این پیش‌تنظیم را ندارید'
            }, status=403)
        
        # اعمال پیش‌تنظیم
        state_manager = UserFilterStateManager(request.user, preset.table_name)
        state_manager.save_filter_state(preset.filter_config)
        
        return JsonResponse({
            'success': True,
            'message': 'پیش‌تنظیم اعمال شد',
            'filter_config': preset.filter_config
        })
    
    except TableFilterPreset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'پیش‌تنظیم یافت نشد'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500) 