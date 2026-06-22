"""
orders/management/commands/send_notifications.py
Run daily via cron: python manage.py send_notifications

Handles:
- Fitting reminders (1 day before)
- 3-month return messages
- 6-month return messages with discount
- Birthday greetings
"""
import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from orders.models import Client, Order
from notifications.whatsapp import (
    notify_fitting_reminder,
    notify_fitting_reminder_3hr,
    notify_return_3_months,
    notify_return_6_months,
    notify_birthday,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send automated WhatsApp notifications to eligible clients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print who would receive notifications without sending',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today   = date.today()
        now     = timezone.now()

        if dry_run:
            self.stdout.write('=== DRY RUN — no messages sent ===')

        self._send_fitting_reminders(today, dry_run)
        self._send_fitting_reminders_3hr(now, dry_run)
        self._send_return_3_months(today, dry_run)
        self._send_return_6_months(today, dry_run)
        self._send_birthdays(today, dry_run)

        self.stdout.write(self.style.SUCCESS('Notifications complete.'))

    def _send_fitting_reminders(self, today, dry_run):
        """Send reminder 1 day before fitting."""
        tomorrow = today + timedelta(days=1)
        orders = Order.objects.filter(
            fitting_date=tomorrow,
            status__in=['new', 'pending', 'processing'],
            client__is_active=True,
            client__marketing_consent=True,
            client__exclude_from_marketing=False,
        ).select_related('client')

        for order in orders:
            self.stdout.write(f'[FITTING] {order.client.name} — {order.order_number}')
            if not dry_run:
                notify_fitting_reminder(order.client, order)

    def _send_fitting_reminders_3hr(self, now, dry_run):
        """Send reminder 3 hours before fitting time."""
        from datetime import datetime, timezone as dt_timezone

        # Target window: fittings happening in 3h ± 15 minutes
        target      = now + timedelta(hours=3)
        window_from = target - timedelta(minutes=15)
        window_to   = target + timedelta(minutes=15)

        orders = Order.objects.filter(
            fitting_date=target.date(),
            fitting_time__isnull=False,
            status__in=['new', 'pending', 'processing'],
            client__is_active=True,
            client__marketing_consent=True,
            client__exclude_from_marketing=False,
        ).select_related('client')

        for order in orders:
            if not order.fitting_time:
                continue
            fitting_dt = datetime.combine(
                order.fitting_date,
                order.fitting_time,
            ).replace(tzinfo=dt_timezone.utc)
            if window_from <= fitting_dt <= window_to:
                self.stdout.write(
                    f'[3HR FITTING] {order.client.name} — {order.order_number} at {order.fitting_time}'
                )
                if not dry_run:
                    notify_fitting_reminder_3hr(order.client, order)

        for order in orders:
            self.stdout.write(f'[FITTING] {order.client.name} — {order.order_number}')
            if not dry_run:
                notify_fitting_reminder(order.client, order)

    def _send_return_3_months(self, today, dry_run):
        """Send 3-month return message to clients whose last delivery was 3 months ago."""
        target_date = today - timedelta(days=90)
        clients = self._clients_last_delivered_on(target_date)
        for client in clients:
            self.stdout.write(f'[3 MONTHS] {client.name}')
            if not dry_run:
                notify_return_3_months(client)

    def _send_return_6_months(self, today, dry_run):
        """Send 6-month return message with loyalty discount."""
        target_date = today - timedelta(days=180)
        clients = self._clients_last_delivered_on(target_date)
        for client in clients:
            self.stdout.write(f'[6 MONTHS] {client.name} — {client.loyalty_tier} ({client.loyalty_discount}%)')
            if not dry_run:
                notify_return_6_months(client)

    def _send_birthdays(self, today, dry_run):
        """Send birthday message to clients whose birthday is today."""
        clients = Client.objects.filter(
            is_active=True,
            marketing_consent=True,
            exclude_from_marketing=False,
            birthday__month=today.month,
            birthday__day=today.day,
        )
        for client in clients:
            self.stdout.write(f'[BIRTHDAY] {client.name}')
            if not dry_run:
                notify_birthday(client)

    def _clients_last_delivered_on(self, target_date):
        """Return eligible clients whose most recent delivered order was on target_date."""
        return Client.objects.filter(
            is_active=True,
            marketing_consent=True,
            exclude_from_marketing=False,
            orders__status='delivered',
            orders__delivery_date=target_date,
        ).distinct()