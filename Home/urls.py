from django.contrib import admin
from django.urls import path, include
from Home import views

urlpatterns = [
    path('', views.home, name="home"),
    path('about/', views.about, name="about"), 
    path('contact/', views.contact, name="contact"), 
    path('dashboard/', views.dashboard, name="dashboard"),
    path('tenants/', views.Tenans, name="tenants"),
    path('property_list/', views.property_list, name="property_list"),
    path('add_property/', views.add_property, name="add_property"),
   # Unit Management (Hierarchical)
    path('property/<int:property_id>/units/', views.unit_manager, name='unit_manager'),
    path('property/<int:property_id>/units/add-ajax/', views.add_unit_ajax, name='add_unit_ajax'),
    path('unit/<int:unit_id>/activate-lease/', views.activate_lease, name='activate_lease'),
    path('payments/', views.payments, name='payments'),
    path('lease/<int:lease_id>/create-bill/', views.create_monthly_bill, name='create_monthly_bill'),
    
    # Action Endpoint (POST only)
    path('payment/process/<int:payment_id>/', views.process_payment, name='process_payment'),
    path('lease_list/', views.lease_list, name='lease_list'),
    path('ledger/', views.payment_ledgers, name='payment_ledger'),
    path('lease/<int:lease_id>/pay/', views.record_payment, name='record_payment'),
    path('unit/<int:unit_id>/vacate/', views.vacate_unit, name='vacate_unit'),
    path('create_tenant/', views.create_tenant, name='create_tenant'),
    ]