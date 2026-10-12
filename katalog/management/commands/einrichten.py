"""Einrichtung bei jedem Deployment (deplo.io Deploy-Job, siehe .deploio.yaml).

1. Datenbank-Migrationen ausführen
2. Benutzergruppen "Lesen" und "Bearbeiten" mit Rechten anlegen
3. Admin-Konto aus DJANGO_SU_NAME / DJANGO_SU_PASSWORD anlegen (falls gesetzt und noch nicht vorhanden)
4. Demo-Konten "leser" und "bearbeiter" mit DEMO_PASSWORT anlegen (falls gesetzt)
5. Testdaten laden, wenn DEMO_DATEN=1 und die Datenbank noch leer ist
"""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand

BEARBEITBAR = ["objekt", "objektbibliothek", "verwaltung", "kosten", "nutzung", "entscheid", "notiz",
               "organisation", "objektquelle"]


class Command(BaseCommand):
    help = "Migrationen, Rollen, Konten und (optional) Testdaten einrichten."

    def handle(self, *args, **opts):
        call_command("migrate", interactive=False)

        lesen, _ = Group.objects.get_or_create(name="Lesen")
        lesen.permissions.set(Permission.objects.filter(content_type__app_label="katalog", codename__startswith="view_"))
        bearbeiten, _ = Group.objects.get_or_create(name="Bearbeiten")
        rechte = Permission.objects.filter(content_type__app_label="katalog", codename__startswith="view_")
        for modell in BEARBEITBAR:
            rechte = rechte | Permission.objects.filter(
                content_type__app_label="katalog", codename__in=[f"add_{modell}", f"change_{modell}", f"delete_{modell}"]
            )
        bearbeiten.permissions.set(rechte)
        self.stdout.write("Gruppen 'Lesen' und 'Bearbeiten' eingerichtet.")

        User = get_user_model()
        name, pw = os.environ.get("DJANGO_SU_NAME"), os.environ.get("DJANGO_SU_PASSWORD")
        if name and pw and not User.objects.filter(username=name).exists():
            User.objects.create_superuser(name, os.environ.get("DJANGO_SU_EMAIL", ""), pw)
            self.stdout.write(f"Admin-Konto '{name}' angelegt.")

        demo_pw = os.environ.get("DEMO_PASSWORT")
        if demo_pw:
            for benutzer, gruppe, staff in (("leser", lesen, False), ("bearbeiter", bearbeiten, True)):
                u, neu = User.objects.get_or_create(username=benutzer, defaults={"is_staff": staff})
                if neu:
                    u.set_password(demo_pw)
                    u.save()
                    self.stdout.write(f"Demo-Konto '{benutzer}' angelegt.")
                u.groups.add(gruppe)

        if os.environ.get("DEMO_DATEN", "").lower() in ("1", "true", "ja"):
            call_command("demo_daten")
