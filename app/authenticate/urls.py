from django.urls import path

from .views import AboutMeView, LoginView, RefreshView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("token/refresh/", RefreshView.as_view(), name="auth-token-refresh"),
    path("about-me/", AboutMeView.as_view(), name="auth-about-me"),
]
