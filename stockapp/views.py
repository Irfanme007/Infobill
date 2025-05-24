from django.shortcuts import render,redirect,get_object_or_404
from decimal import Decimal
from django.urls import reverse
import csv
from django.http import JsonResponse,HttpResponse
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .forms import AddproductForm,supplier_form
from django.contrib import messages
from django.db.models import Sum, Count,F
from .models import Products,PurchaseReports,PurchaseReturn,Suppliers,Tallyreport
import json
import re
from decimal import Decimal
from billingapp.models import Bill,BillItem,SalesReturn
from django.db.models import Q
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction


# Create your views here.

def LoginView(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_superuser:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Unauthorized access")
                return redirect('login')
        else:
            messages.error(request, "Invalid username or password")
    else:
        form = AuthenticationForm()
    return render(request, 'loginform.html', {'form': form})


@login_required
def supplier_management(request):
    if request.method == 'POST':
        form = supplier_form(request.POST)

        if form.is_valid():
            supplier = form.save()  # Save or update supplier
            return redirect('addproduct', supplier.supplier_name,supplier.supplier_gstin)  # ✅ Correct redirect

    else:
        form = supplier_form()

    return render(request, 'supplier_form.html', {'form': form})


@login_required
def fetch_supplier(request):
    if not request.user.is_superuser:
        return JsonResponse({'error':'Unauthorized'},status=403)
    
    phone=request.GET.get('supplier_phone','').strip()
    if not re.match(r'^\d{10}$', phone):  # Ensure it's a valid 10-digit number
        return JsonResponse({'error': 'Invalid phone number format'})
    
    try:
        supplier=Suppliers.objects.get(supplier_phone=phone)
        data={
            'exists':True,
            'name':supplier.supplier_name,
            'email':supplier.supplier_email,
            'address':supplier.supplier_address,
            'gstin':supplier.supplier_gstin,
            'supplier_id':supplier.id,
        }
    except Suppliers.DoesNotExist:
        data={'exists':False}
    return JsonResponse(data)

@login_required
def AddproductView(request, supplier_name, supplier_gstin):
    if request.method == 'POST':
        add_product_form = AddproductForm(request.POST)

        if add_product_form.is_valid():
            try:
                name = add_product_form.cleaned_data['name'].strip().upper()
                brand = add_product_form.cleaned_data['brand'].strip().upper()
                purchase_price = Decimal(add_product_form.cleaned_data['purchase_price'])
                gst = Decimal(add_product_form.cleaned_data['gst'])
                selling_price = Decimal(add_product_form.cleaned_data['selling_price'])
                description = add_product_form.cleaned_data['description']
                category = add_product_form.cleaned_data['category'].strip()
                quantity = add_product_form.cleaned_data['quantity']

                # ✅ Lookup supplier using both supplier name & GSTIN
                supplier = get_object_or_404(Suppliers, supplier_name=supplier_name, supplier_gstin=supplier_gstin)

                # ✅ Create Product
                product = Products.objects.create(
                    name=name,
                    brand=brand,
                    purchase_price=purchase_price,
                    selling_price=selling_price,
                    gst=gst,
                    description=description,
                    category=category,
                    stock=quantity,
                    supplier_name=supplier_name,
                    supplier_id=supplier.id
                )

                # ✅ Save purchase report with supplier name & GSTIN
                PurchaseReports.objects.create(
                    name=product.name,
                    brand=product.brand,
                    purchase_price=product.purchase_price,
                    selling_price=product.selling_price,
                    gst=product.gst,
                    description=product.description,
                    category=product.category,
                    stock=product.stock,
                    sku=product.sku,
                    supplier_name=supplier_name,
                    supplier_gstin=supplier_gstin  # Save GSTIN for accurate tracking
                )

                messages.success(request, f'New product "{product.name}" added with stock {product.stock}.', extra_tags='add_products')
                return redirect('stock-report')  # ✅ Redirect to stock report

            except Exception as e:
                print(e)  # Debugging
                messages.error(request, 'Some error occurred', extra_tags='add_products')

        else:
            messages.error(request, 'Some error happened while validating Form', extra_tags='add_products')

    else:
        add_product_form = AddproductForm()

    return render(request, 'addproduct.html', {'form': add_product_form, 'supplier_name': supplier_name, 'supplier_gstin': supplier_gstin})  # ✅ Pass supplier_gstin

@login_required
def purchase_report(request):
    """Fetch and filter purchase reports based on user input"""
    purchase = PurchaseReports.objects.all().order_by("purchase_date")  # Ensure consistent pagination order

    # Get filters from request
    search_query = request.GET.get('search', '').strip()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Apply search filtering
    if search_query:
        purchase = purchase.filter(
            Q(name__icontains=search_query) | 
            Q(brand__icontains=search_query) | 
            Q(sku__icontains=search_query) | 
            Q(category__icontains=search_query)
        )

    # Apply date filtering safely
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)

            purchase = purchase.filter(purchase_date__range=[start_date, end_date])
        except ValueError:
            pass  # Ignore invalid dates to prevent a crash

    # Pagination
    paginator = Paginator(purchase, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    purchase = paginator.get_page(page_number)
    total_qty = sum(purchased.stock for purchased in purchase)

    return render(request, "purchasereport.html", {"purchase": purchase, 'total_qty': total_qty})

@login_required
def export_csv_purchasereport(request):
    if not request.user.is_superuser:  # Only allow superusers to export
        return HttpResponse("Unauthorized", status=403)

    # Initialize CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_report.csv"'

    writer = csv.writer(response)
    # Write the header
    writer.writerow(['SKU', 'Name', 'Category', 'Brand', 'Description', 'Purchase Price', 'GST', 'Selling Price', 'Stock', 'Purchase Date'])

    # Fetch all purchase records
    purchases = PurchaseReports.objects.all()

    # Get filters from request
    search_query = request.GET.get('search', '').strip()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Apply search filtering
    if search_query:
        purchases = purchases.filter(
            Q(name__icontains=search_query) | 
            Q(brand__icontains=search_query) | 
            Q(sku__icontains=search_query) | 
            Q(category__icontains=search_query)
        )

    # Apply date filtering if both start_date and end_date are provided
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            purchases = purchases.filter(purchase_date__range=[start_date, end_date])
        except ValueError:
            pass  # Ignore invalid dates to prevent a crash

    # Write filtered data to CSV (without pagination)
    for purchase in purchases:
        writer.writerow([
            purchase.sku,
            purchase.name,
            purchase.category,
            purchase.brand,
            purchase.description,
            purchase.purchase_price,
            f"{purchase.gst}%",  # Format GST as percentage
            purchase.selling_price,
            purchase.stock,
            purchase.purchase_date.strftime("%Y-%m-%d")  # Format date
        ])

    return response


@login_required
def StockReport(request):
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort_by', 'newest')

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    products = Products.objects.filter(is_deleted=False)
    # Calculate total stock for filtered products
    total_qty = sum(product.stock for product in products)
    # Apply search filter
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(brand__icontains=query) |
            Q(sku__icontains=query)
        )

    # Apply date filter if provided
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            products = products.filter(purchase_date__gte=start_date)
        except ValueError:
            pass  # Invalid date format

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            products = products.filter(purchase_date__lte=end_date)
        except ValueError:
            pass  # Invalid date format

    # Apply sorting
    if sort_by == "newest":
        products = products.order_by('-purchase_date')
    elif sort_by == "oldest":
        products = products.order_by('purchase_date')

    # Pagination
    paginator = Paginator(products, 10)
    page = request.GET.get('page')
    products = paginator.get_page(page)



    return render(request, 'stockreport.html', {
        'products': products,
        'query': query,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'total_qty': total_qty
    })


@login_required
def export_csv_stockreport(request):
    if not request.user.is_superuser:
        return HttpResponse("Unauthorized", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_report.csv"'

    writer = csv.writer(response)
    # CSV Header
    writer.writerow(['SKU', 'Name', 'Category', 'Brand', 'Description', 'Purchase Price', 'GST', 'Selling Price', 'Stock', 'Purchase Date'])

    # Fetch all non-deleted stock records
    stock = Products.objects.filter(is_deleted=False).order_by('-purchase_date')

    # Get filters from request
    query = request.GET.get('q', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    gst = request.GET.get('gst', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    # Apply filters to stock records
    if query:
        stock = stock.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(brand__icontains=query) |
            Q(sku__icontains=query)
        )

    if min_price.isdigit():
        stock = stock.filter(purchase_price__gte=float(min_price))

    if max_price.isdigit():
        stock = stock.filter(purchase_price__lte=float(max_price))

    if gst.isdigit():
        stock = stock.filter(gst=int(gst))

    # Apply date filters
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            stock = stock.filter(purchase_date__gte=start_date)
        except ValueError:
            pass

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            stock = stock.filter(purchase_date__lte=end_date)
        except ValueError:
            pass

    # Write filtered stock to CSV
    for product in stock:
        writer.writerow([
            product.sku,
            product.name,
            product.category,
            product.brand,
            product.description,
            product.purchase_price,
            f"{product.gst}%",  # Format GST as percentage
            product.selling_price,
            product.stock,
            product.purchase_date.strftime("%Y-%m-%d")
        ])

    return response


@login_required
def purchase_return_view(request, sku):
    product = get_object_or_404(Products, sku=sku)

    
    if request.method == "POST":
        quantity = int(request.POST.get('quantity'))
        
        if quantity > product.stock:
            messages.error(request, "Return quantity exceeds stock.")
            return redirect('purchase-return', sku=sku)
        
        # Create the purchase return entry
        purchase_return = PurchaseReturn.objects.create(
            sku=product.sku,
            item_name=product.name,
            item_brand=product.brand,
            quantity=quantity,
            unit_price=product.purchase_price,
            total_price=product.purchase_price * quantity,
            supplier_name=product.supplier_name,
            supplier_id=product.supplier_id
            
        )
        
        # Reduce the stock in PurchaseReports
        product.stock -= quantity
        product.save()

        messages.success(request, f"{quantity} items returned successfully.")
        return redirect('stock-report')
    
    return redirect('stock-report')

@login_required
def purchase_return(request):
    query = request.GET.get('q', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    purchase_returns = PurchaseReturn.objects.all()

    # Filter by search query
    if query:
        purchase_returns = purchase_returns.filter(
            item_name__icontains=query
        ) | purchase_returns.filter(sku__icontains=query) | purchase_returns.filter(item_brand__icontains=query)
   
    
    # Filter by date range
    if start_date:
        purchase_returns = purchase_returns.filter(return_date__gte=start_date)
    if end_date:
        purchase_returns = purchase_returns.filter(return_date__lte=end_date)
    
    # Pagination
    paginator = Paginator(purchase_returns, 10)  # Show 10 returns per page
    page_number = request.GET.get('page')
    purchase_returns_page = paginator.get_page(page_number)
    total_qty = sum(returns.quantity for returns in purchase_returns_page)

    
    return render(request, "purchase_return.html", {
        "purchase_returns": purchase_returns_page,
        "total_qty": total_qty,
        "query": query,
        "start_date": start_date,
        "end_date": end_date,
    })


@login_required
def export_csv_purchase_return(request):
    if not request.user.is_superuser:
        return HttpResponse("Unauthorized", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_return_report.csv"'

    writer = csv.writer(response)
    # CSV Header
    writer.writerow(['SKU', 'Product Name', 'Brand', 'Quantity Returned', 'Unit Price', 'Total Price', 'Return Date', 'Supplier Name', 'Supplier ID'])

    # Fetch all purchase returns
    purchase_returns = PurchaseReturn.objects.all()

    # Get filters from request
    query = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    # Apply filters to purchase return records
    if query:
        purchase_returns = purchase_returns.filter(
            Q(item_name__icontains=query) |
            Q(sku__icontains=query) |
            Q(item_brand__icontains=query)
        )

    # Apply date filters
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            purchase_returns = purchase_returns.filter(return_date__gte=start_date)
        except ValueError:
            pass

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            purchase_returns = purchase_returns.filter(return_date__lte=end_date)
        except ValueError:
            pass

    # Write filtered purchase returns to CSV
    for return_item in purchase_returns:
        writer.writerow([
            return_item.sku,
            return_item.item_name,
            return_item.item_brand if return_item.item_brand else "N/A",  # Handling optional brand field
            return_item.quantity,
            f"₹{return_item.unit_price:.2f}",  # Format the unit price as currency
            f"₹{return_item.total_price:.2f}",  # Format the total price as currency
            return_item.return_date.strftime("%Y-%m-%d"),  # Format the return date
            return_item.supplier_name,
            return_item.supplier_id
        ])

    return response


@login_required
def purchase_return_invoice(request, id):
    # Retrieve the specific return using the ID
    purchase_return = get_object_or_404(PurchaseReturn, pk=id)
    supplier=get_object_or_404(Suppliers,id=purchase_return.supplier_id)
    # Render the invoice template with the purchase return details
    return render(request, 'purchase_return_invoice.html', {'purchase_return': purchase_return,'supplier':supplier})


@login_required
def DeletePurchaseReport(request,sku):
    # Fetch the product using the provided product_id
    product = get_object_or_404(PurchaseReports,sku=sku)
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to delete purchase reports.")
        return redirect('purchase-report')
    product.delete()
    messages.success(request, "Purchase report deleted successfully.")

    return redirect('purchase-report')

@login_required
def DashBoard(request):
    today = datetime.today()
    current_year = today.year

    # Total Sales (Current Year)
    total_sales = (
        Bill.objects.filter(sales_date__year=current_year)
        .aggregate(total=Sum("net_total"))["total"] or 0
    )

    # Total Stock (No need to filter by year)
    total_stock = Products.objects.aggregate(total=Sum("stock"))["total"] or 0

    # Top 5 Selling Products (Current Year)
    top_products = (
        BillItem.objects.filter(bill__sales_date__year=current_year)
        .values("item_name")
        .annotate(quantity=Sum("quantity"))
        .order_by("-quantity")[:5]
    )

    # Low Stock Products (Stock < 5)
    low_stock_products = Products.objects.filter(stock__lt=5)

    # Sales by Month (Current Year)
    sales_trend = []
    for i in range(1, 12 + 1):
        month_sales = (
            Bill.objects.filter(sales_date__year=current_year, sales_date__month=i)
            .aggregate(total=Sum("net_total"))["total"] or Decimal(0)
        )
        sales_trend.append(float(month_sales))  # Convert Decimal to float

    # Monthly Sales (Selected Month of Current Year)
    selected_month = int(request.GET.get("month", today.month))
    monthly_sales = (
        Bill.objects.filter(sales_date__year=current_year, sales_date__month=selected_month)
        .aggregate(total=Sum("net_total"))["total"] or 0
    )

    # Month Dropdown List
    months = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]

    context = {
        "total_sales": total_sales,
        "total_stock": total_stock,
        "top_products": top_products,
        "low_stock_products": low_stock_products,
        "sales_trend": json.dumps(sales_trend),
        "monthly_sales": monthly_sales,
        "months": months,
        "selected_month": selected_month,
        "year":current_year,
    }

    return render(request, "dashboard.html", context)

@login_required
def generate_tally_report(request):
    today = timezone.now().date()

    # Fetch data for today
    total_purchases = PurchaseReports.objects.filter(purchase_date__date=today).aggregate(Sum('stock'))['stock__sum'] or 0
    total_purchase_returns = PurchaseReturn.objects.filter(return_date__date=today).aggregate(Sum('quantity'))['quantity__sum'] or 0
    total_sales_quantity = BillItem.objects.filter(bill__sales_date__date=today).aggregate(Sum('quantity'))['quantity__sum'] or 0
    total_sales_return = SalesReturn.objects.filter(return_date__date=today).aggregate(Sum('quantity'))['quantity__sum'] or 0
    actual_closing_stock = Products.objects.aggregate(Sum('stock'))['stock__sum'] or 0

    # Get last tally closing stock as opening stock
    last_tally = Tallyreport.objects.last()
    opening_stock = last_tally.closing_stock if last_tally else 0

    # Compute expected closing stock
    print(total_purchases,total_purchase_returns,total_sales_quantity,total_sales_return)
    computed_closing_stock = opening_stock + total_purchases - total_purchase_returns - total_sales_quantity + total_sales_return

    return JsonResponse({
        'opening_stock': opening_stock,
        'total_purchases': total_purchases,
        'total_purchase_returns': total_purchase_returns,
        'total_sales_quantity': total_sales_quantity,
        'total_sales_return': total_sales_return,
        'computed_closing_stock': computed_closing_stock,
        'actual_closing_stock': actual_closing_stock
    })

@login_required
def TallyReport(request):
    """Fetch and display tally reports with optional date filtering."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    reports = Tallyreport.objects.all().order_by('-id')

    if start_date and end_date:
        reports = reports.filter(created_at__date__range=[start_date, end_date])

    return render(request, 'tally_report.html', {'reports': reports})
    

@login_required
@require_POST
def save_tally_report(request):
    try:
        data = json.loads(request.body)  # Read JSON data

        # Validate stock
        computed_stock = (
            int(data['opening_stock']) + int(data['total_purchases']) -
            int(data['total_purchase_returns']) - int(data['total_sales_quantity']) +
            int(data['total_sales_return'])
        )

        if computed_stock != int(data['closing_stock']):
            return JsonResponse({'error': 'Stock mismatch! Cannot save tally report.'}, status=400)

        # Save tally report if everything matches
        Tallyreport.objects.create(
            opening_stock=data['opening_stock'],
            total_purchases=data['total_purchases'],
            total_purchase_returns=data['total_purchase_returns'],
            total_sales_quantity=data['total_sales_quantity'],
            total_sales_return=data['total_sales_return'],
            closing_stock=data['closing_stock']
        )

        return JsonResponse({'success': 'Tally report saved successfully!'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid data format!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Error saving tally report: {str(e)}'}, status=500)
    

@login_required
def supplier_details(request):
    suppliers=Suppliers.objects.all()
    return render(request,'suppliers.html',{'suppliers':suppliers})


def Logoutview(request):
    request.session.flush()  # Clears all session data
    request.session.cycle_key()  # Generates a new session key to prevent session fixation attacks
    cache.clear()
    logout(request)
    return redirect('login')


