from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def dict_get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return None


@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
