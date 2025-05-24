from django.urls import path
from billingapp.views import (customer_management,SelectProduct,fetch_customer,get_bill_items,sales_return_list,
                            SalesReport,search_product,save_bill,Invoice,Removebill,export_csv_salesreport,OpenInvoice,
                            sales_return_bill,customers_details,restock_item)

urlpatterns =[
    path('customer-management/',customer_management,name='customer-management'),
    path('fetch-customer/',fetch_customer,name='fetch-customer'),
    path("product-selection/<int:customer_id>/", SelectProduct, name="product-selection"),
    path('sales-report/',SalesReport,name='sales-report'),
    path('search-product/',search_product,name="search-product"),
    path("save-bill/<int:customer_id>/", save_bill, name="save-bill"),
    path('invoice/<int:bill_id>/',Invoice,name='invoice'),
    path('remove-bill/<int:bill_id>/',Removebill,name="remove-bill"),
    path('get-bill-items/<int:bill_id>/', get_bill_items, name="get-bill-items"),
    path('sales-return/', sales_return_list, name="sales-return"),
    path('export-sales-csv/', export_csv_salesreport, name='export-sales-csv'),
    path('open-bill/<int:bill_id>/',OpenInvoice,name='open-bill'),
    path("sales-return-bill/<int:return_id>/", sales_return_bill, name="sales-return-bill"),
    path('customers/',customers_details,name="customers"),
    path('restock-item/<int:return_id>/', restock_item, name='restock-item'),

]