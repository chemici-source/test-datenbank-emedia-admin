"""Erzeugt erfundene, aber realistisch aufgebaute Testdaten.

Titel, Verlage, Beträge und Nutzungszahlen sind zufällig generiert (fester Seed,
also bei jedem Lauf gleich). Nur die Bibliotheken entsprechen den echten.
"""
import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from katalog.models import (
    Bibliothek, Entscheid, Kennzahl, Kosten, Medientyp, Notiz, Nutzung, Objekt,
    ObjektBibliothek, ObjektQuelle, Organisation, Verwaltung, kategorie_fuer,
)

JAHRE = [2021, 2022, 2023, 2024, 2025]

BIBLIOTHEKEN = [
    ("B452", "Medizin", ["Kardiologie", "Onkologie", "Neurologie", "Pädiatrie", "Radiologie", "Immunologie", "Pharmakologie"]),
    ("B540", "Vetsuisse", ["Veterinary Surgery", "Animal Welfare", "Equine Medicine", "Wildlife Health", "Parasitology"]),
    ("B521", "Zahnmedizin", ["Dental Research", "Orthodontics", "Periodontology", "Oral Surgery"]),
    ("B552", "Pflanzenwissenschaften", ["Plant Biology", "Botany", "Ecology", "Mycology"]),
    ("B467", "Geographie", ["Human Geography", "Climate Science", "Landscape Studies", "Hydrology"]),
    ("E30", "Exakte Wissenschaften", ["Mathematics", "Theoretical Physics", "Astronomy", "Statistics", "Computer Science"]),
    ("B554", "Muesmatt", ["Chemistry", "Geology", "Mineralogy", "Biochemistry"]),
]
MEDIENTYPEN = ["E-Journal-Einzeltitel", "E-Journal-Paket", "E-Book-Paket", "Datenbank", "Lizenzpaket / App", "Zeitschriften-Abo"]
KENNZAHLEN = [
    ("TIR", "Total Item Requests", "COUNTER 5: alle Zugriffe auf Volltexte"),
    ("UIR", "Unique Item Requests", "COUNTER 5: Zugriffe, pro Sitzung und Artikel nur einmal gezählt"),
    ("UTR", "Unique Title Requests", "COUNTER 5: pro Sitzung und Buchtitel nur einmal gezählt"),
    ("SEARCH", "Searches Platform", "COUNTER 5: Suchanfragen auf der Plattform"),
]
VERLAGE = ["Alpenglanz Academic", "Meridian Science Press", "Nordlicht Verlag", "Helvetia Scholarly", "Quartz Journals",
           "Atlas & Söhne Wissenschaft", "Lumen Medical Publishing", "Silvaplana Press", "Orion Research Media", "Rheintal Fachverlag"]
LIEFERANTEN = ["Buchagentur Alpha", "Medienhaus Beta", "Konsortium Gamma", "Direktbezug"]
VORSILBEN = ["Alpine", "Helvetic", "Nordic", "Transatlantic", "Meridian", "Continental", "Lakeside", "Global"]
MUSTER = ["{v} Journal of {f}", "{v} Reviews in {f}", "Annals of {v} {f}", "{f} {v} Letters", "{v} {f} Quarterly", "Advances in {v} {f}"]
NOTIZEN = [
    ("zugang", "Zugriff über IP-Authentifizierung und Shibboleth."),
    ("vertrag", "Preiserhöhung für das Folgejahr angekündigt, Angebot einholen."),
    ("statistik", "Nutzungsstatistik kommt quartalsweise per SUSHI."),
    ("vertrag", "Teil eines Konsortialvertrags, Einzelkündigung nur zum Jahresende möglich."),
    ("allgemein", "Fachreferat wünscht Rückmeldung vor einer Abbestellung."),
    ("statistik", "Vor 2023 nur COUNTER-4-Zahlen verfügbar."),
]
PERSONEN = ["Fachreferat Medizin", "Fachreferat Naturwissenschaften", "E-Medien-Team", "Bibliotheksleitung"]


def issn(rnd):
    ziffern = [rnd.randint(0, 9) for _ in range(7)]
    rest = sum(z * g for z, g in zip(ziffern, range(8, 1, -1))) % 11
    pruef = (11 - rest) % 11
    p = "X" if pruef == 10 else str(pruef)
    s = "".join(map(str, ziffern))
    return f"{s[:4]}-{s[4:]}{p}"


class Command(BaseCommand):
    help = "Füllt die Datenbank mit erfundenen Testdaten."

    def add_arguments(self, parser):
        parser.add_argument("--loeschen", action="store_true", help="Vorhandene Medien vorher löschen.")
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["loeschen"]:
            Objekt.objects.all().delete()
            Organisation.objects.all().delete()
        elif Objekt.objects.exists():
            self.stdout.write("Es sind bereits Medien vorhanden, nichts getan (mit --loeschen neu erzeugen).")
            return

        rnd = random.Random(opts["seed"])
        bibs = {k: Bibliothek.objects.update_or_create(kuerzel=k, defaults={"name": n})[0] for k, n, _ in BIBLIOTHEKEN}
        typen = {n: Medientyp.objects.get_or_create(name=n)[0] for n in MEDIENTYPEN}
        kz = {c: Kennzahl.objects.update_or_create(code=c, defaults={"name": n, "beschreibung": b})[0] for c, n, b in KENNZAHLEN}
        verlage = [Organisation.objects.create(name=n, ist_verlag=True) for n in VERLAGE]
        lieferanten = [Organisation.objects.create(name=n, ist_lieferant=True) for n in LIEFERANTEN]

        benutzt = set()

        def neuer_titel(fach):
            for _ in range(50):
                t = rnd.choice(MUSTER).format(v=rnd.choice(VORSILBEN), f=fach)
                if t not in benutzt:
                    benutzt.add(t)
                    return t
            return f"{fach} {len(benutzt)}"

        anzahl = 0
        for kuerzel, _, faecher in BIBLIOTHEKEN:
            bib = bibs[kuerzel]
            plan = [("E-Journal-Einzeltitel", 14), ("E-Book-Paket", 3), ("Datenbank", 2), ("E-Journal-Paket", 1)]
            if kuerzel in ("B452", "B540", "B521"):
                plan.append(("Lizenzpaket / App", 2))
            if kuerzel in ("B467", "E30", "B554"):
                plan.append(("Zeitschriften-Abo", 3))
            for typ, n in plan:
                for _ in range(n):
                    fach = rnd.choice(faecher)
                    if typ == "E-Book-Paket":
                        titel = f"{rnd.choice(VERLAGE).split()[0]} eBook Collection {fach}"
                    elif typ == "Datenbank":
                        titel = f"{fach}{rnd.choice(['Base', 'Link', 'Index', 'Navigator'])} Online"
                    elif typ == "E-Journal-Paket":
                        titel = f"{rnd.choice(VERLAGE)} Journal Package"
                    elif typ == "Lizenzpaket / App":
                        titel = f"{fach} {rnd.choice(['Learning App', 'Atlas 3D', 'Reference Suite'])}"
                    else:
                        titel = neuer_titel(fach)
                    if titel in benutzt and typ != "E-Journal-Einzeltitel":
                        titel = f"{titel} {kuerzel}"
                    benutzt.add(titel)
                    objekt = self._medium(rnd, titel, typen[typ], fach, bib, bibs, verlage, lieferanten, kz)
                    anzahl += 1
                    if typ == "E-Journal-Paket":
                        for _ in range(rnd.randint(3, 5)):
                            t = Objekt.objects.create(
                                titel=neuer_titel(rnd.choice(faecher)), medientyp=typen["E-Journal-Einzeltitel"],
                                issn_online=issn(rnd), fachgebiet=fach, verlag=objekt.verlag, paket=objekt,
                                lieferant=objekt.lieferant,
                            )
                            ObjektBibliothek.objects.create(objekt=t, bibliothek=bib)
                            for jahr in JAHRE:
                                tir = int(rnd.lognormvariate(5, 1))
                                Nutzung.objects.create(objekt=t, jahr=jahr, kennzahl=kz["TIR"], wert=tir)
                                Nutzung.objects.create(objekt=t, jahr=jahr, kennzahl=kz["UIR"], wert=int(tir * rnd.uniform(0.55, 0.8)))
                            anzahl += 1

        self.stdout.write(self.style.SUCCESS(f"{anzahl} Testmedien erzeugt."))

    def _medium(self, rnd, titel, typ, fach, bib, bibs, verlage, lieferanten, kz):
        ist_journal = typ.name in ("E-Journal-Einzeltitel", "Zeitschriften-Abo")
        status = rnd.choices(
            [Objekt.Status.AKTIV, Objekt.Status.ABBESTELLT, Objekt.Status.PRUEFUNG, Objekt.Status.OA],
            weights=[78, 10, 8, 4] if ist_journal else [85, 8, 7, 0],
        )[0]
        o = Objekt.objects.create(
            titel=titel, medientyp=typ, fachgebiet=fach, status=status,
            issn_print=issn(rnd) if ist_journal and rnd.random() < 0.5 else "",
            issn_online=issn(rnd) if ist_journal else "",
            verlag=rnd.choice(verlage), lieferant=rnd.choice(lieferanten),
        )
        ObjektBibliothek.objects.create(objekt=o, bibliothek=bib, verwaltung=rnd.choice(["MNW", "E-Library", ""]))
        weitere = None
        if rnd.random() < 0.08:  # gemeinsame Lizenz zweier Bibliotheken (wie VetCenter)
            weitere = rnd.choice([b for b in bibs.values() if b != bib])
            ObjektBibliothek.objects.create(objekt=o, bibliothek=weitere)
        ObjektQuelle.objects.create(objekt=o, quelle_datei="Testdaten", quelle_blatt=bib.kuerzel, original_titel=titel)

        # Kosten
        basis = {
            "E-Journal-Einzeltitel": (7.0, 0.9), "Zeitschriften-Abo": (6.0, 0.7), "E-Book-Paket": (8.5, 0.7),
            "Datenbank": (9.0, 0.8), "E-Journal-Paket": (10.3, 0.5), "Lizenzpaket / App": (8.8, 0.6),
        }[typ.name]
        preis = Decimal(str(round(rnd.lognormvariate(*basis), 2)))
        letzte = 2023 if status == Objekt.Status.ABBESTELLT else 2025
        start = rnd.choice([2021, 2021, 2021, 2022, 2023])
        for jahr in JAHRE:
            if status == Objekt.Status.OA or jahr < start or jahr > letzte:
                continue
            preis = (preis * Decimal(str(rnd.uniform(1.0, 1.07)))).quantize(Decimal("0.01"))
            fw = rnd.choice(["EUR", "USD", "GBP", ""])
            if jahr == 2021 and rnd.random() < 0.3:
                # Übergangszustand: aus alter Liste nur Kategorie bekannt
                Kosten.objects.create(objekt=o, bibliothek=bib, jahr=jahr, kategorie=kategorie_fuer(preis))
            else:
                Kosten.objects.create(
                    objekt=o, bibliothek=bib, jahr=jahr, betrag_chf=preis,
                    betrag_fw=(preis * Decimal("1.05")).quantize(Decimal("0.01")) if fw else None,
                    waehrung=fw, rechnungsdatum=date(jahr, rnd.randint(1, 3), rnd.randint(1, 28)),
                )
            if rnd.random() < 0.04:
                Kosten.objects.create(objekt=o, bibliothek=bib, jahr=jahr, art=Kosten.Art.GUTSCHRIFT,
                                      betrag_chf=(preis * Decimal("0.1")).quantize(Decimal("0.01")))
            Verwaltung.objects.create(
                objekt=o, bibliothek=bib, jahr=jahr,
                erwerbungsart=rnd.choice(Verwaltung.Erwerbungsart.values),
                etat_code=f"{bib.kuerzel}-NB-{rnd.randint(10, 99)}",
                bestellposten_alma=f"POL-DEMO-{jahr}-{rnd.randint(10000, 99999)}",
                abo_nr=str(rnd.randint(100000, 999999)) if rnd.random() < 0.4 else "",
                laufzeit_bis=date(jahr, 12, 31),
            )

        # Nutzung
        if typ.name == "E-Journal-Paket":
            pass  # Nutzung ergibt sich aus den Titeln im Paket
        elif rnd.random() > 0.07:  # einige Medien liefern keine Statistik
            mittel = {"E-Journal-Einzeltitel": 5.5, "Zeitschriften-Abo": 4.5}.get(typ.name, 7.5)
            tir = rnd.lognormvariate(mittel, 1.0)
            trend = rnd.uniform(0.9, 1.1)
            for jahr in JAHRE:
                if jahr < start:
                    continue
                tir = max(0, tir * trend * rnd.uniform(0.85, 1.15))
                Nutzung.objects.create(objekt=o, jahr=jahr, kennzahl=kz["TIR"], wert=int(tir))
                if typ.name == "E-Book-Paket":
                    Nutzung.objects.create(objekt=o, jahr=jahr, kennzahl=kz["UTR"], wert=int(tir * rnd.uniform(0.4, 0.6)))
                else:
                    Nutzung.objects.create(objekt=o, jahr=jahr, kennzahl=kz["UIR"], wert=int(tir * rnd.uniform(0.55, 0.8)))
                if typ.name == "Datenbank":
                    Nutzung.objects.create(objekt=o, jahr=jahr, kennzahl=kz["SEARCH"], wert=int(tir * rnd.uniform(1.5, 4)))
        else:
            Notiz.objects.create(objekt=o, typ=Notiz.Typ.STATISTIK, text="Anbieter liefert keine Nutzungsstatistik.")

        # Entscheide und Notizen
        if status == Objekt.Status.ABBESTELLT:
            Entscheid.objects.create(objekt=o, datum=date(2023, 10, rnd.randint(1, 28)), entscheid=Entscheid.Wahl.ABBESTELLEN,
                                     begruendung="CPU dauerhaft zu hoch, Alternative über Konsortium vorhanden.",
                                     person=rnd.choice(PERSONEN))
        elif status == Objekt.Status.PRUEFUNG:
            Entscheid.objects.create(objekt=o, datum=date(2025, rnd.randint(1, 9), rnd.randint(1, 28)), entscheid=Entscheid.Wahl.BEOBACHTEN,
                                     begruendung="Nutzung rückläufig, Entwicklung 2025 abwarten.", person=rnd.choice(PERSONEN))
        elif rnd.random() < 0.25:
            Entscheid.objects.create(objekt=o, datum=date(rnd.choice([2024, 2025]), rnd.randint(1, 9), rnd.randint(1, 28)),
                                     entscheid=Entscheid.Wahl.BEHALTEN, begruendung="Kernressource für Lehre und Forschung.",
                                     person=rnd.choice(PERSONEN))
        if rnd.random() < 0.35:
            typ_n, text = rnd.choice(NOTIZEN)
            Notiz.objects.create(objekt=o, typ=typ_n, text=text, jahr=rnd.choice([None, 2024, 2025]))
        return o
