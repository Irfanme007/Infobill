from django.urls import path
from django.contrib.auth import views as auth_views

from .views import (
    LoginView,DashBoard,AddproductView,StockReport,purchase_return_view,Logoutview,purchase_return_invoice,
    export_csv_purchasereport,export_csv_stockreport,purchase_report,DeletePurchaseReport,purchase_return,supplier_management,fetch_supplier,generate_tally_report,save_tally_report,
    TallyReport,supplier_details,export_csv_purchase_return)
urlpatterns=[
    path('',LoginView,name='login'),
    path('dashboard/',DashBoard,name='dashboard'),
    path('suppliers/',supplier_details,name='suppliers'),
    path('supplier-management/',supplier_management,name='supplier-management'),
    path('fetch-supplier/',fetch_supplier,name="fetch-supplier"),
    path('addproduct/<str:supplier_name>/<str:supplier_gstin>/', AddproductView, name='addproduct'),
    path('stock-report/',StockReport,name='stock-report'),
    path('purchase-return/<str:sku>/',purchase_return_view,name='purchase-return'),
    path('export_purchase_return_csv/', export_csv_purchase_return, name='export_purchase_return_csv'),
    path('purchase-return-page/',purchase_return,name='purchase-return-page'),
    path('deletepurchasereport/<str:sku>/',DeletePurchaseReport,name='delete-purchase'),
    path('logout/',Logoutview,name='logout'),
    path('purchase-report/',purchase_report,name='purchase-report'),
    path('export-purchase-csv/', export_csv_purchasereport, name='export-purchase-csv'),
    path('export-stock-csv/', export_csv_stockreport, name='export-stock-csv'),
    path('purchase-return-invoice/<int:id>/',purchase_return_invoice, name='purchase-return-invoice'),
    path('save-tally/',save_tally_report,name='save-tally'),
    path('generate-tally/',generate_tally_report,name='generate-tally'),
    path('tally-report/',TallyReport,name='tally-report'),



    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]