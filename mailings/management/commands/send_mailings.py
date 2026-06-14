from django.core.management.base import BaseCommand

from mailings.models import Mailing
from mailings.services import send_mailing, update_mailing_statuses


class Command(BaseCommand):
    help = "Отправляет все активные рассылки"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mailing-id", type=int, help="ID конкретной рассылки для отправки"
        )

    def handle(self, *args, **options):
        # Сначала обновляем статусы
        update_mailing_statuses()

        mailing_id = options.get("mailing_id")

        if mailing_id:
            # Отправляем конкретную рассылку
            self.stdout.write(f"Отправка рассылки #{mailing_id}...")
            success, total = send_mailing(mailing_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Рассылка #{mailing_id} отправлена. Успешно: {success} из {total}"
                )
            )
        else:
            # Отправляем все активные рассылки
            mailings = Mailing.objects.filter(status=Mailing.STATUS_STARTED)
            self.stdout.write(f"Найдено активных рассылок: {mailings.count()}")

            for mailing in mailings:
                self.stdout.write(f"Отправка рассылки #{mailing.id}...")
                success, total = send_mailing(mailing.id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Рассылка #{mailing.id} отправлена. Успешно: {success} из {total}"
                    )
                )
