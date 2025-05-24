from django.shortcuts import render, redirect,get_object_or_404
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
from django.db.models import Q
from django.db import transaction,IntegrityError
import csv
import re
from django.http import JsonResponse,HttpResponse
from .forms import CustomerForm,BillItemForm,BillForm
from .models import Customers,Bill,BillItem,SalesReturn
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from stockapp.models import Products
from django.contrib.auth.decorators import login_required
from django.urls import reverse
import json
from django.utils.dateparse import parse_datetime

from decimal import Decimal,InvalidOperation
from django.db.models import Sum

# view to save,update and to show empty form
@login_required
def customer_management(request):
    if request.method=='POST':
        form=CustomerForm(request.POST)
        if form.is_valid():
            customer=form.save()
            print('customer saved')
            return redirect('product-selection',customer_id=customer.id)
    
    else:
        form=CustomerForm()
    return render(request,'customerform.html',{'form':form})

# AJAX for fetching customer details automatically

@login_required
def fetch_customer(request):
    if not request.user.is_superuser:  # Restrict access to superuser
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    phone = request.GET.get('phone', '').strip()

    if not re.match(r'^\d{10}$', phone):  # Ensure it's a valid 10-digit number
        return JsonResponse({'error': 'Invalid phone number format'})

    try:
        customer = Customers.objects.get(phone=phone)
        data = {
            'exists': True,
            'name': customer.name,
            'email': customer.email,
            'address': customer.address,
            'customer_id': customer.id,
        }
    except Customers.DoesNotExist:
        data = {'exists': False}

    return JsonResponse(data)


@login_required
def search_product(request):
    query=request.GET.get('query','').strip()
    print({query})

    if not query:
        return JsonResponse({'error':'no query provided'})
    
    products=Products.objects.filter(name__icontains=query,stock__gt=0)[:5]

    product_list=[]
    for p in products:
        product_dict={
            "id":p.id,
            'name':p.name,
            'brand':p.brand,
            'price':float(p.selling_price),
            'gst':float(p.gst),
            'stock':p.stock,
            'sku':p.sku,
        }
        product_list.append(product_dict)
        print('productdisctionary:',product_dict)
    return JsonResponse({"products":product_list})

@login_required
def SelectProduct(request,customer_id):
    customer=get_object_or_404(Customers,id=customer_id)
    print(customer.name)

    bill_form = BillForm()
    bill_item_form = BillItemForm()
    return render(request,'productselection.html',{'customer':customer,"bill_form":bill_form,"bill_item_form":bill_item_form})


@login_required
@transaction.atomic  # Ensures all DB operations are atomic
def save_bill(request, customer_id):
    if not request.user.is_superuser:  # Restrict to superuser
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            total_discount = Decimal(data.get("discount", 0))  # Overall discount
            items = data.get("items", [])

            if not items:
                return JsonResponse({'success': False, 'error': 'No items provided'}, status=400)

            # Compute total gross price (before discount)
            total_gross_price = sum(
                Decimal(item['price']) * int(item['quantity']) for item in items
            )

            # Retrieve Customer
            try:
                customer = Customers.objects.get(id=customer_id)
            except Customers.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)

            total_cgst = Decimal(0)
            total_sgst = Decimal(0)
            total_discounted_price = total_gross_price - total_discount  # After discount

            # Create Bill
            bill = Bill.objects.create(
                customer_name=customer.name,
                customer_phone=customer.phone,
                customer_email=customer.email,
                gross_total=total_gross_price,
                total_discount=total_discount,
                total_cgst=Decimal(0),  
                total_sgst=Decimal(0),  
                net_total=Decimal(0) 
            )

            for item in items:
                sku = item.get('sku')
                try:
                    product = Products.objects.get(name=item["name"], brand=item["brand"], sku=sku)
                except Products.DoesNotExist:
                    return JsonResponse({'success': False, "error": f'Product not found: {item["name"]}'}, status=404)

                quantity = int(item['quantity'])
                unit_price = Decimal(item['price'])
                sub_total = unit_price * quantity  # Before discount

                # Validate stock availability
                if product.stock < quantity:
                    return JsonResponse({'success': False, "error": f'Not enough stock for {item["name"]}'}, status=400)

                # Calculate proportional discount
                discount_share_percent = (sub_total / total_gross_price) * 100
                discounted_share_amount = (total_discount * discount_share_percent) / 100
                discounted_price = sub_total - discounted_share_amount  # Discounted total for this item

                # Apply GST on the discounted price
                gst_rate = product.gst / Decimal(100)
                base_price = discounted_price / (1 + gst_rate)
                total_gst = discounted_price * gst_rate  # GST amount
                cgst = total_gst / 2  # CGST split
                sgst = total_gst / 2  # SGST split
                net = discounted_price + total_gst

                # Update product stock
                product.stock -= quantity
                product.save()

                # Save bill item
                BillItem.objects.create(
                    bill=bill,
                    sku=product.sku,
                    item_name=product.name,
                    item_brand=product.brand,
                    quantity=quantity,
                    unit_price=unit_price,
                    gross_total=sub_total,
                    discount=discounted_share_amount,
                    cgst=cgst,
                    cgst_rate=product.gst / 2,
                    sgst=sgst,
                    sgst_rate=product.gst / 2,
                    net_total=net
                )

                # Accumulate GST values
                total_cgst += cgst
                total_sgst += sgst

            # Update Bill with correct GST and net total
            bill.total_cgst = total_cgst
            bill.total_sgst = total_sgst
            bill.net_total = total_discounted_price + total_cgst + total_sgst
            bill.save()

            print(f"Bill saved with ID: {bill.id}")
            return JsonResponse({'success': True, 'bill_id': bill.id})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON input'}, status=400)
        except (ValueError,InvalidOperation):
            return JsonResponse({'success': False, 'error': 'Invalid numerical input'}, status=400)
        except IntegrityError:
            return JsonResponse({'success': False, 'error': 'Database error occurred'}, status=500)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e), 'type': type(e).__name__}, status=500)

    else:
        print('methos is not post',request.method)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def Invoice(request, bill_id):
    bill = Bill.objects.get(id=bill_id)
    items = BillItem.objects.filter(bill=bill)

    gross_total = sum(item.gross_total for item in items)
    discount = sum(item.discount for item in items)
    total_cgst = sum(item.cgst for item in items)
    total_sgst = sum(item.sgst for item in items)
    total_gst = total_cgst + total_sgst
    net_total = sum(item.net_total for item in items)  # This should match bill.total_amount

    return render(request, 'invoice.html', {
        'bill': bill,
        'items': items,
        'gross_total': gross_total,
        'discount': discount,
        'total_cgst': total_cgst,
        'total_sgst': total_sgst,
        'total_gst': total_gst,
        'net_total': net_total
    })

@login_required
@transaction.atomic
def Removebill(request, bill_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            items_to_remove = data.get("items", [])

            if not items_to_remove:
                return JsonResponse({'error': 'No items selected for return'}, status=400)

            bill = Bill.objects.get(id=bill_id)

            # Generate a unique return_id based on the latest SalesReturn ID or use a custom sequence
            last_return = SalesReturn.objects.all().order_by('-return_id').first()
            if last_return:
                return_id = last_return.return_id + 1  # Increment the last ID by 1
            else:
                return_id = 1  # Start from 1 if no previous returns exist

            for item in items_to_remove:
                sku = item["sku"]
                return_qty = int(item["return_qty"])

                bill_item = BillItem.objects.get(bill=bill, sku=sku)

                if return_qty <= 0 or return_qty > bill_item.quantity:
                    return JsonResponse({'error': f'Invalid return quantity for {bill_item.item_name}'}, status=400)

                # Log the removed item in SalesReturn with unique return_id
                SalesReturn.objects.create(
                    return_id=return_id,  # Assign a unique ID for each return session
                    billid=bill_id,
                    sku=bill_item.sku,
                    item_name=bill_item.item_name,
                    item_brand=bill_item.item_brand,
                    quantity=return_qty,
                    unit_price=bill_item.unit_price,
                    total_price=(bill_item.unit_price * return_qty),
                    discount=(bill_item.discount / bill_item.quantity) * return_qty if bill_item.quantity > 0 else 0,
                    net_total=(bill_item.unit_price * return_qty) - ((bill_item.discount / bill_item.quantity) * return_qty if bill_item.quantity > 0 else 0)
                )

            return JsonResponse({'success': True, 'message': 'Items returned successfully', 'return_id': return_id})

        except Bill.DoesNotExist:
            return JsonResponse({'error': 'Bill not found'}, status=404)
        except BillItem.DoesNotExist:
            return JsonResponse({'error': 'Item not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
@transaction.atomic
def get_bill_items(request, bill_id):
    
    try:
        bill_items = BillItem.objects.filter(bill_id=bill_id)
        sales_return_items = SalesReturn.objects.filter(billid=bill_id)

        # Calculate total returned quantities for each SKU
        returned_quantities = {}
        for returned_item in sales_return_items:
            returned_quantities[returned_item.sku] = returned_quantities.get(returned_item.sku, 0) + returned_item.quantity

        items = []
        for item in bill_items:
            already_returned = returned_quantities.get(item.sku, 0)
            remaining_qty = item.quantity - already_returned  # This ensures we do not allow over-returning

            items.append({
                "sku": item.sku,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "returned_qty": already_returned,
                "remaining_qty": remaining_qty,  # Available for return
                "unit_price": float(item.unit_price),
                "discount": float(item.discount),
            })

        return JsonResponse({"items": items})
        
    except Bill.DoesNotExist:
        return JsonResponse({"error": "Bill not found"}, status=404)

@login_required
def SalesReport(request):
    query = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Fetch all bills
    bills = Bill.objects.all()

    # Apply customer name search filter
    if query:
        bills = bills.filter(customer_name__icontains=query)

    # Apply date range filtering (if dates are valid)
    if start_date:
        parsed_start_date = parse_date(start_date)
        if parsed_start_date:
            bills = bills.filter(sales_date__gte=parsed_start_date)

    if end_date:
        parsed_end_date = parse_date(end_date)
        if parsed_end_date:
            # Adjust end date to include the entire day (23:59:59)
            end_date_with_time = parsed_end_date + timedelta(days=1) - timedelta(seconds=1)
            bills = bills.filter(sales_date__lte=end_date_with_time)

    # Apply pagination (10 items per page)
    paginator = Paginator(bills, 10)
    page_number = request.GET.get('page')
    page_object = paginator.get_page(page_number)

    return render(request, 'salesreport.html', {
        'bills': page_object,  # Pass paginated results
        'page_object': page_object,
        'query': query,
        'start_date': start_date,  # Keep filter values in form
        'end_date': end_date,
    })

@login_required
def OpenInvoice(request,bill_id):
    bill=get_object_or_404(Bill,id=bill_id)
    billitem=BillItem.objects.filter(bill=bill)

    context={
        'bill':bill,
        'billitem':billitem,
    }
    return render(request,'invoice.html',context)


@login_required
def export_csv_salesreport(request):
    if not request.user.is_superuser:  # Only allow superuser
        return HttpResponse("Unauthorized", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Bill No', 'Customer Name', 'Phone', 'Email', 'Amount', 'Date'])

    # Get all sales records
    sales = Bill.objects.all()

    # Apply filters from request
    search_query = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    # Apply search filtering
    if search_query:
        sales = sales.filter(
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(customer_email__icontains=search_query) |
            Q(id__icontains=search_query)  # Searching by Bill No
        )

    # Apply date filtering
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            sales = sales.filter(sales_date__gte=start_date)
        except ValueError:
            pass  # Ignore invalid dates

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            sales = sales.filter(sales_date__lte=end_date)
        except ValueError:
            pass  # Ignore invalid dates

    # Apply pagination (export only the visible page)
    paginator = Paginator(sales, 10)  # Match frontend pagination
    page = request.GET.get('page')
    visible_sales = paginator.get_page(page)

    # Write only visible filtered records to CSV
    for bill in visible_sales:
        writer.writerow([
            bill.id,
            bill.customer_name,
            bill.customer_phone,
            bill.customer_email,
            bill.net_total,
            bill.sales_date.strftime("%Y-%m-%d")  # Format date (exclude time)
        ])

    return response

@login_required
def sales_return_list(request):
    # Get search query and date filters from GET request
    query = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Fetch all sales returns
    sales_returns = SalesReturn.objects.all().order_by("-return_date")

    # Apply search filter by SKU, item name, or item brand
    if query:
        sales_returns = sales_returns.filter(
            Q(sku__icontains=query) | Q(item_name__icontains=query) | Q(item_brand__icontains=query)
        )

    # Apply date range filtering
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            sales_returns = sales_returns.filter(return_date__gte=start_date)
        except ValueError:
            pass  # Ignore invalid dates

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            sales_returns = sales_returns.filter(return_date__lte=end_date)
        except ValueError:
            pass  # Ignore invalid dates

    # Apply pagination (10 items per page)
    paginator = Paginator(sales_returns, 10)
    page_number = request.GET.get('page')
    page_object = paginator.get_page(page_number)

    # Return the rendered template with paginated results
    return render(request, 'sales_return.html', {
        'sales_returns': page_object,
        'page_object': page_object,
        'query': query,
        'start_date': start_date,
        'end_date': end_date,
    })

@login_required
def sales_return_bill(request, return_id):
    sales_returns = SalesReturn.objects.filter(return_id=return_id).order_by("return_date")

    if not sales_returns.exists():
        return render(request, "sales_return_bill.html", {"error": "No sales return found for this transaction."})

    first_return = sales_returns.first()
    total_refund = sales_returns.aggregate(total=Sum("net_total"))["total"] or 0

    return render(request, "sales_return_bill.html", {
        "return_id": return_id,  # Use return ID instead of bill_id
        "return_date": first_return.return_date if first_return else None,
        "sales_returns": sales_returns,
        "total_refund": total_refund
    })

def restock_item(request, return_id):
    # Get the returned item
    sales_return = get_object_or_404(SalesReturn, return_id=return_id)

    # Prevent duplicate restocking
    if sales_return.status == "Restocked":
        return redirect('sales-return')  # Redirect if already restocked

    # Fetch the original product details
    original_product = get_object_or_404(Products, sku=sales_return.sku)

    # Generate new SKU by modifying last three digits
    new_sku = sales_return.sku[:-4] + "REST"

    # Ensure SKU is unique
    if Products.objects.filter(sku=new_sku).exists():
        timestamp = datetime.now().strftime("%H%M%S")
        new_sku = f"{sales_return.sku[:-4]}REST{timestamp}"

    # Create a new product entry
    Products.objects.create(
        name=original_product.name,
        category=original_product.category,
        description=original_product.description,
        brand=original_product.brand,
        purchase_price=original_product.purchase_price,  # Maintain the same purchase price
        gst=original_product.gst,  # Keep the GST rate unchanged
        selling_price=original_product.selling_price,  # Maintain the original selling price
        stock=sales_return.quantity,  # New stock equals returned quantity
        sku=new_sku,
        supplier_name=original_product.supplier_name,
        supplier_id=original_product.supplier_id,
    )

    # Mark as restocked
    sales_return.status = "Restocked"
    sales_return.save()

    return redirect('sales-return')  # Redirect to the sales return page

@login_required
def customers_details(request):
    customers=Customers.objects.all()
    return render(request,'customers.html',{'customers':customers})
