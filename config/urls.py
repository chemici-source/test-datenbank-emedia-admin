from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("verwaltung/", admin.site.urls),
    path("anmelden/", auth_views.LoginView.as_view(), name="login"),
    path("abmelden/", auth_views.LogoutView.as_view(), name="logout"),
    path("favicon.ico", lambda request: HttpResponse(status=204)),
    path("", include("katalog.urls")),
]
