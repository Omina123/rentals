from django.shortcuts import render,redirect
from django.conf import settings
from .models import *
from django.contrib import messages
from django.db import IntegrityError
from decimal import Decimal
# Create your views here.
def home(request):
    return render(request, "index.html")
from django.shortcuts import render
from django.db.models import Sum, Count
from .models import Property, Unit, Lease, RentPayment
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    # 1. Total Properties owned or managed by this user
    # Adjust filtering based on whether the user is a Landlord ('2') or Manager ('3')
    if request.user.user_type == '2':
        properties = Property.objects.filter(owner=request.user)
    else:
        properties = Property.objects.filter(manager=request.user)

    total_properties = properties.count()

    # 2. Total Tenants (Active Leases associated with those properties)
    active_leases = Lease.objects.filter(unit__property__in=properties, is_active=True)
    total_tenants = active_leases.values('tenant').distinct().count()

    # 3. Monthly Revenue (Total paid this month)
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    monthly_revenue = RentPayment.objects.filter(
        lease__unit__property__in=properties,
        last_payment_date__month=current_month,
        last_payment_date__year=current_year
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0

    # 4. Pending Rent (Sum of amount_due - amount_paid for unpaid bills)
    # We calculate the difference between due and paid for all non-paid statuses
    pending_data = RentPayment.objects.filter(
        lease__unit__property__in=properties,
        status__in=['pending', 'partially_paid', 'overdue']
    )
    
    # Logic: Sum(due) - Sum(paid)
    total_due = pending_data.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    total_paid_towards_pending = pending_data.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    pending_rent = total_due - total_paid_towards_pending

    # 5. Recent Payments Table
    recent_payments = RentPayment.objects.filter(
        lease__unit__property__in=properties
    ).order_by('-last_payment_date')[:10]

    context = {
        'total_properties': total_properties,
        'total_tenants': total_tenants,
        'monthly_revenue': monthly_revenue,
        'pending_rent': pending_rent,
        'recent_payments': recent_payments,
    }
    return render(request, "dashboard.html", context)
def Tenans(request):
    return render(request, "tenant.html")

def about(request):
    return render(request, "about.html")
def contact(request):
    return render(request, "contact.html")
# views.py
def property_list(request):
    # Ensure this filter matches exactly how you saved it
    properties = Property.objects.filter(owner=request.user) 
    
    # Debugging tip: Print this to your terminal to see if anything exists
    print(f"DEBUG: Found {properties.count()} properties for {request.user.username}")
    
    return render(request, 'property_list.html', {'properties': properties})

def add_property(request):
    # if request.user.user_type not in ['1', '2']: # Only Admin or Landlord
    #     messages.error(request, "Unauthorized.")
    #     return redirect('property_list')

    if request.method == "POST":
        try:
            Property.objects.create(
                name=request.POST.get('name'),
                location=request.POST.get('location'),
                owner=request.user, # Automatically assign to the logged-in landlord
                # manager assignment logic can go here
            )
            messages.success(request, "Property successfully added to your portfolio!")
            return redirect('property_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'add_property.html')
def lease_list(request):
    # This view lists all active contracts so you can trigger billing
    leases = Lease.objects.filter(is_active=True).select_related('tenant', 'unit')
    return render(request, 'lease_list.html', {'leases': leases})
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Property, Unit

def unit_manager(request, property_id):
    property_obj = get_object_or_404(Property, id=property_id)
    units = property_obj.units.all().order_by('unit_number')
    return render(request, 'unit_manager.html', {
        'property': property_obj, 
        'units': units
    })

def add_unit_ajax(request, property_id):
    if request.method == "POST":
        property_obj = get_object_or_404(Property, id=property_id)
        # Architect Tip: Validate data before saving
        unit_number = request.POST.get('unit_number')
        rent = request.POST.get('rent_amount')
        deposit = request.POST.get('deposit_amount')

        unit = Unit.objects.create(
            property=property_obj,
            unit_number=unit_number,
            rent_amount=rent,
            deposit_amount=deposit
        )
        return JsonResponse({
            "status": "success",
            "unit_id": unit.id,
            "unit_number": unit.unit_number,
            "rent": str(unit.rent_amount)
        })
    return JsonResponse({"status": "error"}, status=400)
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Unit, Lease

def vacate_unit(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)
    
    # 1. Find the active lease
    # Assuming is_active is a field or we check for leases without end_dates
    active_lease = Lease.objects.filter(unit=unit, is_active=True).first()
    
    if active_lease:
        # 2. Close the lease
        active_lease.is_active = False
        active_lease.end_date = timezone.now().date()
        active_lease.save()
        
        # 3. Make unit available
        unit.is_occupied = False
        unit.save()
        
        messages.success(request, f"Unit {unit.unit_number} is now vacant and available.")
    else:
        messages.error(request, "No active lease found for this unit.")
        
    return redirect('unit_manager', property_id=unit.property.id)
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.contrib import messages
from .models import Unit, Lease
from Users.models import CustomUser
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from .models import Unit, Tenant, Lease

def activate_lease(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)
    
    # 1. Validation: Prevent leasing an occupied unit
    if unit.is_occupied:
        messages.error(request, f"Unit {unit.unit_number} is already occupied.")
        return redirect('unit_manager', property_id=unit.property.id)

    if request.method == "POST":
        try:
            with transaction.atomic():
                tenant_id = request.POST.get('tenant')
                tenant = get_object_or_404(Tenant, id=tenant_id)
                
                # Create the Lease record
                Lease.objects.create(
                    tenant=tenant,
                    unit=unit,
                    start_date=request.POST.get('start_date'),
                    end_date=request.POST.get('end_date') or None,
                    agreed_rent=request.POST.get('agreed_rent'),
                    agreed_deposit=request.POST.get('agreed_deposit'),
                    is_active=True
                )
                
                # 2. IMPORTANT: Update unit status so it shows as occupied
                unit.is_occupied = True
                unit.save()
                
            messages.success(request, f"Lease activated successfully for {tenant.full_name}!")
            return redirect('unit_manager', property_id=unit.property.id)
            
        except Exception as e:
            messages.error(request, f"Activation Error: {str(e)}")
            return redirect('activate_lease', unit_id=unit.id)

    # Context for the GET request
    tenants = Tenant.objects.all().order_by('full_name')
    return render(request, 'activate_lease.html', {
        'unit': unit, 
        'tenants': tenants
    })
# def activate_lease(request, unit_id):
    # unit = get_object_or_404(Unit, id=unit_id)
    # 
    # Architect Check: Don't allow leasing an occupied unit
    # if unit.is_occupied:
        # messages.error(request, "This unit is already occupied by an active lease.")
        # return redirect('unit_manager', property_id=unit.property.id)
# 
    # if request.method == "POST":
        # try:
            # with transaction.atomic():
                # tenant_id = request.POST.get('tenant')
                # tenant = get_object_or_404(Tenant, id=tenant_id)
                # 
                # lease = Lease.objects.create(
                    # tenant=tenant,
                    # unit=unit,
                    # start_date=request.POST.get('start_date'),
                    # end_date=request.POST.get('end_date') or None,
                    # agreed_rent=request.POST.get('agreed_rent'),
                    # agreed_deposit=request.POST.get('agreed_deposit'),
                    # is_active=True
                # )
                # 
            # messages.success(request, f"Lease activated for {tenant.get_full_name()}!")
            # return redirect('unit_manager', property_id=unit.property.id)
        # except Exception as e:
            # messages.error(request, f"Activation Error: {str(e)}")
# 
    # tenants = Tenant.objects.all() # Tenants only
    # return render(request, 'activate_lease.html', {
        # 'unit': unit, 
        # 'tenants': tenants
    # })
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import RentPayment
from django.contrib import messages
@login_required(login_url='Login')
def payment_ledger(request, lease_id=None):
    # If lease_id is provided, show specific; else show all for the property manager
    if lease_id:
        payments = RentPayment.objects.filter(lease_id=lease_id).order_by('-due_date')
    else:
        payments = RentPayment.objects.all().order_by('-due_date')
    
    return render(request, 'payment_ledger.html', {'payments': payments})
def payment_ledgers(request, lease_id=None):
    # .select_related() joins the tables in SQL for better performance
    base_query = RentPayment.objects.select_related('lease__tenant', 'lease__unit').order_by('-due_date')
    
    if lease_id:
        payments = base_query.filter(lease_id=lease_id)
    else:
        payments = base_query.all()
    
    return render(request, 'payment_ledger.html', {'payments': payments})
from django.contrib import messages
from decimal import Decimal  # Import this at the top

def process_payment(request, payment_id):
    payment = get_object_or_404(RentPayment, id=payment_id)
    
    if request.method == 'POST':
        ref_code = request.POST.get('ref_code')
        
        # Change float() to Decimal()
        try:
            amount_str = request.POST.get('amount_to_add', '0')
            amount = Decimal(amount_str) 
        except (ValueError, TypeError, InvalidOperation):
            amount = Decimal('0.00')

        try:
            # Now both sides are Decimals, so += will work
            payment.amount_paid += amount

            # UPDATE STATUS LOGIC
            if payment.amount_paid >= payment.amount_due:
                payment.status = 'paid'
            elif payment.amount_paid > 0:
                payment.status = 'partially_paid'
            else:
                payment.status = 'pending'

            payment.reference_code = ref_code
            payment.save()

            messages.success(request, f"Successfully added KES {amount} to payment.")
            return redirect('payment_ledger')

        except IntegrityError:
            messages.error(request, f"The reference code '{ref_code}' has already been used.")
            return redirect(request.META.get('HTTP_REFERER', 'payment_ledger'))

def payments(request):
    # Fetch all payments, ordered by most recent due date
    payments = RentPayment.objects.all().order_by('-due_date')
    
    # Calculate global stats for the header
    total_due = sum(p.amount_due for p in payments)
    total_collected = sum(p.amount_paid for p in payments)
    
    context = {
        'payments': payments,
        'total_due': total_due,
        'total_collected': total_collected,
        'outstanding': total_due - total_collected
    }
    return render(request, 'payment.html', context)


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Lease, RentPayment
from django.utils import timezone

def create_monthly_bill(request, lease_id):
    """
    Manually trigger a billing entry for a specific lease.
    In a production system, this would eventually be a 'celery' cron job.
    """
    lease = get_object_or_404(Lease, id=lease_id)
    
    if request.method == "POST":
        billing_date_str = request.POST.get('billing_month') # Format YYYY-MM-DD
        due_date_str = request.POST.get('due_date')
        
        # Check if a bill already exists for this lease in this specific month
        # to prevent double-billing.
        billing_date = timezone.datetime.strptime(billing_date_str, '%Y-%m-%d').date()
        exists = RentPayment.objects.filter(
            lease=lease, 
            billing_month__month=billing_date.month, 
            billing_month__year=billing_date.year
        ).exists()

        if exists:
            messages.error(request, f"A bill for {billing_date.strftime('%B %Y')} already exists for this tenant.")
        else:
            RentPayment.objects.create(
                lease=lease,
                billing_month=billing_date,
                amount_due=lease.agreed_rent,
                due_date=due_date_str,
                status='pending'
            )
            messages.success(request, f"Invoice generated for {lease.unit.unit_number}.")
            
        return redirect('payment_ledger')
    
    return render(request, 'create_bill.html', {'lease': lease})
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .models import Lease, RentPayment

def record_payment(request, lease_id):
    lease = get_object_or_404(Lease, id=lease_id)
    
    if request.method == "POST":
        amount = request.POST.get('amount')
        reference = request.POST.get('reference')
        
        # We use .create() with the exact field names from your model
        payment = RentPayment.objects.create(
            lease=lease,
            amount_due=lease.agreed_rent, # Using lease rent as the bill amount
            amount_paid=amount,
            billing_month=timezone.now().date().replace(day=1), # Sets to first of current month
            due_date=timezone.now().date(),
            last_payment_date=timezone.now(), # Matches your model field
            status='paid'
        )

        # Only save reference_code if it was provided to avoid Unique constraint errors
        if reference:
            payment.reference_code = reference
            payment.save()
            
        return redirect('payment_ledger')
    
    return render(request, 'record_payment_form.html', {'lease': lease})
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Tenant

from django.core.exceptions import ValidationError

def create_tenant(request):
    if request.method == 'POST':
        name = request.POST.get('full_name')
        phone = request.POST.get('phone_number')
        national_id = request.POST.get('id_number')

        if Tenant.objects.filter(phone_number=phone).exists():
            messages.error(request, f"Phone number {phone} is already registered.")
            return render(request, 'create_tenant.html') # Stay on page to show error

        try:
            # We use full_clean() because .create() doesn't always trigger 
            # model validators automatically in some Django setups
            new_tenant = Tenant(
                full_name=name,
                phone_number=phone,
                id_number=national_id
            )
            new_tenant.full_clean() # This triggers the Kenya Phone/ID validators
            new_tenant.save()
            
            messages.success(request, f"Tenant {new_tenant.full_name} added successfully!")
            return redirect('tenant_list') 
            
        except ValidationError as e:
            # This captures the "Invalid Kenyan Number" message from your model
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")
            
    return render(request, 'create_tenant.html')