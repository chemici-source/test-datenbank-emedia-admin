from django.conf import settings


def portal(request):
    return {"portal_hinweis": settings.PORTAL_HINWEIS}
