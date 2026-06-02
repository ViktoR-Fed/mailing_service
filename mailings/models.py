from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Модель пользователя с дополнительными полями
    """

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="mailings_user_set",  # Уникальное имя
        blank=True,
        verbose_name="groups",
        help_text="The groups this user belongs to.",
    )

    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="mailings_user_set",  # Уникальное имя
        blank=True,
        verbose_name="user permissions",
        help_text="Specific permissions for this user.",
    )

    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Номер телефона должен быть в формате: '+79991234567' (до 15 цифр)",
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        verbose_name="Номер телефона",
    )
    avatar = models.ImageField(
        upload_to="avatars/", blank=True, null=True, verbose_name="Аватар"
    )
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")
    blocked_at = models.DateTimeField(
        blank=True, null=True, verbose_name="Дата блокировки"
    )
    email_verified = models.BooleanField(
        default=False, verbose_name="Email подтверждён"
    )
    email_verification_token = models.CharField(
        max_length=100, blank=True, verbose_name="Токен верификации email"
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        permissions = [
            ("can_view_all_users", "Может просматривать всех пользователей"),
            ("can_block_users", "Может блокировать пользователей"),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    def block(self):
        """Блокировка пользователя"""
        if not self.is_blocked:
            self.is_blocked = True
            self.blocked_at = timezone.now()
            self.save()

    def unblock(self):
        """Разблокировка пользователя"""
        if self.is_blocked:
            self.is_blocked = False
            self.blocked_at = None
            self.save()

    @property
    def is_active(self):
        """Переопределение is_active с учётом блокировки"""
        return super().is_active and not self.is_blocked


class Client(models.Model):
    """Модель получателя рассылки"""

    email = models.EmailField(unique=True, verbose_name="Email")
    full_name = models.CharField(max_length=255, verbose_name="Фамилия Имя Отчество")
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clients",
        verbose_name="Владелец",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Получатель"
        verbose_name_plural = "Получатели"
        ordering = ["full_name"]
        permissions = [
            ("can_view_all_clients", "Может просматривать всех клиентов"),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class Message(models.Model):
    """Модель сообщения для рассылки"""

    subject = models.CharField(max_length=255, verbose_name="Тема письма")
    body = models.TextField(verbose_name="Тело письма")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Владелец",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        permissions = [
            ("can_view_all_messages", "Может просматривать все сообщения"),
        ]

    def __str__(self):
        return self.subject


class Mailing(models.Model):
    """Модель рассылки"""

    STATUS_CREATED = "created"
    STATUS_STARTED = "started"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Создана"),
        (STATUS_STARTED, "Запущена"),
        (STATUS_COMPLETED, "Завершена"),
    ]

    start_datetime = models.DateTimeField(verbose_name="Дата и время первой отправки")
    end_datetime = models.DateTimeField(verbose_name="Дата и время окончания отправки")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
        verbose_name="Статус",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="mailings",
        verbose_name="Получатели",
    )
    recipients = models.ManyToManyField(
        Client, related_name="mailings", verbose_name="Получатели"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mailings",
        verbose_name="Владелец",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-start_datetime"]
        permissions = [
            ("can_view_all_mailings", "Может просматривать все рассылки"),
            ("can_disable_mailings", "Может отключать рассылки"),
        ]

    def __str__(self):
        return f"Рассылка #{self.id} - {self.message.subject}"

    def is_active(self):
        """Проверяет, активна ли рассылка"""
        now = timezone.now()
        return self.status == self.STATUS_STARTED and now <= self.end_datetime

    def update_status(self):
        """Обновляет статус рассылки на основе текущего времени"""
        now = timezone.now()
        new_status = self._calculate_status(now)

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=["status"])
            return True
        return False

    def _calculate_status(self, now):
        """Вычисляет статус на основе времени"""
        if now < self.start_datetime:
            return self.STATUS_CREATED
        elif now <= self.end_datetime:
            return self.STATUS_STARTED
        else:
            return self.STATUS_COMPLETED

    def can_send(self):
        """Проверяет, можно ли отправить рассылку"""
        now = timezone.now()
        return self.is_active and self.start_datetime <= now <= self.end_datetime

    def clean(self):
        """Валидация модели"""
        if (
            self.start_datetime
            and self.end_datetime
            and self.start_datetime >= self.end_datetime
        ):
            raise ValidationError("Дата окончания должна быть позже даты начала")

        if self.start_datetime and self.start_datetime < timezone.now():
            raise ValidationError("Дата начала не может быть в прошлом")


class MailingAttempt(models.Model):
    """Модель попытки рассылки"""

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Успешно"),
        (STATUS_FAILED, "Не успешно"),
    ]

    attempt_datetime = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата и время попытки"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, verbose_name="Статус"
    )
    server_response = models.TextField(
        blank=True, verbose_name="Ответ почтового сервера"
    )
    mailing = models.ForeignKey(
        Mailing,
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name="Рассылка",
    )

    class Meta:
        verbose_name = "Попытка рассылки"
        verbose_name_plural = "Попытки рассылки"
        ordering = ["-attempt_datetime"]

    def __str__(self):
        return f"Попытка #{self.id} - {self.get_status_display()}"
