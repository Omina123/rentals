import uuid
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

# --- KENYAN VALIDATORS ---
# Supports: Safaricom (070-072, 074, 079, 011) and Airtel (073, 075, 078, 010)
kenya_phone_validator = RegexValidator(
    regex=r'^(?:254|\+254|0)?((7(?:[01249][0-9]|3[0-9]|5[0-7]|8[0-9])|1(?:1[0-5]|0[0-2]))[0-9]{6})$',
    message="Enter a valid Kenyan phone number (Safaricom or Airtel)."
)

kenya_id_validator = RegexValidator(
    regex=r'^\d{7,8}$',
    message="Enter a valid 7 or 8-digit Kenyan ID number."
)

# --- NEW TENANT MODEL (NO LOGIN REQUIRED) ---
class Tenant(models.Model):
    """
    Direct model for tenants added manually by the admin.
    """
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(
        max_length=15, 
        validators=[kenya_phone_validator], 
        unique=True,
        help_text="Primary number for SMS rent alerts"
    )
    id_number = models.CharField(
        max_length=8, 
        validators=[kenya_id_validator], 
        unique=True
    )
    date_registered = models.DateTimeField(auto_now_add=True)

    # Inside class Lease:
    def __str__(self):
        return f"{self.tenant.full_name} - Unit {self.unit.unit_number}"


class Property(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        limit_choices_to={'user_type': '2'},
        related_name='owned_properties'
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_properties', 
        limit_choices_to={'user_type': '3'}
    )

    class Meta:
        verbose_name_plural = "Properties"

    def __str__(self):
        return self.name


class Unit(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=20)
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.property.name} - Unit {self.unit_number}"


class Lease(models.Model):
    # Now links to the simple Tenant model instead of AUTH_USER_MODEL
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leases')
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='leases')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    agreed_rent = models.DecimalField(max_digits=12, decimal_places=2)
    agreed_deposit = models.DecimalField(max_digits=12, decimal_places=2)

    def clean(self):
        if self.is_active and self.unit.is_occupied and not self.pk:
            active_lease = Lease.objects.filter(unit=self.unit, is_active=True).exists()
            if active_lease:
                raise ValidationError(f"Unit {self.unit.unit_number} is already occupied.")

    def save(self, *args, **kwargs):
        if self.is_active:
            self.unit.is_occupied = True
        else:
            other_active = Lease.objects.filter(unit=self.unit, is_active=True).exclude(pk=self.pk).exists()
            self.unit.is_occupied = other_active
        
        self.unit.save()
        super().save(*args, **kwargs)

    # Inside class Lease:
    def __str__(self):
        return f"{self.tenant.full_name} - Unit {self.unit.unit_number}"


class RentPayment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='payments')
    billing_month = models.DateField(help_text="The month this rent covers")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_date = models.DateField()
    last_payment_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Reference code is now a simple field so the Admin can type M-PESA codes
    reference_code = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Enter M-PESA or Bank Transaction Reference"
    )

    def update_status(self):
        if self.amount_paid >= self.amount_due:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partially_paid'
        elif self.due_date < timezone.now().date():
            self.status = 'overdue'
        self.save()

    def __str__(self):
        return f"Rent {self.billing_month.strftime('%B %Y')} - {self.lease.tenant.full_name}"