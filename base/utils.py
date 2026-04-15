import json
import hashlib
import calendar
from datetime import datetime
from datetime import timedelta

from django.core.cache import cache
from django.utils.timezone import now
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

from base.models import BaseModel

from apps.incident.models import (
    Incident, IncidentType
)


def parse_custom_date(date_str):
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').date()
    except Exception:
        return None


# একটাই স্থায়ী প্যালেট (প্রয়োজনে বাড়াতে/বদলাতে পারেন)
STABLE_COLOR_PALETTE = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
    '#FF9F40', '#00A6A6', '#FF6B6B', '#C9CBCF', '#845EC2',
    '#F67280', '#6C5B7B', '#355C7D', '#3EC1D3', '#FFD166',
    '#2a9d8f', '#e76f51', '#264653', '#8ab17d', '#6a4c93',
]

CACHE_KEY_COLOR_MAP = "incident_type_color_map_v1"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 1 day


def _hash_color(label: str) -> str:
    """প্যালেটে না থাকলে নির্ভরযোগ্য ফলোব্যাক: লেবেল-হ্যাশ থেকে হেক্স কালার।"""
    if not label:
        return '#999999'
    h = hashlib.md5(label.encode('utf-8')).hexdigest()
    return f"#{h[:6]}"


def get_incident_type_color_map(refresh: bool = False) -> dict:
    """
    IncidentType -> color স্টেবল ম্যাপ।
    - id ASC অর্ডারে কালার অ্যাসাইন (যাতে যোগ হওয়া নতুন টাইপ শেষে যায়)
    - cache করা থাকে; চাইলে refresh=True দিলে পুনর্নির্মাণ
    """
    color_map = cache.get(CACHE_KEY_COLOR_MAP)
    if refresh or not color_map:
        color_map = {}
        # name_bn ইউনিক ধরে নিচ্ছি; না হলে name_en/slug ব্যবহার করতে পারেন
        type_names = list(
            IncidentType.objects.order_by('id').values_list('name_bn', flat=True)
        )
        for idx, name in enumerate(type_names):
            color_map[name] = STABLE_COLOR_PALETTE[idx % len(STABLE_COLOR_PALETTE)]
        cache.set(CACHE_KEY_COLOR_MAP, color_map, CACHE_TTL_SECONDS)
    return color_map


def color_for_label(label: str, cmap: dict) -> str:
    """প্রধান সহায়ক: আগে cmap, না থাকলে হ্যাশ-কালার।"""
    return cmap.get(label) or _hash_color(label or "")


def build_incident_dashboard_context(*, user=None, include_geo_counts=False):
    """
    Reusable builder for donut + line chart data.
    - user=None  => whole system (HomeView)
    - user=<User> => user scoped (TerminalDashboardView)
    """
    q = Q()
    if user is not None:
        q &= Q(posted_by=user)

    # ---------- Donut ----------
    published_incident_total = Incident.objects.filter(
        q,
        status=BaseModel.StatusChoices.PUBLISHED
    ).count()

    it_qs = (
        Incident.objects
        .filter(
            q,
            status=BaseModel.StatusChoices.PUBLISHED
        )
        .values('incident_type__name_bn')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    cmap = get_incident_type_color_map()
    donut_data, donut_colors, donut_legend_items = [], [], []

    for row in it_qs:
        label = row['incident_type__name_bn']
        if not label:
            continue
        color = color_for_label(label, cmap)
        donut_data.append({'label': label, 'value': row['count']})
        donut_colors.append(color)
        donut_legend_items.append({
            'label': label,
            'value': row['count'],
            'color': color,
            'percentage': round((row['count'] / published_incident_total) * 100) if published_incident_total else 0,
        })

    # ---------- Line (last 12 months per type) ----------
    today = now()
    last_year = today - timedelta(days=365)

    line_qs = (
        Incident.objects
        .filter(q, date__gte=last_year, status=BaseModel.StatusChoices.PUBLISHED)
        .annotate(month=TruncMonth('date'))
        .values('month', 'incident_type__name_bn')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    months_found = {entry['month'].strftime('%B') for entry in line_qs}
    month_order = list(calendar.month_name)[1:]
    all_months = [m for m in month_order if m in months_found] or [today.strftime('%B')]

    # group by type
    data_by_type = {}
    for entry in line_qs:
        it_name = entry['incident_type__name_bn']
        mon = entry['month'].strftime('%B')
        total = entry['total']
        data_by_type.setdefault(it_name, {})[mon] = total

    # datasets (রঙ নেওয়া হবে স্টেবল cmap থেকে)
    datasets = []
    for it_name, month_map in data_by_type.items():
        border = color_for_label(it_name, cmap)
        datasets.append({
            'label': it_name or 'Uncategorized',
            'data': [month_map.get(m, 0) for m in all_months],
            'fill': False,
            'borderColor': border,
            'tension': 0.3,
        })

    ctx = {
        'donut_chart_data': donut_data,
        'donut_chart_colors': donut_colors,
        'donut_legend_items': donut_legend_items,
        'chart_labels': all_months,          # return Python list (not JSON string)
        'chart_datasets': datasets,         # list of dicts
        'published_incident_total': published_incident_total,
    }

    if include_geo_counts:
        ctx.update({
            'incident_of_bd': Incident.objects.filter(country='BD').count(),
            'incident_of_in': Incident.objects.filter(country='IN').count(),
            'incident_of_mm': Incident.objects.filter(country='MM').count(),
        })

    return ctx
