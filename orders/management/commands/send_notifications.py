"""
orders/management/commands/send_notifications.py
Run hourly via cron: python manage.py send_notifications

Handles:
- Fitting reminders (1 day before, and 3 hours before)
- 3-month return messages
- 6-month return messages with loyalty discount
- Birthday greetings

3/6-month return logic:
  Uses delivery_date if set, otherwise falls back to created_at.date()
  (covers backfilled orders from a physical book that have no recorded
  delivery date - they are treated as "added today" rather than guessed).

  Uses a THRESHOLD check (days_since >= 90 / >= 180), not an exact-day
  match, and tracks return_3mo_notified_at / return_6mo_notified_at on
  the Order so each order is only ever notified once - even very old
  backfilled orders are caught and notified on the very next run,
  instead of silently waiting for the exact matching day.

  Multiple qualifying orders for the same client in the same run are
  deduplicated so the client only receives ONE 3-month and ONE 6-month
  message per run, but every qualifying order flag is still marked
  so none of them get notified again later.
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
            self.stdout.write('=== DRY RUN -- no messages sent ===')

        self._send_fitting_reminders(today, dry_run)
        self._send_fitting_reminders_3hr(now, dry_run)
        self._send_return_3_months(today, now, dry_run)
        self._send_return_6_months(today, now, dry_run)
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
            self.stdout.write(f'[FITTING] {order.client.name} -- {order.order_number}')
            if not dry_run:
                notify_fitting_reminder(order.client, order)

    def _send_fitting_reminders_3hr(self, now, dry_run):
        """Send reminder 3 hours before fitting time."""
        from datetime import datetime, timezone as dt_timezone

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
                    f'[3HR FITTING] {order.client.name} -- {order.order_number} at {order.fitting_time}'
                )
                if not dry_run:
                    notify_fitting_reminder_3hr(order.client, order)

    def _eligible_orders_for_return_reminder(self, threshold_days, notified_field, today):
        """
        Orders that are at least threshold_days old (by delivery_date,
        falling back to created_at.date() when delivery_date is blank)
        and have not yet had the given reminder sent.
        """
        cutoff = today - timedelta(days=threshold_days)
        filter_kwargs = {f'{notified_field}__isnull': True}
        return (
            Order.objects.filter(
                status='delivered',
                client__is_active=True,
                client__marketing_consent=True,
                client__exclude_from_marketing=False,
                **filter_kwargs,
            )
            .filter(
                Q(delivery_date__isnull=False, delivery_date__lte=cutoff) |
                Q(delivery_date__isnull=True, created_at__date__lte=cutoff)
            )
            .select_related('client')
            .order_by('client_id', '-delivery_date', '-created_at')
        )

    def _send_return_3_months(self, today, now, dry_run):
        """Send 3-month return message -- at least 90 days since delivery (or creation if no delivery date)."""
        orders = self._eligible_orders_for_return_reminder(90, 'return_3mo_notified_at', today)
        notified_client_ids = set()
        matched_order_ids   = []

        for order in orders:
            matched_order_ids.append(order.pk)
            if order.client_id in notified_client_ids:
                continue
            notified_client_ids.add(order.client_id)
            ref_date = order.delivery_date or order.created_at.date()
            self.stdout.write(
                f'[3 MONTHS] {order.client.name} -- {order.order_number} (ref date: {ref_date})'
            )
            if not dry_run:
                notify_return_3_months(order.client)

        if not dry_run and matched_order_ids:
            Order.objects.filter(pk__in=matched_order_ids).update(return_3mo_notified_at=now)

    def _send_return_6_months(self, today, now, dry_run):
        """Send 6-month return message with loyalty discount -- at least 180 days since delivery (or creation)."""
        orders = self._eligible_orders_for_return_reminder(180, 'return_6mo_notified_at', today)
        notified_client_ids = set()
        matched_order_ids   = []

        for order in orders:
            matched_order_ids.append(order.pk)
            if order.client_id in notified_client_ids:
                continue
            notified_client_ids.add(order.client_id)
            ref_date = order.delivery_date or order.created_at.date()
            self.stdout.write(
                f'[6 MONTHS] {order.client.name} -- {order.client.loyalty_tier} '
                f'({order.client.loyalty_discount}%) (ref date: {ref_date})'
            )
            if not dry_run:
                notify_return_6_months(order.client)

        if not dry_run and matched_order_ids:
            Order.objects.filter(pk__in=matched_order_ids).update(return_6mo_notified_at=now)

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
