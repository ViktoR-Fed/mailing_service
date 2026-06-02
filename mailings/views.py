from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
)
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    ClientForm,
    CustomUserChangeForm,
    CustomUserCreationForm,
    MailingForm,
    MessageForm,
)
from .models import Client, Mailing, MailingAttempt, Message, User
from .services import send_mailing, update_mailing_statuses


def is_manager(user):
    """Проверка, является ли пользователь менеджером"""
    return user.has_perm("mailings.can_view_all_mailings")


def can_disable_mailings(user):
    """Проверка, может ли пользователь отключать рассылки"""
    return user.has_perm("mailings.can_disable_mailings")


# Представления для аутентификации
class UserRegistrationView(CreateView):
    """Регистрация нового пользователя"""

    form_class = CustomUserCreationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("mailings:index")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()

        # Отправка приветственного письма
        send_mail(
            subject="Добро пожаловать в сервис рассылок",
            message=f"Здравствуйте, {user.username}!\n\nВы успешно зарегистрировались в сервисе управления рассылками.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        # Автоматический вход после регистрации
        login(self.request, user)
        messages.success(self.request, "Регистрация прошла успешно!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Регистрация"
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    """Профиль пользователя"""

    model = User
    form_class = CustomUserChangeForm
    template_name = "registration/profile.html"
    success_url = reverse_lazy("mailings:index")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Профиль успешно обновлён")
        return super().form_valid(form)


class CustomLoginView(LoginView):
    """Кастомная страница входа"""

    template_name = "registration/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Вход в систему"
        return context


class CustomLogoutView(LogoutView):
    """Выход из системы"""

    next_page = "mailings:index"


class CustomPasswordResetView(PasswordResetView):
    """Восстановление пароля"""

    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("mailings:password_reset_done")


class IndexView(TemplateView):
    template_name = "mailings/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Кеширование статистики на 5 минут
        cache_key = "main_statistics"
        statistics = cache.get(cache_key)

        if statistics is None:
            update_mailing_statuses()

            if is_manager(self.request.user):
                # Менеджер видит все рассылки
                statistics = {
                    "total_mailings": Mailing.objects.count(),
                    "active_mailings": Mailing.objects.filter(
                        start_time__lte=timezone.now(),
                        end_time__gte=timezone.now(),
                        is_active=True,
                    ).count(),
                    "unique_clients": Client.objects.count(),
                    "completed_mailings": Mailing.objects.filter(
                        status=Mailing.STATUS_COMPLETED
                    ).count(),
                    "created_mailings": Mailing.objects.filter(
                        status=Mailing.STATUS_CREATED
                    ).count(),
                }
            else:
                # Обычный пользователь видит только свои рассылки
                statistics = {
                    "total_mailings": Mailing.objects.filter(
                        owner=self.request.user
                    ).count(),
                    "active_mailings": Mailing.objects.filter(
                        owner=self.request.user,
                        start_time__lte=timezone.now(),
                        end_time__gte=timezone.now(),
                        is_active=True,
                    ).count(),
                    "unique_clients": Client.objects.filter(
                        owner=self.request.user
                    ).count(),
                    "completed_mailings": Mailing.objects.filter(
                        owner=self.request.user, status=Mailing.STATUS_COMPLETED
                    ).count(),
                    "created_mailings": Mailing.objects.filter(
                        owner=self.request.user, status=Mailing.STATUS_CREATED
                    ).count(),
                }

            cache.set(cache_key, statistics, 300)  # Кеш на 5 минут

        context.update(statistics)
        return context


# Mixin для проверки владельца
class OwnerRequiredMixin(UserPassesTestMixin):
    """Проверяет, является ли пользователь владельцем объекта"""

    def test_func(self):
        obj = self.get_object()
        if is_manager(self.request.user):
            return True
        return hasattr(obj, "owner") and obj.owner == self.request.user

    def handle_no_permission(self):
        messages.error(self.request, "У вас нет прав для выполнения этого действия")
        return redirect("mailings:index")


# Представления для клиентов
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "mailings/client_list.html"
    context_object_name = "clients"

    def get_queryset(self):
        if is_manager(self.request.user):
            return Client.objects.all()
        return Client.objects.filter(owner=self.request.user)


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "mailings/client_form.html"
    success_url = reverse_lazy("mailings:client_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Клиент успешно добавлен")

        # Инвалидация кеша
        cache.delete("main_statistics")

        return super().form_valid(form)


class ClientUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "mailings/client_form.html"
    success_url = reverse_lazy("mailings:client_list")

    def form_valid(self, form):
        messages.success(self.request, "Клиент успешно обновлён")
        cache.delete("main_statistics")
        return super().form_valid(form)


class ClientDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Client
    template_name = "mailings/client_confirm_delete.html"
    success_url = reverse_lazy("mailings:client_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Клиент успешно удалён")
        cache.delete("main_statistics")
        return super().delete(request, *args, **kwargs)


# Представления для сообщений
class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = "mailings/message_list.html"
    context_object_name = "messages"

    def get_queryset(self):
        if is_manager(self.request.user):
            return Message.objects.all()
        return Message.objects.filter(owner=self.request.user)


class MessageCreateView(LoginRequiredMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = "mailings/message_form.html"
    success_url = reverse_lazy("mailings:message_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Сообщение успешно создано")
        return super().form_valid(form)


class MessageUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Message
    form_class = MessageForm
    template_name = "mailings/message_form.html"
    success_url = reverse_lazy("mailings:message_list")

    def form_valid(self, form):
        messages.success(self.request, "Сообщение успешно обновлено")
        return super().form_valid(form)


class MessageDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Message
    template_name = "mailings/message_confirm_delete.html"
    success_url = reverse_lazy("mailings:message_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Сообщение успешно удалено")
        return super().delete(request, *args, **kwargs)


# Представления для рассылок


class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = "mailings/mailing_list.html"
    context_object_name = "mailings"

    def get_queryset(self):
        update_mailing_statuses()
        if is_manager(self.request.user):
            return Mailing.objects.all().prefetch_related("message", "recipients")
        return Mailing.objects.filter(owner=self.request.user).prefetch_related(
            "message", "recipients"
        )


class MailingUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = "mailings/mailing_form.html"
    success_url = reverse_lazy("mailings:mailing_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Редактирование рассылки"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Рассылка успешно обновлена")
        cache.delete("main_statistics")
        return super().form_valid(form)


class MailingCreateView(LoginRequiredMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = "mailings/mailing_form.html"
    success_url = reverse_lazy("mailings:mailing_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Создание рассылки"
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Рассылка успешно создана")
        cache.delete("main_statistics")
        return super().form_valid(form)


class MailingDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Mailing
    template_name = "mailings/mailing_confirm_delete.html"
    success_url = reverse_lazy("mailings:mailing_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Рассылка успешно удалена")
        cache.delete("main_statistics")
        return super().delete(request, *args, **kwargs)


def mailing_detail(request, pk):
    """Детальный просмотр рассылки со статистикой"""
    mailing = get_object_or_404(Mailing, id=pk)

    # Проверка прав доступа
    if not is_manager(request.user) and mailing.owner != request.user:
        messages.error(request, "У вас нет прав для просмотра этой рассылки")
        return redirect("mailings:index")

    # Автоматическое обновление статуса
    mailing.update_status()

    # Кеширование статистики попыток
    cache_key = f"mailing_stats_{pk}"
    stats = cache.get(cache_key)

    if stats is None:
        attempts = mailing.attempts.all()
        stats = {
            "attempts": attempts,
            "success_attempts": attempts.filter(
                status=MailingAttempt.STATUS_SUCCESS
            ).count(),
            "failed_attempts": attempts.filter(
                status=MailingAttempt.STATUS_FAILED
            ).count(),
            "total_attempts": attempts.count(),
        }
        cache.set(cache_key, stats, 60)  # Кеш на 1 минуту

    context = {"mailing": mailing, **stats}

    return render(request, "mailings/mailing_detail.html", context)


@user_passes_test(is_manager)
def user_list_view(request):
    """Список пользователей (только для менеджеров)"""
    users = User.objects.all().prefetch_related("mailings")
    context = {
        "users": users,
    }
    return render(request, "mailings/user_list.html", context)


@user_passes_test(is_manager)
def toggle_user_active(request, user_id):
    """Блокировка/разблокировка пользователя (только для менеджеров)"""
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()

    status = "разблокирован" if user.is_active else "заблокирован"
    messages.success(request, f"Пользователь {user.username} {status}")

    return redirect("mailings:user_list")


@user_passes_test(can_disable_mailings)
def toggle_mailing_active(request, pk):
    """Отключение/включение рассылки (только для менеджеров)"""
    mailing = get_object_or_404(Mailing, id=pk)
    mailing.is_active = not mailing.is_active
    mailing.save()

    status = "активна" if mailing.is_active else "отключена"
    messages.success(request, f'Рассылка "{mailing.message.subject}" {status}')

    cache.delete("main_statistics")

    return redirect("mailings:mailing_detail", pk=pk)


def send_mailing_manual(request, pk):
    """Ручная отправка рассылки"""
    mailing = get_object_or_404(Mailing, id=pk)

    # Проверка прав доступа
    if not is_manager(request.user) and mailing.owner != request.user:
        messages.error(request, "У вас нет прав для отправки этой рассылки")
        return redirect("mailings:index")

    # Проверка возможности отправки
    if not mailing.can_send():
        messages.error(
            request,
            "Рассылка не может быть отправлена в данный момент. Проверьте дату и время.",
        )
        return redirect("mailings:mailing_detail", pk=pk)

    # Отправка рассылки
    success, total = send_mailing(mailing.id)

    # Инвалидация кеша
    cache.delete(f"mailing_stats_{pk}")
    cache.delete("main_statistics")

    if success == total:
        messages.success(
            request, f"Рассылка успешно отправлена. Отправлено: {success} из {total}"
        )
    else:
        messages.warning(
            request, f"Рассылка отправлена частично. Успешно: {success} из {total}"
        )

    return redirect("mailings:mailing_detail", pk=pk)


def user_statistics(request):
    """Статистика по рассылкам текущего пользователя"""
    if is_manager(request.user):
        mailings = Mailing.objects.all()
    else:
        mailings = Mailing.objects.filter(owner=request.user)

    total_mailings = mailings.count()
    total_attempts = MailingAttempt.objects.filter(mailing__in=mailings).count()
    success_attempts = MailingAttempt.objects.filter(
        mailing__in=mailings, status=MailingAttempt.STATUS_SUCCESS
    ).count()
    failed_attempts = total_attempts - success_attempts

    # Статистика по каждой рассылке
    mailing_stats = []
    for mailing in mailings:
        attempts = mailing.attempts.count()
        success = mailing.attempts.filter(status=MailingAttempt.STATUS_SUCCESS).count()
        mailing_stats.append(
            {
                "mailing": mailing,
                "total_attempts": attempts,
                "success": success,
                "failed": attempts - success,
            }
        )

    context = {
        "total_mailings": total_mailings,
        "total_attempts": total_attempts,
        "success_attempts": success_attempts,
        "failed_attempts": failed_attempts,
        "success_rate": (
            (success_attempts / total_attempts * 100) if total_attempts > 0 else 0
        ),
        "mailing_stats": mailing_stats,
    }

    return render(request, "mailings/user_statistics.html", context)
