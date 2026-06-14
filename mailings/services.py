import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import Mailing, MailingAttempt

logger = logging.getLogger(__name__)


def send_mailing(mailing_id):
    """
    Отправка рассылки по её ID с использованием batch-вставки попыток
    Возвращает tuple (успешно_писем, всего_писем)
    """
    try:
        mailing = Mailing.objects.get(id=mailing_id)
    except Mailing.DoesNotExist:
        logger.error(f"Рассылка #{mailing_id} не найдена")
        return 0, 0

    # Проверяем, можно ли отправить рассылку
    if not mailing.can_send():
        logger.warning(
            f"Рассылка #{mailing_id} не может быть отправлена (is_active={mailing.is_active()})"
        )
        return 0, 0

    recipients = mailing.recipients.all()
    total_count = recipients.count()

    # Список для batch-создания попыток
    attempts_to_create = []
    success_count = 0

    for recipient in recipients:
        try:
            # Отправка письма
            result = send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False,
            )

            if result:
                success_count += 1
                attempts_to_create.append(
                    MailingAttempt(
                        status=MailingAttempt.STATUS_SUCCESS,
                        server_response="Письмо успешно отправлено",
                        mailing=mailing,
                    )
                )
                logger.info(f"Письмо успешно отправлено на {recipient.email}")
            else:
                attempts_to_create.append(
                    MailingAttempt(
                        status=MailingAttempt.STATUS_FAILED,
                        server_response="Ошибка отправки письма",
                        mailing=mailing,
                    )
                )
                logger.error(f"Ошибка отправки письма на {recipient.email}")

        except Exception as e:
            attempts_to_create.append(
                MailingAttempt(
                    status=MailingAttempt.STATUS_FAILED,
                    server_response=str(e)[:500],
                    mailing=mailing,
                )
            )
            logger.error(f"Исключение при отправке на {recipient.email}: {e}")

    # Batch-создание попыток (одна операция в БД)
    if attempts_to_create:
        with transaction.atomic():
            MailingAttempt.objects.bulk_create(attempts_to_create)

    # Обновляем статус рассылки, если время окончания прошло
    if timezone.now() > mailing.end_datetime:
        mailing.update_status()

    return success_count, total_count


def update_mailing_statuses():
    """Обновляет статусы всех рассылок"""
    mailings = Mailing.objects.all()
    updated_count = 0

    for mailing in mailings:
        if mailing.update_status():
            updated_count += 1

    if updated_count > 0:
        logger.info(f"Обновлено статусов рассылок: {updated_count}")

    return updated_count


def generate_email_verification_token(user):
    """Генерирует токен для подтверждения email"""
    return default_token_generator.make_token(user)


def send_verification_email(user, request):
    """Отправляет письмо с ссылкой для подтверждения email"""
    token = generate_email_verification_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    verification_url = request.build_absolute_uri(
        reverse("mailings:verify_email", kwargs={"uidb64": uid, "token": token})
    )

    subject = "Подтверждение email - Сервис рассылок"
    message = f"""
    Здравствуйте, {user.username}!

    Для завершения регистрации и подтверждения вашего email адреса, пожалуйста, перейдите по ссылке:

    {verification_url}

    Если вы не регистрировались на нашем сервисе, просто проигнорируйте это письмо.

    С уважением,
    Команда сервиса рассылок
    """

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify_email_token(user, token):
    """Проверяет токен подтверждения email"""
    return default_token_generator.check_token(user, token)
