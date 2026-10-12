"""Zahlen im Schweizer Format: 12'345.50"""
from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def chf(wert, stellen=2):
    if wert is None or wert == "":
        return "–"
    return f"{Decimal(wert):,.{int(stellen)}f}".replace(",", "'")


@register.filter
def zahl(wert):
    if wert is None or wert == "":
        return "–"
    return f"{int(wert):,}".replace(",", "'")


@register.simple_tag(takes_context=True)
def url_mit(context, **aenderungen):
    """Aktuelle Query-Parameter übernehmen und einzelne ersetzen (None entfernt)."""
    params = context["request"].GET.copy()
    for k, v in aenderungen.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = v
    return "?" + params.urlencode()
