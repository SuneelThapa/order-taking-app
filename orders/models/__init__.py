# Import order matters — dependencies must come before dependants.

# No external order-model dependencies
from .tenant import *
from .referral_source import *
from .product_type import *

# Depends on referral_source
from .client import *

# Depends on CustomUser (external)
from .staff_profile import *

# Depends on client, tenant
from .order import *

# All depend on order
from .cancellation_record import *
from .delivery import *
from .payment import *
from .client_signature import *
from .scratch_note import *
from .client_photo import *

# Depends on order, product_type
from .order_item import *

# Depends on order, CustomUser
from .order_staff import *

# Depends on client, CustomUser
from .email_log import *

# Measurement base — depends on order_item
from .base_measurement import *

# Abstract mixins (no concrete table)
from .upper_body import *
from .lower_body import *

# Concrete measurement models — depend on base_measurement + mixins
from .jacket import *
from .shirt import *
from .pants import *
from .shorts import *
from .skirt import *
from .vest import *
from .coat import *
from .suit import *
from .dress import *
from .blouse import *
from .no_measurement import *
from .shoes import *
from .belt import *

# Item photos — depends on order_item
from .order_item_photo import *

# ── Production bill models ──────────────────────────────
# No external dependencies
from .target_item import *
from .variation_type import *

# Depends on ProductType
from .fabric_zone import *

# Depends on OrderItem, VariationType, VariationOption, FabricZone
from .production_bill import *