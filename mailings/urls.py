from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
)
from django.urls import path

from . import views

app_name = "mailings"

urlpatterns = [
    # Главная страница
    path("", views.IndexView.as_view(), name="index"),
    # Аутентификация
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path(
        "register/done/", views.RegistrationDoneView.as_view(), name="registration_done"
    ),
    path(
        "verify/<uidb64>/<token>/",
        views.EmailVerificationView.as_view(),
        name="verify_email",
    ),
    path(
        "resend-verification/",
        views.ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    # Восстановление пароля
    path(
        "password-reset/",
        views.CustomPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # Статистика
    path("statistics/", views.user_statistics, name="user_statistics"),
    # Управление пользователями (только для менеджеров)
    path("users/", views.user_list_view, name="user_list"),
    path(
        "users/<int:user_id>/toggle/",
        views.toggle_user_active,
        name="toggle_user_active",
    ),
    # Клиенты
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/create/", views.ClientCreateView.as_view(), name="client_create"),
    path(
        "clients/<int:pk>/edit/", views.ClientUpdateView.as_view(), name="client_update"
    ),
    path(
        "clients/<int:pk>/delete/",
        views.ClientDeleteView.as_view(),
        name="client_delete",
    ),
    # Сообщения
    path("messages/", views.MessageListView.as_view(), name="message_list"),
    path("messages/create/", views.MessageCreateView.as_view(), name="message_create"),
    path(
        "messages/<int:pk>/edit/",
        views.MessageUpdateView.as_view(),
        name="message_update",
    ),
    path(
        "messages/<int:pk>/delete/",
        views.MessageDeleteView.as_view(),
        name="message_delete",
    ),
    # Рассылки
    path("mailings/", views.MailingListView.as_view(), name="mailing_list"),
    path("mailings/create/", views.MailingCreateView.as_view(), name="mailing_create"),
    path(
        "mailings/<int:pk>/edit/",
        views.MailingUpdateView.as_view(),
        name="mailing_update",
    ),
    path(
        "mailings/<int:pk>/delete/",
        views.MailingDeleteView.as_view(),
        name="mailing_delete",
    ),
    path("mailings/<int:pk>/", views.mailing_detail, name="mailing_detail"),
    path("mailings/<int:pk>/send/", views.send_mailing_manual, name="send_mailing"),
    path(
        "mailings/<int:pk>/toggle/",
        views.toggle_mailing_enabled,
        name="toggle_mailing_enabled",
    ),
]
