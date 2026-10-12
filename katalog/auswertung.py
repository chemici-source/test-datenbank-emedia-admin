"""Berechnung von Kosten, Nutzung und CPU über viele Medien auf einmal.

Bewusst in Python statt in SQL: Die Datenmenge (wenige tausend Medien) ist klein,
und so verhält sich die Berechnung auf SQLite, PostgreSQL und MySQL identisch.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Max

from .models import Kosten, Nutzung, cpu


def verfuegbare_jahre():
    jahre = set(Kosten.objects.values_list("jahr", flat=True).distinct())
    jahre |= set(Nutzung.objects.values_list("jahr", flat=True).distinct())
    return sorted(jahre, reverse=True)


def standardjahr():
    """Letztes Jahr, für das Kosten erfasst sind."""
    return Kosten.objects.aggregate(j=Max("jahr"))["j"] or Nutzung.objects.aggregate(j=Max("jahr"))["j"]


def kosten_nach_objekt(objekt_ids, jahr, bibliothek=None):
    qs = Kosten.objects.filter(objekt_id__in=objekt_ids, jahr=jahr, betrag_chf__isnull=False)
    if bibliothek:
        qs = qs.filter(bibliothek=bibliothek)
    summe = defaultdict(Decimal)
    for objekt_id, art, betrag in qs.values_list("objekt_id", "art", "betrag_chf"):
        summe[objekt_id] += -betrag if art == Kosten.Art.GUTSCHRIFT else betrag
    return summe


def nutzung_nach_objekt(objekt_ids, jahr, kennzahl):
    """Nutzung pro Medium. Ein Paket ohne eigene Zahlen erhält die Summe seiner Titel."""
    eigene = dict(
        Nutzung.objects.filter(objekt_id__in=objekt_ids, jahr=jahr, kennzahl__code=kennzahl)
        .values_list("objekt_id", "wert")
    )
    summe_titel = defaultdict(int)
    for paket_id, wert in Nutzung.objects.filter(
        objekt__paket_id__in=objekt_ids, jahr=jahr, kennzahl__code=kennzahl
    ).values_list("objekt__paket_id", "wert"):
        summe_titel[paket_id] += wert
    return {**summe_titel, **eigene}


def zeilen(objekte, jahr, kennzahl="TIR", bibliothek=None):
    """Hängt jedem Objekt .kosten_jahr, .nutzung_jahr und .cpu_jahr an."""
    objekte = list(objekte)
    ids = [o.pk for o in objekte]
    kosten = kosten_nach_objekt(ids, jahr, bibliothek)
    nutzung = nutzung_nach_objekt(ids, jahr, kennzahl)
    for o in objekte:
        o.kosten_jahr = kosten.get(o.pk)
        o.nutzung_jahr = nutzung.get(o.pk)
        o.cpu_jahr = cpu(o.kosten_jahr, o.nutzung_jahr)
    return objekte


def summen(objekte):
    """Gesamtkosten, Gesamtnutzung und CPU über alle Medien mit beiden Werten."""
    kosten = sum((o.kosten_jahr for o in objekte if o.kosten_jahr is not None), Decimal(0))
    nutzung = sum(o.nutzung_jahr for o in objekte if o.nutzung_jahr)
    beide = [o for o in objekte if o.kosten_jahr is not None and o.nutzung_jahr]
    cpu_gesamt = cpu(sum((o.kosten_jahr for o in beide), Decimal(0)), sum(o.nutzung_jahr for o in beide))
    return {"kosten": kosten, "nutzung": nutzung, "cpu": cpu_gesamt, "anzahl": len(objekte)}
