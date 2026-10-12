"""Abfrageoberfläche: Übersicht, Medienliste mit Suche/Filtern, Detailseite."""
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from . import auswertung
from .models import Bibliothek, Entscheid, Kennzahl, Medientyp, Nutzung, Objekt

PRO_SEITE = 50
SORTIERUNGEN = {
    "titel": lambda o: o.titel.lower(),
    "typ": lambda o: o.medientyp.name,
    "kosten": lambda o: o.kosten_jahr,
    "nutzung": lambda o: o.nutzung_jahr,
    "cpu": lambda o: o.cpu_jahr,
}


def _int(wert):
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


@login_required
def uebersicht(request):
    jahre = auswertung.verfuegbare_jahre()
    jahr = _int(request.GET.get("jahr")) or auswertung.standardjahr()
    objekte = auswertung.zeilen(
        Objekt.objects.select_related("medientyp").prefetch_related("bibliotheken"), jahr
    )
    gesamt = auswertung.summen(objekte)

    pro_bibliothek = []
    for bib in Bibliothek.objects.all():
        teil = [o for o in objekte if bib in o.bibliotheken.all()]
        if teil:
            pro_bibliothek.append({"bibliothek": bib, **auswertung.summen(teil)})

    cpu_grenze = 50
    ueber_grenze = sum(1 for o in objekte if o.cpu_jahr is not None and o.cpu_jahr >= cpu_grenze)
    teuerste = sorted((o for o in objekte if o.cpu_jahr is not None), key=lambda o: o.cpu_jahr, reverse=True)[:10]

    # Entwicklung über die Jahre (für das Balkendiagramm)
    verlauf = []
    for j in sorted(jahre):
        s = auswertung.summen(auswertung.zeilen(Objekt.objects.all(), j))
        verlauf.append({"jahr": j, **s})
    max_kosten = max((v["kosten"] for v in verlauf), default=0) or 1
    for v in verlauf:
        v["prozent"] = int(v["kosten"] / max_kosten * 100)

    return render(request, "katalog/uebersicht.html", {
        "jahr": jahr, "jahre": jahre, "gesamt": gesamt, "pro_bibliothek": pro_bibliothek,
        "teuerste": teuerste, "verlauf": verlauf, "cpu_grenze": cpu_grenze, "ueber_grenze": ueber_grenze,
        "entscheide": Entscheid.objects.select_related("objekt")[:8],
        "anzahl_medien": Objekt.objects.count(),
    })


@login_required
def medien_liste(request):
    p = request.GET
    q = p.get("q", "").strip()
    jahr = _int(p.get("jahr")) or auswertung.standardjahr()
    kennzahl = p.get("kennzahl") or "TIR"
    bibliothek = Bibliothek.objects.filter(pk=_int(p.get("bibliothek"))).first()

    qs = Objekt.objects.select_related("medientyp", "verlag").prefetch_related("bibliotheken")
    if q:
        qs = qs.filter(
            Q(titel__icontains=q) | Q(issn_print__icontains=q) | Q(issn_online__icontains=q)
            | Q(verlag__name__icontains=q) | Q(fachgebiet__icontains=q)
        )
    if bibliothek:
        qs = qs.filter(bibliotheken=bibliothek)
    if _int(p.get("medientyp")):
        qs = qs.filter(medientyp_id=_int(p.get("medientyp")))
    if p.get("status"):
        qs = qs.filter(status=p["status"])

    objekte = auswertung.zeilen(qs.distinct(), jahr, kennzahl, bibliothek)

    try:
        cpu_min = Decimal(p.get("cpu_min", "").replace(",", ".")) if p.get("cpu_min") else None
    except InvalidOperation:
        cpu_min = None
    if cpu_min is not None:
        objekte = [o for o in objekte if o.cpu_jahr is not None and o.cpu_jahr >= cpu_min]

    sort = p.get("sort", "titel")
    richtung = p.get("dir", "desc" if sort in ("kosten", "nutzung", "cpu") else "asc")
    if sort in SORTIERUNGEN:
        key = SORTIERUNGEN[sort]
        mit = [o for o in objekte if key(o) is not None]
        ohne = [o for o in objekte if key(o) is None]
        objekte = sorted(mit, key=key, reverse=(richtung == "desc")) + ohne

    if p.get("format") == "csv":
        return _csv(objekte, jahr, kennzahl)

    vorschlag = None
    if q and not objekte:
        titel = list(Objekt.objects.values_list("titel", flat=True))
        treffer = get_close_matches(q, titel, n=1, cutoff=0.6)
        vorschlag = treffer[0] if treffer else None

    seite = Paginator(objekte, PRO_SEITE).get_page(p.get("seite"))
    return render(request, "katalog/medien_liste.html", {
        "seite": seite, "anzahl": len(objekte), "q": q, "jahr": jahr, "kennzahl": kennzahl,
        "sort": sort, "richtung": richtung, "cpu_min": p.get("cpu_min", ""), "vorschlag": vorschlag,
        "jahre": auswertung.verfuegbare_jahre(), "bibliotheken": Bibliothek.objects.all(),
        "medientypen": Medientyp.objects.all(), "kennzahlen": Kennzahl.objects.all(),
        "status_wahl": Objekt.Status.choices,
        "filter_aktiv": any(p.get(k) for k in ("q", "bibliothek", "medientyp", "status", "cpu_min")),
    })


def _csv(objekte, jahr, kennzahl):
    antwort = HttpResponse(content_type="text/csv; charset=utf-8")
    antwort["Content-Disposition"] = f'attachment; filename="e-medien-{jahr}.csv"'
    antwort.write("﻿")  # damit Excel Umlaute richtig liest
    w = csv.writer(antwort, delimiter=";")
    w.writerow(["Titel", "Medientyp", "Verlag", "Bibliotheken", "Status", "ISSN",
                f"Kosten CHF {jahr}", f"Nutzung {kennzahl} {jahr}", f"CPU {kennzahl} {jahr}"])
    for o in objekte:
        w.writerow([
            o.titel, o.medientyp.name, o.verlag or "", ", ".join(b.kuerzel for b in o.bibliotheken.all()),
            o.get_status_display(), o.issn_online or o.issn_print,
            o.kosten_jahr if o.kosten_jahr is not None else "", o.nutzung_jahr or "", o.cpu_jahr or "",
        ])
    return antwort


@login_required
def medium_detail(request, pk):
    objekt = get_object_or_404(
        Objekt.objects.select_related("medientyp", "verlag", "lieferant", "paket").prefetch_related(
            "kosten", "nutzung__kennzahl", "objektbibliothek_set__bibliothek",
            "verwaltung__bibliothek", "entscheide", "notizen", "titel_im_paket",
        ),
        pk=pk,
    )
    codes = set(Nutzung.objects.filter(Q(objekt=objekt) | Q(objekt__paket=objekt)).values_list("kennzahl__code", flat=True))
    codes = sorted(codes, key=lambda c: (c != "TIR", c)) or ["TIR"]
    verwaltung = defaultdict(list)
    for v in objekt.verwaltung.all():
        verwaltung[v.jahr].append(v)
    return render(request, "katalog/medium_detail.html", {
        "o": objekt, "codes": codes, "jahreswerte": objekt.jahreswerte(codes),
        "verwaltung": sorted(verwaltung.items(), reverse=True),
        "darf_bearbeiten": request.user.has_perm("katalog.change_objekt"),
    })
