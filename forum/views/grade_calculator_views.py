"""
Grade calculator views for comparing and analyzing student grades.
Mirrors the structure of course_comparer_views.py for consistency.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from forum.services.grade_services import (
    get_user_grades,
    calculate_user_gpa,
    get_grade_statistics
)


@login_required
@require_http_methods(["GET"])
def grade_calculator(request):
    """Display the grade calculator page"""
    return render(request, 'forum/grade_calculator.html')


@login_required
@require_http_methods(["GET"])
def get_user_grades_api(request, user_id):
    """
    API endpoint to fetch grades for a specific user.
    Returns grade data organized by marking period.
    """
    from django.shortcuts import get_object_or_404
    from forum.models import User, UserProfile
    
    try:
        user = get_object_or_404(User, id=user_id)
        user_profile = get_object_or_404(UserProfile, user=user)
        
        # Check if user allows grade sharing
        if not user_profile.allow_schedule_comparison:
            return JsonResponse({
                'error': 'This user has not enabled grade sharing'
            }, status=403)
        
        # Fetch grades and GPA
        grades = get_user_grades(user)
        gpa_data = calculate_user_gpa(user)
        
        response_data = {
            'user_id': user.id,
            'username': user.username,
            'full_name': user.get_full_name(),
            'profile_picture_url': user.userprofile.profile_picture.url if user.userprofile.profile_picture else None,
            'grades': grades,
            'gpa': gpa_data
        }
        
        return JsonResponse(response_data, status=200)
    
    except Exception as e:
        return JsonResponse({
            'error': 'User or grades not found',
            'details': str(e)
        }, status=404)


@login_required
@require_http_methods(["POST"])
def compare_grades_api(request):
    """
    API endpoint to compare grades across multiple users.
    Accepts a list of user IDs and returns comparative statistics.
    """
    try:
        data = json.loads(request.body)
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return JsonResponse({'error': 'No user IDs provided'}, status=400)
        
        from forum.models import User
        users = User.objects.filter(id__in=user_ids)
        
        if not users.exists():
            return JsonResponse({'error': 'No valid users found'}, status=404)
        
        # Get statistics
        stats = get_grade_statistics(users)
        
        return JsonResponse({
            'success': True,
            'statistics': stats
        }, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'error': 'Error comparing grades',
            'details': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def grade_trend_api(request, user_id):
    """
    API endpoint to fetch grade trend over time for a user.
    Shows how grades have changed across marking periods.
    """
    from django.shortcuts import get_object_or_404
    from forum.models import User
    from forum.services.grade_services import get_grade_trend
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Fetch grade trend
        trend = get_grade_trend(user, limit=20)
        
        return JsonResponse({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.get_full_name(),
            'trend': trend
        }, status=200)
    
    except Exception as e:
        return JsonResponse({
            'error': 'Grade trend not found',
            'details': str(e)
        }, status=404)
