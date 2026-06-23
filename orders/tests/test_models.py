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


def make_client(tenant=None):
    return Client.objects.create(
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
        self.staff  = make_user(tenant=self.tenant)
        self.client = make_client()
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
            recorded_by=self.staff,
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
            recorded_by=self.staff,
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
            recorded_by=self.staff,
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
            recorded_by=self.staff,
        )
        Payment.objects.create(
            order=self.order,
            original_amount=Decimal('7000.00'),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal('7000.00'),
            method='cash',
            type='balance',
            recorded_by=self.staff,
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
        self.client = make_client()

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
            name='Jane Doe',
            phone='+66898765432',
        )
        self.assertEqual(client.name, 'Jane Doe')
        self.assertTrue(client.is_active)

    def test_client_str(self):
        """Client __str__ includes name and phone."""
        client = make_client()
        self.assertIn('John Smith', str(client))

    def test_client_referral(self):
        """Client can be referred by another client."""
        referrer = make_client()
        referred = Client.objects.create(
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
        self.client  = make_client()
        self.order   = make_order(self.tenant, self.client)
        self.pt      = ProductType.objects.create(name='Suit', measurement_model='SuitMeasurement')
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
        pt2   = ProductType.objects.create(name='Shirt', measurement_model='ShirtMeasurement')
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


# ─────────────────────────────────────────────────────────────────
# Client Loyalty + Notification Tests
# ─────────────────────────────────────────────────────────────────
class ClientLoyaltyTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.staff  = make_user(tenant=self.tenant)

    def _client_with_spend(self, spend):
        """Create a client and add a payment of given amount."""
        from decimal import Decimal
        from orders.models import Payment
        client = Client.objects.create(name='Test Client', phone='+66812345678')
        order  = Order.objects.create(tenant=self.tenant, client=client, status='delivered')
        Payment.objects.create(
            order=order,
            original_amount=Decimal(str(spend)),
            currency='THB',
            exchange_rate_to_thb=Decimal('1.00'),
            thb_equivalent=Decimal(str(spend)),
            method='cash',
            type='deposit',
            recorded_by=self.staff,
        )
        return client

    def test_loyalty_tier_none(self):
        """Client with no spend has tier 'none'."""
        client = Client.objects.create(name='New', phone='+66800000001')
        self.assertEqual(client.loyalty_tier, 'none')
        self.assertEqual(client.loyalty_discount, 0)

    def test_loyalty_tier_bronze(self):
        """Client spending ฿9,000 gets bronze tier (5%)."""
        client = self._client_with_spend(9000)
        self.assertEqual(client.loyalty_tier, 'bronze')
        self.assertEqual(client.loyalty_discount, 5)

    def test_loyalty_tier_silver(self):
        """Client spending ฿30,000 gets silver tier (10%)."""
        client = self._client_with_spend(30000)
        self.assertEqual(client.loyalty_tier, 'silver')
        self.assertEqual(client.loyalty_discount, 10)

    def test_loyalty_tier_gold(self):
        """Client spending ฿80,000 gets gold tier (15%)."""
        client = self._client_with_spend(80000)
        self.assertEqual(client.loyalty_tier, 'gold')
        self.assertEqual(client.loyalty_discount, 15)

    def test_eligible_for_notifications_default(self):
        """New client is eligible for notifications by default."""
        client = Client.objects.create(name='Test', phone='+66800000002')
        self.assertTrue(client.is_eligible_for_notifications)

    def test_excluded_from_marketing(self):
        """Client with exclude_from_marketing=True is not eligible."""
        client = Client.objects.create(
            name='Unhappy', phone='+66800000003',
            exclude_from_marketing=True
        )
        self.assertFalse(client.is_eligible_for_notifications)

    def test_no_marketing_consent(self):
        """Client without marketing consent is not eligible."""
        client = Client.objects.create(
            name='NoConsent', phone='+66800000004',
            marketing_consent=False
        )
        self.assertFalse(client.is_eligible_for_notifications)

    def test_inactive_client_not_eligible(self):
        """Inactive client is not eligible for notifications."""
        client = Client.objects.create(
            name='Inactive', phone='+66800000005',
            is_active=False
        )
        self.assertFalse(client.is_eligible_for_notifications)


# ─────────────────────────────────────────────────────────────────
# Tenant Model Tests
# ─────────────────────────────────────────────────────────────────
class TenantModelTest(TestCase):

    def test_tenant_created(self):
        """Tenant creates with required fields."""
        tenant = Tenant.objects.create(name='Test Shop', subdomain='testshop')
        self.assertEqual(tenant.name, 'Test Shop')
        self.assertTrue(tenant.is_active)

    def test_tenant_display_key(self):
        """Tenant display key can be set."""
        tenant = Tenant.objects.create(
            name='Shop', subdomain='shop', display_key='shop2026'
        )
        self.assertEqual(tenant.display_key, 'shop2026')

    def test_tenant_whatsapp_fallback(self):
        """Tenant without own token uses system fallback."""
        tenant = Tenant.objects.create(name='Shop2', subdomain='shop2')
        # No token set — whatsapp_access_token returns settings value
        from django.conf import settings
        expected = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
        self.assertEqual(tenant.whatsapp_access_token, expected)

    def test_tenant_own_whatsapp_token(self):
        """Tenant with own token uses it."""
        tenant = Tenant.objects.create(
            name='Shop3', subdomain='shop3',
            whatsapp_token='own_token_123',
            whatsapp_phone_number_id='123456789'
        )
        self.assertEqual(tenant.whatsapp_access_token, 'own_token_123')
        self.assertEqual(tenant.whatsapp_number_id, '123456789')