from django.urls import path
from .views import dashboard, orders_table, order_delete, order_detail, order_edit, load_measurement_form


app_name = 'orders'


urlpatterns = [
    
    path('', dashboard, name='dashboard'),
    path("orders-table/", orders_table, name="orders_table"),

    path("<int:pk>/", order_detail, name="order_detail"),
    path("<int:pk>/edit/", order_edit, name="order_edit"),
    path("<int:pk>/delete/", order_delete, name="order_delete"),

    path(
        "load-measurement-form/",
        load_measurement_form,
        name="load_measurement_form",
    ),

   
]
