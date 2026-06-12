from django.urls import path
from .views import (
    dashboard, stat_cards, orders_table,
    order_detail, order_delete,
    order_quick_status, order_add_payment,
    client_search, client_create_inline,
    order_form_view, order_item_row,
    payment_row, load_measurement_form,
)

app_name = "orders"

urlpatterns = [
    path("",                        dashboard,             name="dashboard"),
    path("cards/",                  stat_cards,            name="stat_cards"),
    path("orders-table/",           orders_table,          name="orders_table"),
    path("new/",                    order_form_view,       name="order_add"),
    path("<int:pk>/edit/",          order_form_view,       name="order_edit"),
    path("<int:pk>/detail/",        order_detail,          name="order_detail"),
    path("<int:pk>/delete/",        order_delete,          name="order_delete"),
    path("<int:pk>/quick-status/",  order_quick_status,    name="order_quick_status"),
    path("<int:pk>/add-payment/",   order_add_payment,     name="order_add_payment"),
    path("client/search/",          client_search,         name="client_search"),
    path("client/create-inline/",   client_create_inline,  name="client_create_inline"),
    path("item-row/",               order_item_row,        name="order_item_row"),
    path("payment-row/",            payment_row,           name="payment_row"),
    path("load-measurement-form/",  load_measurement_form, name="load_measurement_form"),
]