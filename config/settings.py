"""Einstellungen für das E-Medien-Portal.

Alles, was sich zwischen lokal und deplo.io unterscheidet, kommt aus
Umgebungsvariablen. Lokal läuft die App mit DEBUG=1 ohne weitere Konfiguration mit SQLite.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, unquote

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "ja")


DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Beim Bauen auf deplo.io (collectstatic) sind die geheimen Variablen noch nicht gesetzt;
    # dafür reicht ein Platzhalter. Im laufenden Betrieb ist SECRET_KEY Pflicht.
    if DEBUG or "collectstatic" in sys.argv:
        SECRET_KEY = "nur-fuer-lokale-entwicklung-und-build"
    else:
        raise ValueError("Umgebungsvariable SECRET_KEY fehlt.")

# .deploio.app ist die Standard-Domain auf deplo.io; eigene Domains per ALLOWED_HOSTS ergänzen.
_extra_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS = [".deploio.app", "localhost", "127.0.0.1"] + _extra_hosts
CSRF_TRUSTED_ORIGINS = ["https://*.deploio.app"] + [f"https://{h.lstrip('.')}" for h in _extra_hosts]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "katalog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "katalog.context_processors.portal",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Datenbank -----------------------------------------------------------
# Reihenfolge: DATABASE_URL, sonst die von deplo.io injizierte Verbindung
# (NINE_..._DSN, entsteht mit `nctl update app ... --service db=postgresdatabase/<name>`),
# sonst lokale SQLite-Datei.

def _find_database_url():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    for key in sorted(os.environ):
        if re.fullmatch(r"NINE_\w+_DSN", key):
            return os.environ[key]
    return None


def _mysql_config(url):
    # deplo.io liefert mysql://user:pw@host:port/db?ssl-mode=REQUIRED.
    # PyMySQL kennt "ssl-mode" nicht, daher TLS hier selbst einschalten.
    import pymysql

    pymysql.install_as_MySQLdb()
    parts = urlsplit(url)
    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname,
        "PORT": parts.port or 3306,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"charset": "utf8mb4", "ssl": {"check_hostname": False}},
    }


_db_url = _find_database_url()
if _db_url and _db_url.startswith("mysql"):
    DATABASES = {"default": _mysql_config(_db_url)}
elif _db_url:
    DATABASES = {"default": dj_database_url.parse(_db_url, conn_max_age=60)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "de-ch"
LANGUAGES = [("de", "Deutsch")]  # Oberfläche immer deutsch, auch bei englischem Browser
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "uebersicht"
LOGOUT_REDIRECT_URL = "login"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Hinweis im Kopf jeder Seite; leer lassen für den Echtbetrieb.
PORTAL_HINWEIS = os.environ.get("PORTAL_HINWEIS", "Demo mit erfundenen Testdaten")
