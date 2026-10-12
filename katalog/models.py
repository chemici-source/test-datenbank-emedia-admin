"""Datenmodell E-Medien MNW.

Kern ist `Objekt` (ein Datensatz pro Medium). Nutzung und Kosten sind getrennte,
typisierte Tabellen; die CPU (Cost per Use) wird daraus berechnet und nie gespeichert.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

ISSN_VALIDATOR = RegexValidator(r"^\d{4}-\d{3}[\dX]$", "ISSN im Format 1234-567X angeben.")


class Bibliothek(models.Model):
    kuerzel = models.CharField("Kürzel", max_length=10, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Bibliothek"
        verbose_name_plural = "Bibliotheken"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.kuerzel})"


class Medientyp(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name = "Medientyp"
        verbose_name_plural = "Medientypen"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Organisation(models.Model):
    """Verlag, Lieferant oder Konsortium."""

    name = models.CharField(max_length=150, unique=True)
    ist_verlag = models.BooleanField("Verlag", default=False)
    ist_lieferant = models.BooleanField("Lieferant", default=False)

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisationen (Verlage, Lieferanten)"
        ordering = ["name"]

    def __str__(self):
        return self.name


def cpu(kosten, nutzung):
    if kosten is None or not nutzung:
        return None
    return (Decimal(kosten) / Decimal(nutzung)).quantize(Decimal("0.01"))


class Objekt(models.Model):
    class Status(models.TextChoices):
        AKTIV = "aktiv", "aktiv"
        PRUEFUNG = "pruefung", "in Prüfung"
        ABBESTELLT = "abbestellt", "abbestellt"
        OA = "oa", "Open Access / frei"

    titel = models.CharField(max_length=300)
    medientyp = models.ForeignKey(Medientyp, on_delete=models.PROTECT)
    issn_print = models.CharField("ISSN Print", max_length=9, blank=True, validators=[ISSN_VALIDATOR])
    issn_online = models.CharField("ISSN Online", max_length=9, blank=True, validators=[ISSN_VALIDATOR])
    fachgebiet = models.CharField(max_length=100, blank=True)
    verlag = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, null=True, blank=True, related_name="verlegt"
    )
    lieferant = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, null=True, blank=True, related_name="liefert"
    )
    paket = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="titel_im_paket",
        help_text="Falls der Titel Teil eines lizenzierten Pakets ist.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AKTIV)
    bibliotheken = models.ManyToManyField(Bibliothek, through="ObjektBibliothek", related_name="objekte")
    erstellt = models.DateTimeField(auto_now_add=True)
    geaendert = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Medium"
        verbose_name_plural = "Medien"
        ordering = ["titel"]

    def __str__(self):
        return self.titel

    def jahreswerte(self, kennzahlen=("TIR", "UIR")):
        """Kosten, Nutzung und CPU pro Jahr, neuestes Jahr zuerst."""
        kosten, kategorie = {}, {}
        for k in self.kosten.all():
            if k.betrag_chf is not None:
                kosten[k.jahr] = kosten.get(k.jahr, Decimal(0)) + k.vorzeichen * k.betrag_chf
            elif k.kategorie:
                kategorie[k.jahr] = k.get_kategorie_display()
        nutzung = {}
        # Ein Paket ohne eigene Nutzungszahlen erhält die Summe seiner Titel.
        for n in Nutzung.objects.filter(objekt__paket=self).select_related("kennzahl"):
            jahr = nutzung.setdefault(n.jahr, {})
            jahr[n.kennzahl.code] = jahr.get(n.kennzahl.code, 0) + n.wert
        for n in self.nutzung.all():
            nutzung.setdefault(n.jahr, {})[n.kennzahl.code] = n.wert
        jahre = sorted(set(kosten) | set(kategorie) | set(nutzung), reverse=True)
        zeilen = []
        for jahr in jahre:
            z = {"jahr": jahr, "kosten": kosten.get(jahr), "kategorie": kategorie.get(jahr), "werte": []}
            for code in kennzahlen:
                wert = nutzung.get(jahr, {}).get(code)
                z["werte"].append({"code": code, "nutzung": wert, "cpu": cpu(kosten.get(jahr), wert)})
            zeilen.append(z)
        return zeilen


class ObjektBibliothek(models.Model):
    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE)
    bibliothek = models.ForeignKey(Bibliothek, on_delete=models.PROTECT)
    herkunft = models.CharField(max_length=60, blank=True)
    verwaltung = models.CharField("verwaltet durch", max_length=60, blank=True)

    class Meta:
        verbose_name = "Bibliothekszuordnung"
        verbose_name_plural = "Bibliothekszuordnungen"
        constraints = [models.UniqueConstraint(fields=["objekt", "bibliothek"], name="objekt_bibliothek_einmalig")]

    def __str__(self):
        return f"{self.objekt} – {self.bibliothek.kuerzel}"


class Verwaltung(models.Model):
    """Bestellabwicklung pro Medium, Bibliothek und Jahr."""

    class Erwerbungsart(models.TextChoices):
        LIZENZ = "lizenz", "Lizenz"
        KAUF = "kauf", "Kauf"
        ABO = "abo", "Abonnement"
        KONSORTIUM = "konsortium", "Konsortium"
        PRINT_ONLINE = "print_online", "Print + Online"

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="verwaltung")
    bibliothek = models.ForeignKey(Bibliothek, on_delete=models.PROTECT)
    jahr = models.PositiveSmallIntegerField()
    erwerbungsart = models.CharField(max_length=20, choices=Erwerbungsart.choices, blank=True)
    etat_code = models.CharField("Etat Code", max_length=40, blank=True)
    sachkonto = models.CharField(max_length=20, blank=True)
    bestellposten_alma = models.CharField("Bestellposten Alma", max_length=40, blank=True)
    abo_nr = models.CharField("Abo-Nr", max_length=40, blank=True)
    ref_nr = models.CharField("REF-Nr", max_length=40, blank=True)
    laufzeit_bis = models.DateField("Lizenz läuft bis", null=True, blank=True)

    class Meta:
        verbose_name = "Verwaltung (pro Jahr)"
        verbose_name_plural = "Verwaltung (pro Jahr)"
        ordering = ["-jahr"]
        constraints = [
            models.UniqueConstraint(fields=["objekt", "bibliothek", "jahr"], name="verwaltung_einmalig")
        ]

    def __str__(self):
        return f"{self.objekt} {self.bibliothek.kuerzel} {self.jahr}"


class Kennzahl(models.Model):
    """Nutzungskennzahl, z. B. COUNTER 5 Total_Item_Requests."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80)
    beschreibung = models.TextField(blank=True)

    class Meta:
        verbose_name = "Kennzahl"
        verbose_name_plural = "Kennzahlen"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class Nutzung(models.Model):
    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="nutzung")
    jahr = models.PositiveSmallIntegerField()
    kennzahl = models.ForeignKey(Kennzahl, on_delete=models.PROTECT)
    wert = models.PositiveIntegerField()
    quelle = models.CharField(max_length=60, blank=True, help_text="z. B. COUNTER 5 Bericht TR_J1")

    class Meta:
        verbose_name = "Nutzung"
        verbose_name_plural = "Nutzung"
        ordering = ["-jahr", "kennzahl__code"]
        constraints = [
            models.UniqueConstraint(fields=["objekt", "jahr", "kennzahl"], name="nutzung_einmalig")
        ]

    def __str__(self):
        return f"{self.objekt} {self.jahr} {self.kennzahl.code}: {self.wert}"


class Kosten(models.Model):
    class Art(models.TextChoices):
        RECHNUNG = "rechnung", "Rechnung"
        GUTSCHRIFT = "gutschrift", "Gutschrift / Korrektur"

    class Kategorie(models.TextChoices):
        UNTER_500 = "unter 500", "unter 500"
        BIS_2000 = "500-2000", "500–2000"
        BIS_10000 = "2000-10000", "2000–10 000"
        BIS_50000 = "10000-50000", "10 000–50 000"
        UEBER_50000 = "über 50000", "über 50 000"

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="kosten")
    bibliothek = models.ForeignKey(Bibliothek, on_delete=models.PROTECT, null=True, blank=True)
    jahr = models.PositiveSmallIntegerField()
    art = models.CharField(max_length=12, choices=Art.choices, default=Art.RECHNUNG)
    betrag_chf = models.DecimalField("Betrag CHF", max_digits=12, decimal_places=2, null=True, blank=True)
    betrag_fw = models.DecimalField("Betrag Fremdwährung", max_digits=12, decimal_places=2, null=True, blank=True)
    waehrung = models.CharField("Währung", max_length=3, blank=True, help_text="z. B. EUR, USD, GBP")
    rechnungsdatum = models.DateField(null=True, blank=True)
    kategorie = models.CharField(
        max_length=15, choices=Kategorie.choices, blank=True,
        help_text="Nur solange kein exakter Betrag erfasst ist (Übernahme aus den alten Listen).",
    )

    class Meta:
        verbose_name = "Kosten"
        verbose_name_plural = "Kosten"
        ordering = ["-jahr"]

    def __str__(self):
        return f"{self.objekt} {self.jahr}: {self.betrag_chf or self.kategorie} CHF"

    @property
    def vorzeichen(self):
        return -1 if self.art == self.Art.GUTSCHRIFT else 1

    def save(self, *args, **kwargs):
        if self.betrag_chf is not None and self.art == self.Art.RECHNUNG:
            self.kategorie = kategorie_fuer(self.betrag_chf)
        super().save(*args, **kwargs)


def kategorie_fuer(betrag):
    for grenze, kat in (
        (500, Kosten.Kategorie.UNTER_500), (2000, Kosten.Kategorie.BIS_2000),
        (10000, Kosten.Kategorie.BIS_10000), (50000, Kosten.Kategorie.BIS_50000),
    ):
        if betrag < grenze:
            return kat
    return Kosten.Kategorie.UEBER_50000


class Entscheid(models.Model):
    class Wahl(models.TextChoices):
        BEHALTEN = "behalten", "behalten"
        BEOBACHTEN = "beobachten", "beobachten / abwarten"
        ABBESTELLEN = "abbestellen", "abbestellen"
        ERSETZEN = "ersetzen", "ersetzen"

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="entscheide")
    datum = models.DateField()
    entscheid = models.CharField(max_length=15, choices=Wahl.choices)
    begruendung = models.TextField("Begründung", blank=True)
    person = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name = "Entscheid"
        verbose_name_plural = "Entscheide"
        ordering = ["-datum"]

    def __str__(self):
        return f"{self.objekt}: {self.get_entscheid_display()} ({self.datum:%d.%m.%Y})"


class Notiz(models.Model):
    class Typ(models.TextChoices):
        ALLGEMEIN = "allgemein", "Allgemein"
        ZUGANG = "zugang", "Zugang / Plattform"
        VERTRAG = "vertrag", "Vertrag / Konditionen"
        STATISTIK = "statistik", "Nutzungsstatistik"

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="notizen")
    jahr = models.PositiveSmallIntegerField(null=True, blank=True)
    typ = models.CharField(max_length=12, choices=Typ.choices, default=Typ.ALLGEMEIN)
    text = models.TextField()
    erstellt = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "Notiz"
        verbose_name_plural = "Notizen"
        ordering = ["-erstellt"]

    def __str__(self):
        return self.text[:60]


class ObjektQuelle(models.Model):
    """Herkunftsnachweis aus der Migration der alten Excel-Listen."""

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name="quellen")
    quelle_datei = models.CharField(max_length=150)
    quelle_blatt = models.CharField(max_length=100, blank=True)
    original_titel = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Herkunft"
        verbose_name_plural = "Herkunft (Migration)"

    def __str__(self):
        return f"{self.quelle_datei} / {self.quelle_blatt}"
