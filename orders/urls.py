from django.urls import path

from .views import (
    dashboard,
    stat_cards,
    orders_table,
    order_detail,
    order_delete,
    order_form_view,
    order_item_row,
    load_measurement_form,
)

app_name = "orders"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("cards/", stat_cards, name="stat_cards"),
    path("orders-table/", orders_table, name="orders_table"),

    path("new/", order_form_view, name="order_add"),
    path("<int:pk>/edit/", order_form_view, name="order_edit"),
    path("<int:pk>/detail/", order_detail, name="order_detail"),
    path("<int:pk>/delete/", order_delete, name="order_delete"),

    path("item-row/", order_item_row, name="order_item_row"),
    path("load-measurement-form/", load_measurement_form, name="load_measurement_form"),
]