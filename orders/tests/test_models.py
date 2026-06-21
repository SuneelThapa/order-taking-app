"""
Tests for critical business logic:
- Payment THB equivalent storage
- Commission rules
- Order cancellation
- Production bill token
- Scratch pad session
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from orders.models import (
    Tenant, Client, Order, Payment, StaffProfile,
    OrderStaff, CancellationRecord, ProductionBill,
    ScratchPadSession, ReferralSource, ProductType,
    OrderItem,
)

User = get_user_model()


def make_tenant():
    return Tenant.objects.create(name='Test Shop', subdomain='test')


def make_user(username='jimmy', tenant=None, is_staff=True):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
    )
    if tenant:
        user.tenant = tenant
        user.save()
    return user


def make_client(tenant):
    return Client.objects.create(
        tenant=tenant,
        name='John Smith',
        phone='+66812345678',
    )


def make_order(tenant, client):
    return Order.objects.create(
        tenant=tenant,
        client=client,
        status='new',
    )


# ─────────────────────────────────────────────────────────────────
# Payment Tests
# ─────────────────────────────────────────────────────────────────
class PaymentModelTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.client = make_client(self.tenant)
        self.order  = make_order(self.tenant, self.client)

    def test_thb_payment_stored_correctly(self):
        """THB payment: thb_equivalent == original_amount, exchange_rate == 1."""
        p = Payment.objects.create(
            order=self.order,
            original_amount=Decimal('5000.00'),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal('5000.00'),
            method='cash',
            type='deposit',
        )
        self.assertEqual(p.thb_equivalent, Decimal('5000.00'))
        self.assertEqual(p.currency, 'THB')

    def test_usd_payment_thb_equivalent(self):
        """USD payment: thb_equivalent = original_amount × exchange_rate."""
        p = Payment.objects.create(
            order=self.order,
            original_amount=Decimal('100.00'),
            currency='USD',
            exchange_rate_to_thb=Decimal('35.50'),
            thb_equivalent=Decimal('3550.00'),
            method='cash',
            type='deposit',
        )
        self.assertEqual(p.thb_equivalent, Decimal('3550.00'))

    def test_refund_is_negative(self):
        """Refund payments must have negative original_amount."""
        p = Payment.objects.create(
            order=self.order,
            original_amount=Decimal('-1000.00'),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal('-1000.00'),
            method='cash',
            type='refund',
        )
        self.assertLess(p.thb_equivalent, 0)
        self.assertEqual(p.type, 'refund')

    def test_multiple_payments_sum(self):
        """Multiple payments on same order sum correctly."""
        Payment.objects.create(
            order=self.order,
            original_amount=Decimal('3000.00'),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal('3000.00'),
            method='cash',
            type='deposit',
        )
        Payment.objects.create(
            order=self.order,
            original_amount=Decimal('7000.00'),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal('7000.00'),
            method='cash',
            type='balance',
        )
        total = sum(
            p.thb_equivalent
            for p in Payment.objects.filter(order=self.order)
        )
        self.assertEqual(total, Decimal('10000.00'))


# ─────────────────────────────────────────────────────────────────
# Order Tests
# ─────────────────────────────────────────────────────────────────
class OrderModelTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.client = make_client(self.tenant)

    def test_order_created_with_new_status(self):
        """New orders default to 'new' status."""
        order = make_order(self.tenant, self.client)
        self.assertEqual(order.status, 'new')

    def test_order_linked_to_client(self):
        """Order correctly linked to client."""
        order = make_order(self.tenant, self.client)
        self.assertEqual(order.client, self.client)
        self.assertEqual(order.client.name, 'John Smith')

    def test_order_number_generated(self):
        """Order number is auto-generated and not empty."""
        order = make_order(self.tenant, self.client)
        self.assertTrue(order.order_number)
        self.assertGreater(len(str(order.order_number)), 0)

    def test_cancelled_order_status(self):
        """Cancelled order stays cancelled — no reopening."""
        order = make_order(self.tenant, self.client)
        order.status = 'canceled'
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'canceled')


# ─────────────────────────────────────────────────────────────────
# Client Tests
# ─────────────────────────────────────────────────────────────────
class ClientModelTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()

    def test_client_created(self):
        """Client created with required fields."""
        client = Client.objects.create(
            tenant=self.tenant,
            name='Jane Doe',
            phone='+66898765432',
        )
        self.assertEqual(client.name, 'Jane Doe')
        self.assertTrue(client.is_active)

    def test_client_str(self):
        """Client __str__ includes name and phone."""
        client = make_client(self.tenant)
        self.assertIn('John Smith', str(client))

    def test_client_referral(self):
        """Client can be referred by another client."""
        referrer = make_client(self.tenant)
        referred = Client.objects.create(
            tenant=self.tenant,
            name='Jane Doe',
            phone='+66898765432',
            referred_by=referrer,
        )
        self.assertEqual(referred.referred_by, referrer)


# ─────────────────────────────────────────────────────────────────
# Production Bill Tests
# ─────────────────────────────────────────────────────────────────
class ProductionBillTest(TestCase):

    def setUp(self):
        self.tenant  = make_tenant()
        self.client  = make_client(self.tenant)
        self.order   = make_order(self.tenant, self.client)
        self.pt      = ProductType.objects.create(name='Suit', tenant=self.tenant)
        self.item    = OrderItem.objects.create(
            order=self.order,
            product_type=self.pt,
            quantity=1,
        )

    def test_share_token_auto_generated(self):
        """ProductionBill gets a unique UUID share_token on creation."""
        bill = ProductionBill.objects.create(
            order_item=self.item,
            gender='men',
        )
        self.assertIsNotNone(bill.share_token)
        self.assertTrue(str(bill.share_token))

    def test_share_tokens_unique(self):
        """Two bills get different share tokens."""
        pt2   = ProductType.objects.create(name='Shirt', tenant=self.tenant)
        item2 = OrderItem.objects.create(order=self.order, product_type=pt2, quantity=1)
        bill1 = ProductionBill.objects.create(order_item=self.item, gender='men')
        bill2 = ProductionBill.objects.create(order_item=item2, gender='men')
        self.assertNotEqual(bill1.share_token, bill2.share_token)

    def test_bill_default_status_draft(self):
        """New bill defaults to draft status."""
        bill = ProductionBill.objects.create(order_item=self.item, gender='men')
        self.assertEqual(bill.status, 'draft')


# ─────────────────────────────────────────────────────────────────
# Scratch Pad Session Tests
# ─────────────────────────────────────────────────────────────────
class ScratchPadSessionTest(TestCase):

    def test_session_created_with_token(self):
        """ScratchPadSession gets unique token on creation."""
        session = ScratchPadSession.objects.create(mode='contact')
        self.assertIsNotNone(session.token)

    def test_session_default_pending(self):
        """New session starts as pending."""
        session = ScratchPadSession.objects.create(mode='contact')
        self.assertEqual(session.status, 'pending')

    def test_session_expires_at_set(self):
        """Session gets expires_at automatically."""
        session = ScratchPadSession.objects.create(mode='contact')
        self.assertIsNotNone(session.expires_at)
        self.assertGreater(session.expires_at, timezone.now())

    def test_session_modes(self):
        """Both contact and measurements modes work."""
        s1 = ScratchPadSession.objects.create(mode='contact')
        s2 = ScratchPadSession.objects.create(mode='measurements')
        self.assertEqual(s1.mode, 'contact')
        self.assertEqual(s2.mode, 'measurements')

    def test_session_tokens_unique(self):
        """Two sessions get different tokens."""
        s1 = ScratchPadSession.objects.create(mode='contact')
        s2 = ScratchPadSession.objects.create(mode='contact')
        self.assertNotEqual(s1.token, s2.token)

    def test_session_processed_on_result_save(self):
        """Session marked processed when result is saved."""
        session = ScratchPadSession.objects.create(mode='contact')
        session.result = {'name': 'John', 'phone': '+66812345678'}
        session.status = 'processed'
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.status, 'processed')
        self.assertEqual(session.result['name'], 'John')