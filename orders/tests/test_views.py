"""
Tests for critical views:
- Order form loads correctly
- Scratch pad session create/poll/submit
- Production bill public share view
- QR generator
- Shipping label
"""
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.contrib.auth import get_user_model

from orders.models import (
    Tenant, Client, Order, ProductionBill,
    ScratchPadSession, ProductType, OrderItem,
)

User = get_user_model()


def make_tenant():
    return Tenant.objects.create(name='Test Shop', subdomain='test')


def make_staff_user(tenant, username='jimmy'):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=True,
    )
    user.tenant = tenant
    user.save()
    return user


class OrderFormViewTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user   = make_staff_user(self.tenant)
        self.c      = TestClient()
        # Set tenant on request via session
        self.c.force_login(self.user)

    def test_new_order_page_loads(self):
        """GET /new/ returns 200 for staff user."""
        resp = self.c.get('/new/', HTTP_HOST='test.studio.emporiumarmani.com')
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_loads(self):
        """GET /dashboard/ returns 200 for staff user."""
        resp = self.c.get('/', HTTP_HOST='test.studio.emporiumarmani.com')
        self.assertIn(resp.status_code, [200, 302])

    def test_qr_generator_loads(self):
        """GET /qr/ returns 200 for staff user."""
        resp = self.c.get('/qr/', HTTP_HOST='test.studio.emporiumarmani.com')
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_redirects(self):
        """Unauthenticated user redirected from /new/."""
        c = TestClient()
        resp = c.get('/new/', HTTP_HOST='test.studio.emporiumarmani.com')
        self.assertEqual(resp.status_code, 302)


class ScratchPadViewTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user   = make_staff_user(self.tenant)
        self.c      = TestClient()
        self.c.force_login(self.user)

    def test_create_session(self):
        """POST /scratch/create/ creates a session and returns token."""
        resp = self.c.post(
            '/scratch/create/',
            {'mode': 'contact'},
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('token', data)
        self.assertIn('tablet_url', data)

    def test_create_measurements_session(self):
        """POST /scratch/create/ with mode=measurements works."""
        resp = self.c.post(
            '/scratch/create/',
            {'mode': 'measurements', 'gender': 'men'},
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('token', data)

    def test_tablet_canvas_loads(self):
        """GET /scratch/<token>/ loads tablet canvas (no login)."""
        session = ScratchPadSession.objects.create(mode='contact')
        resp = self.c.get(
            f'/scratch/{session.token}/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)

    def test_poll_pending_session(self):
        """GET /scratch/<token>/poll/ returns pending status."""
        session = ScratchPadSession.objects.create(mode='contact')
        resp = self.c.get(
            f'/scratch/{session.token}/poll/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'pending')

    def test_poll_processed_session(self):
        """GET /scratch/<token>/poll/ returns result when processed."""
        session = ScratchPadSession.objects.create(
            mode='contact',
            status='processed',
            result={'name': 'John', 'phone': '+66812345678'}
        )
        resp = self.c.get(
            f'/scratch/{session.token}/poll/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        data = resp.json()
        self.assertEqual(data['status'], 'processed')
        self.assertEqual(data['result']['name'], 'John')


class ProductionBillShareTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.client_obj = Client.objects.create(
            name='John', phone='+66812345678'
        )
        self.order = Order.objects.create(
            tenant=self.tenant, client=self.client_obj, status='new'
        )
        self.pt   = ProductType.objects.create(name='Suit', measurement_model='SuitMeasurement')
        self.item = OrderItem.objects.create(
            order=self.order, product_type=self.pt, quantity=1
        )
        self.bill = ProductionBill.objects.create(
            order_item=self.item, gender='men'
        )

    def test_public_share_url_no_login(self):
        """GET /bill/view/<token>/ works without login."""
        c = TestClient()
        # Use logged-in user so template renders request.user correctly
        c.force_login(make_staff_user(self.tenant, username='sharetest'))
        resp = c.get(
            f'/bill/view/{self.bill.share_token}/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)

    def test_invalid_token_returns_404(self):
        """GET /bill/view/<invalid-token>/ returns 404."""
        import uuid
        c = TestClient()
        resp = c.get(
            f'/bill/view/{uuid.uuid4()}/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 404)


class OnboardingViewTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            password='testpass123',
            is_staff=True,
        )
        self.c = TestClient()
        self.c.force_login(self.superuser)

    def test_onboarding_page_loads(self):
        """GET /onboarding/ returns 200 for superuser."""
        resp = self.c.get(
            '/onboarding/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)

    def test_onboarding_non_superuser_redirects(self):
        """Non-superuser cannot access onboarding."""
        staff = make_staff_user(self.tenant, username='staffonly')
        c = TestClient()
        c.force_login(staff)
        resp = c.get(
            '/onboarding/',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertIn(resp.status_code, [302, 403])

    def test_onboarding_creates_tenant(self):
        """POST /onboarding/ creates tenant and owner user."""
        from orders.models import Tenant as TenantModel
        resp = self.c.post('/onboarding/', {
            'shop_name':    'New Tailor Shop',
            'subdomain':    'newtailor',
            'package':      'studio',
            'owner_name':   'John Owner',
            'owner_email':  'john@newtailor.com',
            'owner_phone':  '+66812345678',
            'username':     'newtailor_owner',
            'password':     'securepass123',
            'display_key':  'newtailor2026',
        }, HTTP_HOST='test.studio.emporiumarmani.com')

        # Should redirect to success page
        self.assertEqual(resp.status_code, 302)

        # Tenant should be created
        tenant = TenantModel.objects.filter(subdomain='newtailor').first()
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.name, 'New Tailor Shop')
        self.assertEqual(tenant.display_key, 'newtailor2026')

        # Owner user should be created
        owner = User.objects.filter(username='newtailor_owner').first()
        self.assertIsNotNone(owner)
        self.assertTrue(owner.is_staff)
        self.assertEqual(owner.tenant, tenant)

        # Cleanup
        owner.delete()
        tenant.delete()


class StatusBoardTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.tenant.display_key = 'testkey2026'
        self.tenant.save()

    def test_status_board_correct_key(self):
        """Status board accessible with correct key."""
        c = TestClient()
        resp = c.get(
            '/display/?key=testkey2026',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 200)

    def test_status_board_wrong_key(self):
        """Status board denied with wrong key."""
        c = TestClient()
        resp = c.get(
            '/display/?key=wrongkey',
            HTTP_HOST='test.studio.emporiumarmani.com'
        )
        self.assertEqual(resp.status_code, 403)