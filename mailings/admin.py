from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import Client, Mailing, MailingAttempt, Message, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Админка для модели User"""

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = ["username", "email", "first_name", "last_name", "phone_number"]
    list_filter = ["email"]
    search_fields = ["username", "email", "phone_number"]

    fieldsets = UserAdmin.fieldsets + (
        (
            "Дополнительная информация",
            {
                "fields": (
                    "phone_number",
                    "avatar",
                    "is_blocked",
                    "blocked_at",
                    "email_verified",
                    "email_verification_token",
                ),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Дополнительная информация",
            {
                "fields": ("email", "phone_number"),
            },
        ),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["email", "full_name", "owner", "created_at"]
    list_filter = ["created_at", "owner"]
    search_fields = ["email", "full_name"]
    raw_id_fields = ["owner"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "owner", "created_at"]
    list_filter = ["created_at", "owner"]
    search_fields = ["subject"]
    raw_id_fields = ["owner"]


class MailingAttemptInline(admin.TabularInline):
    model = MailingAttempt
    extra = 0
    readonly_fields = ["attempt_datetime", "status", "server_response"]
    can_delete = False


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "message",
        "owner",
        "status",
        "start_datetime",
        "end_datetime",
    ]
    list_filter = ["status", "start_datetime", "owner"]
    filter_horizontal = ["recipients"]
    inlines = [MailingAttemptInline]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["owner", "message"]


@admin.register(MailingAttempt)
class MailingAttemptAdmin(admin.ModelAdmin):
    list_display = ["id", "mailing", "attempt_datetime", "status"]
    list_filter = ["status", "attempt_datetime"]
    readonly_fields = ["attempt_datetime", "status", "server_response", "mailing"]
