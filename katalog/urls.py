from django.urls import path

from . import views

urlpatterns = [
    path("", views.uebersicht, name="uebersicht"),
    path("medien/", views.medien_liste, name="medien_liste"),
    path("medien/<int:pk>/", views.medium_detail, name="medium_detail"),
]
