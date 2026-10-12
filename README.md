# E-Medien MNW – Demo

Webanwendung für Bestand, Kosten, Nutzung und CPU (Cost per Use) der E-Medien der UB MNW.
Diese Version läuft mit **erfundenen Testdaten** und dient dazu, die Anwendung und die Zielplattform deplo.io auszuprobieren.

## Was die Demo kann

| Bereich | Adresse | Wer |
|---|---|---|
| Übersicht: Kosten, Nutzung, CPU pro Jahr und Bibliothek, höchste CPU, letzte Entscheide | `/` | alle angemeldeten |
| Medienliste mit Suche (inkl. „Meinten Sie …?“), Filtern, Sortierung nach CPU, CSV-Export für Excel | `/medien/` | alle angemeldeten |
| Detailseite pro Medium: Stammdaten, Jahrestabelle mit CPU, Verwaltung, Entscheide, Notizen | `/medien/<id>/` | alle angemeldeten |
| Verwaltung: Medien anlegen und bearbeiten, inkl. Kosten, Nutzung, Entscheiden, Notizen; Änderungsgeschichte pro Datensatz | `/verwaltung/` | Gruppe „Bearbeiten“, Admin |

CPU wird immer aus Kosten und Nutzung berechnet (Kosten CHF ÷ Nutzung), nie gespeichert. Ein Paket ohne eigene Nutzungszahlen erhält die Summe seiner Titel.

### Rollen

- **Lesen**: sieht alle Abfrageseiten, kann nichts ändern.
- **Bearbeiten**: kann zusätzlich alle E-Medien-Daten in der Verwaltung ändern, aber keine Benutzer.
- **Admin** (Superuser): alles, inkl. Benutzerverwaltung.

Die Demo legt die Konten `leser` und `bearbeiter` an, wenn `DEMO_PASSWORT` gesetzt ist.

## Auf deplo.io bereitstellen

Voraussetzungen: ein deplo.io-Konto, das Kommandozeilenwerkzeug [`nctl`](https://github.com/ninech/nctl) (mindestens v1.1.0) und dieser Code in einem Git-Repository (GitHub, GitLab o. ä.; privat ist möglich).

```bash
nctl auth login

# 1. Datenbank (PostgreSQL, Economy-Variante)
nctl create postgresdatabase emedien-db

# 2. Anwendung
nctl create app emedien \
  --git-url=https://github.com/<konto>/<repo> \
  --git-revision=main \
  --language=python \
  --buildpack-stack=heroku \
  --service db=postgresdatabase/emedien-db \
  --env=DEMO_DATEN=1 \
  --env=DJANGO_SU_NAME=admin \
  --sensitive-env=SECRET_KEY=<langer-zufaelliger-text> \
  --sensitive-env=DJANGO_SU_PASSWORD=<admin-passwort> \
  --sensitive-env=DEMO_PASSWORT=<passwort-fuer-leser-und-bearbeiter>
```

Bei einem privaten Repository zusätzlich `--git-username=<benutzer> --git-password=<token>` angeben.

Danach:

```bash
nctl get app emedien          # zeigt die Adresse, z. B. https://emedien.<id>.deploio.app
nctl logs app emedien         # Protokolle der laufenden App
nctl get builds               # Status der Builds
```

### Was beim Deployment passiert

1. deplo.io baut die App mit dem Python-Buildpack aus `requirements.txt` und `.python-version`.
2. Vor jedem Release läuft der Deploy-Job aus `.deploio.yaml`: `python manage.py einrichten`
   führt die Datenbank-Migrationen aus, legt die Gruppen „Lesen“ und „Bearbeiten“ an, erstellt das Admin-Konto und die Demo-Konten und lädt die Testdaten, wenn die Datenbank leer ist.
3. Die App startet mit `gunicorn` (siehe `Procfile`).

Die Verbindung zur Datenbank übergibt deplo.io automatisch über die Umgebungsvariable `NINE_PGDB_DB_DSN`. Die App erkennt jede Variable der Form `NINE_..._DSN` oder `DATABASE_URL`.

### MySQL statt PostgreSQL

Funktioniert ebenfalls ohne Codeänderung: `nctl create mysqldatabase emedien-db` und `--service db=mysqldatabase/emedien-db`.

### Umgebungsvariablen

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `SECRET_KEY` | ja | langer zufälliger Text, geheim halten |
| `DJANGO_SU_NAME`, `DJANGO_SU_PASSWORD` | für das erste Admin-Konto | wird nur angelegt, wenn es noch nicht existiert |
| `DEMO_PASSWORT` | nein | legt die Demo-Konten `leser` und `bearbeiter` an |
| `DEMO_DATEN` | nein | `1` = Testdaten laden, wenn die Datenbank leer ist |
| `ALLOWED_HOSTS` | nein | eigene Domains, kommagetrennt (`*.deploio.app` ist immer erlaubt) |
| `PORTAL_HINWEIS` | nein | Text im gelben Band oben; leer = kein Band |
| `DATABASE_URL` | nein | überschreibt die von deplo.io injizierte Datenbank |

## Lokal starten

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
set DEBUG=1 / export DEBUG=1
export DJANGO_SU_NAME=admin DJANGO_SU_PASSWORD=admin123 DEMO_PASSWORT=demo123 DEMO_DATEN=1
python manage.py einrichten
python manage.py runserver
```

Dann http://127.0.0.1:8000 öffnen. Ohne Datenbankvariable verwendet die App lokal eine SQLite-Datei.

Testdaten neu erzeugen: `python manage.py demo_daten --loeschen`
Tests: `python manage.py test katalog`

## Aufbau

```
config/            Einstellungen, URLs
katalog/models.py  Datenmodell (Medium, Bibliothek, Verwaltung, Kosten, Nutzung, Entscheid, Notiz, Herkunft)
katalog/admin.py   Verwaltungsoberfläche
katalog/views.py   Abfrageoberfläche
katalog/auswertung.py  Berechnung von Kosten, Nutzung und CPU
katalog/management/commands/  einrichten, demo_daten
```
