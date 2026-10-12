from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Kennzahl, Kosten, Medientyp, Nutzung, Objekt, cpu


class CpuTest(TestCase):
    def test_cpu_rechnet_mit_gutschrift(self):
        o = Objekt.objects.create(titel="Testjournal", medientyp=Medientyp.objects.create(name="E-Journal"))
        tir = Kennzahl.objects.create(code="TIR", name="Total Item Requests")
        Kosten.objects.create(objekt=o, jahr=2025, betrag_chf=Decimal("1000"))
        Kosten.objects.create(objekt=o, jahr=2025, betrag_chf=Decimal("100"), art=Kosten.Art.GUTSCHRIFT)
        Nutzung.objects.create(objekt=o, jahr=2025, kennzahl=tir, wert=300)
        zeile = o.jahreswerte(["TIR"])[0]
        self.assertEqual(zeile["kosten"], Decimal("900"))
        self.assertEqual(zeile["werte"][0]["cpu"], Decimal("3.00"))

    def test_keine_cpu_ohne_nutzung(self):
        self.assertIsNone(cpu(Decimal("500"), 0))
        self.assertIsNone(cpu(None, 10))

    def test_kategorie_wird_aus_betrag_gesetzt(self):
        o = Objekt.objects.create(titel="X", medientyp=Medientyp.objects.create(name="Datenbank"))
        k = Kosten.objects.create(objekt=o, jahr=2025, betrag_chf=Decimal("2500"))
        self.assertEqual(k.kategorie, Kosten.Kategorie.BIS_10000)


@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SeitenTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        import os
        os.environ["DEMO_PASSWORT"] = "demo-test-123"
        os.environ["DEMO_DATEN"] = "1"
        call_command("einrichten", verbosity=0)

    def anmelden(self, name):
        self.client.force_login(get_user_model().objects.get(username=name))

    def test_ohne_anmeldung_umleitung(self):
        r = self.client.get(reverse("uebersicht"))
        self.assertEqual(r.status_code, 302)

    def test_leser_sieht_alle_seiten_aber_keine_verwaltung(self):
        self.anmelden("leser")
        for url in [reverse("uebersicht"), reverse("medien_liste"), reverse("medien_liste") + "?sort=cpu&cpu_min=20",
                    reverse("medium_detail", args=[Objekt.objects.first().pk])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        r = self.client.get(reverse("medien_liste") + "?format=csv")
        self.assertIn("text/csv", r["Content-Type"])

    def test_bearbeiter_kann_medium_aendern(self):
        self.anmelden("bearbeiter")
        o = Objekt.objects.first()
        self.assertEqual(self.client.get(reverse("admin:katalog_objekt_change", args=[o.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:katalog_objekt_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)

    def test_suche_mit_vorschlag(self):
        self.anmelden("leser")
        titel = Objekt.objects.filter(medientyp__name="E-Journal-Einzeltitel").first().titel
        r = self.client.get(reverse("medien_liste"), {"q": titel[:-2] + "xx"})
        self.assertContains(r, "Meinten Sie")


class PaketTest(TestCase):
    def test_paket_nutzung_ist_summe_der_titel(self):
        from . import auswertung
        typ = Medientyp.objects.create(name="Paket")
        tir = Kennzahl.objects.create(code="TIR", name="Total Item Requests")
        paket = Objekt.objects.create(titel="Paket", medientyp=typ)
        for wert in (100, 300):
            t = Objekt.objects.create(titel=f"Titel {wert}", medientyp=typ, paket=paket)
            Nutzung.objects.create(objekt=t, jahr=2025, kennzahl=tir, wert=wert)
        Kosten.objects.create(objekt=paket, jahr=2025, betrag_chf=Decimal("2000"))
        [p] = auswertung.zeilen(Objekt.objects.filter(pk=paket.pk), 2025)
        self.assertEqual(p.nutzung_jahr, 400)
        self.assertEqual(p.cpu_jahr, Decimal("5.00"))
        self.assertEqual(paket.jahreswerte(["TIR"])[0]["werte"][0]["nutzung"], 400)
