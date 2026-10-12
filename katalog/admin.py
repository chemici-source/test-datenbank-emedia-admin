"""Verwaltungsteil: Bearbeiten und Erfassen über die Django-Administration."""
from django.contrib import admin

from .models import (
    Bibliothek, Entscheid, Kennzahl, Kosten, Medientyp, Notiz, Nutzung, Objekt,
    ObjektBibliothek, ObjektQuelle, Organisation, Verwaltung,
)

admin.site.site_header = "E-Medien MNW – Verwaltung"
admin.site.site_title = "E-Medien MNW"
admin.site.index_title = "Daten bearbeiten"
admin.site.site_url = "/"


class ObjektBibliothekInline(admin.TabularInline):
    model = ObjektBibliothek
    extra = 0


class VerwaltungInline(admin.TabularInline):
    model = Verwaltung
    extra = 0
    fields = ["jahr", "bibliothek", "erwerbungsart", "etat_code", "bestellposten_alma", "abo_nr", "laufzeit_bis"]


class KostenInline(admin.TabularInline):
    model = Kosten
    extra = 0
    fields = ["jahr", "bibliothek", "art", "betrag_chf", "betrag_fw", "waehrung", "rechnungsdatum", "kategorie"]


class NutzungInline(admin.TabularInline):
    model = Nutzung
    extra = 0
    fields = ["jahr", "kennzahl", "wert", "quelle"]


class EntscheidInline(admin.StackedInline):
    model = Entscheid
    extra = 0
    fields = [("datum", "entscheid", "person"), "begruendung"]


class NotizInline(admin.StackedInline):
    model = Notiz
    extra = 0
    fields = [("typ", "jahr"), "text"]


class ObjektQuelleInline(admin.TabularInline):
    model = ObjektQuelle
    extra = 0
    classes = ["collapse"]


@admin.register(Objekt)
class ObjektAdmin(admin.ModelAdmin):
    list_display = ["titel", "medientyp", "verlag", "status", "bibliotheken_kurz", "geaendert"]
    list_filter = ["medientyp", "status", "bibliotheken", "verlag"]
    search_fields = ["titel", "issn_print", "issn_online", "verlag__name", "fachgebiet"]
    autocomplete_fields = ["verlag", "lieferant", "paket"]
    list_per_page = 50
    save_on_top = True
    fieldsets = [
        (None, {"fields": ["titel", ("medientyp", "status"), "fachgebiet"]}),
        ("Identifikation", {"fields": [("issn_print", "issn_online")]}),
        ("Bezug", {"fields": [("verlag", "lieferant"), "paket"]}),
    ]
    inlines = [
        ObjektBibliothekInline, VerwaltungInline, KostenInline, NutzungInline,
        EntscheidInline, NotizInline, ObjektQuelleInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("medientyp", "verlag").prefetch_related("bibliotheken")

    @admin.display(description="Bibliotheken")
    def bibliotheken_kurz(self, obj):
        return ", ".join(b.kuerzel for b in obj.bibliotheken.all())

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, Notiz) and inst.erstellt_von_id is None:
                inst.erstellt_von = request.user
            inst.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["name", "ist_verlag", "ist_lieferant"]
    list_filter = ["ist_verlag", "ist_lieferant"]
    search_fields = ["name"]


@admin.register(Bibliothek)
class BibliothekAdmin(admin.ModelAdmin):
    list_display = ["name", "kuerzel"]


@admin.register(Medientyp)
class MedientypAdmin(admin.ModelAdmin):
    list_display = ["name"]


@admin.register(Kennzahl)
class KennzahlAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]


@admin.register(Kosten)
class KostenAdmin(admin.ModelAdmin):
    list_display = ["objekt", "jahr", "bibliothek", "art", "betrag_chf", "kategorie"]
    list_filter = ["jahr", "bibliothek", "art", "kategorie"]
    search_fields = ["objekt__titel"]
    autocomplete_fields = ["objekt"]


@admin.register(Nutzung)
class NutzungAdmin(admin.ModelAdmin):
    list_display = ["objekt", "jahr", "kennzahl", "wert"]
    list_filter = ["jahr", "kennzahl"]
    search_fields = ["objekt__titel"]
    autocomplete_fields = ["objekt"]


@admin.register(Entscheid)
class EntscheidAdmin(admin.ModelAdmin):
    list_display = ["objekt", "datum", "entscheid", "person"]
    list_filter = ["entscheid"]
    search_fields = ["objekt__titel", "begruendung"]
    autocomplete_fields = ["objekt"]
