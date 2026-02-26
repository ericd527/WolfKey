"""
Grade services for calculating and retrieving user grades.
Supports grade calculation, GPA computation, and grade breakdown analysis.
"""
from django.http import JsonResponse
from forum.models import User, GradebookSnapshot
from django.db.models import Q, F, Value, IntegerField, Case, When, Avg, Count
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def get_user_grades(user):
    """
    Fetch the most recent grade snapshots for a user.
    Returns the latest GradebookSnapshot entries organized by marking period.
    """
    if not user.is_authenticated:
        return {}
    
    try:
        # Get the most recent snapshots for each marking period/section combination
        latest_snapshots = GradebookSnapshot.objects.filter(
            user=user
        ).order_by('-timestamp')[:50]  # Get recent snapshots
        
        # Organize by marking period
        grades_by_period = {}
        for snapshot in latest_snapshots:
            mp_id = snapshot.marking_period_id
            if mp_id not in grades_by_period:
                grades_by_period[mp_id] = {
                    'marking_period_id': mp_id,
                    'timestamp': snapshot.timestamp.isoformat(),
                    'courses': []
                }
            
            # Extract course data from json_data
            if isinstance(snapshot.json_data, dict):
                grades_by_period[mp_id]['courses'].append({
                    'section_id': snapshot.section_id,
                    'data': snapshot.json_data
                })
        
        return grades_by_period
    except Exception as e:
        logger.error(f"Error fetching grades for user {user.id}: {str(e)}")
        return {}


def calculate_user_gpa(user):
    """
    Calculate weighted GPA from the most recent grade snapshots.
    Returns overall GPA and per-course grades if available.
    """
    if not user.is_authenticated:
        return None
    
    try:
        grades = get_user_grades(user)
        
        if not grades:
            return None
        
        # Get the most recent marking period
        most_recent = max(grades.values(), key=lambda x: x['timestamp'])
        
        total_grade = 0
        course_count = 0
        courses = []
        
        # Parse grades from json_data
        for course in most_recent['courses']:
            data = course.get('data', {})
            
            if isinstance(data, dict):
                # Try to extract grade value (varies by data structure)
                grade = data.get('grade') or data.get('percent') or data.get('score')
                
                if grade is not None:
                    try:
                        grade_val = float(grade) if isinstance(grade, str) else grade
                        courses.append({
                            'section_id': course['section_id'],
                            'grade': grade_val,
                            'data': data
                        })
                        total_grade += grade_val
                        course_count += 1
                    except (ValueError, TypeError):
                        pass
        
        gpa = total_grade / course_count if course_count > 0 else 0
        
        return {
            'gpa': round(gpa, 2),
            'course_count': course_count,
            'courses': courses,
            'marking_period': most_recent['marking_period_id'],
            'timestamp': most_recent['timestamp']
        }
    except Exception as e:
        logger.error(f"Error calculating GPA for user {user.id}: {str(e)}")
        return None


def get_grade_statistics(users):
    """
    Get grade statistics across multiple users for comparison.
    Useful for showing class averages or peer comparisons.
    """
    stats = {
        'average_gpa': 0,
        'highest_gpa': 0,
        'lowest_gpa': float('inf'),
        'user_grades': []
    }
    
    user_gpas = []
    
    for user in users:
        gpa_data = calculate_user_gpa(user)
        if gpa_data:
            user_gpas.append(gpa_data['gpa'])
            stats['user_grades'].append({
                'user_id': user.id,
                'username': user.username,
                'full_name': user.get_full_name(),
                'gpa': gpa_data['gpa'],
                'course_count': gpa_data['course_count']
            })
    
    if user_gpas:
        stats['average_gpa'] = round(sum(user_gpas) / len(user_gpas), 2)
        stats['highest_gpa'] = max(user_gpas)
        stats['lowest_gpa'] = min(user_gpas)
    
    return stats


def search_users_by_grade_range(min_gpa=None, max_gpa=None, limit=10):
    """
    Find users within a specific GPA range.
    """
    users_in_range = []
    
    try:
        # Get all users with grades
        users_with_grades = User.objects.filter(
            gradebook_snapshots__isnull=False
        ).distinct()
        
        for user in users_with_grades[:100]:  # Limit iteration
            gpa_data = calculate_user_gpa(user)
            if gpa_data:
                gpa = gpa_data['gpa']
                
                if min_gpa and gpa < min_gpa:
                    continue
                if max_gpa and gpa > max_gpa:
                    continue
                
                users_in_range.append({
                    'user_id': user.id,
                    'username': user.username,
                    'full_name': user.get_full_name(),
                    'gpa': gpa
                })
                
                if len(users_in_range) >= limit:
                    break
        
        return users_in_range
    except Exception as e:
        logger.error(f"Error searching users by grade range: {str(e)}")
        return []


def get_grade_trend(user, limit=10):
    """
    Get grade trend over time for a specific user.
    Shows how grades have changed across marking periods.
    """
    if not user.is_authenticated:
        return []
    
    try:
        snapshots = GradebookSnapshot.objects.filter(
            user=user
        ).order_by('timestamp')[:limit]
        
        trend = []
        for snapshot in snapshots:
            if isinstance(snapshot.json_data, dict):
                grades = []
                if 'grade' in snapshot.json_data:
                    grades.append(snapshot.json_data['grade'])
                
                trend.append({
                    'marking_period': snapshot.marking_period_id,
                    'timestamp': snapshot.timestamp.isoformat(),
                    'data': snapshot.json_data,
                    'average_grade': sum([float(g) for g in grades if isinstance(g, (int, float, str))]) / len(grades) if grades else 0
                })
        
        return trend
    except Exception as e:
        logger.error(f"Error fetching grade trend for user {user.id}: {str(e)}")
        return []
