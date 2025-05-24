from django.db import models
from stockapp.models import Products

# Create your models here.

class Customers(models.Model):
    phone=models.CharField(max_length=10,unique=True)
    name=models.CharField(max_length=100)
    email=models.EmailField(null=True,blank=True)
    address=models.TextField(null=True,blank=True)

    def __str__(self):
        return f"{self.phone}({self.name})"

class Bill(models.Model):
    customer_name=models.CharField(max_length=100)
    customer_phone=models.CharField(max_length=10)
    customer_email=models.EmailField(null=True,blank=True)
    sales_date=models.DateTimeField(auto_now_add=True)
    gross_total=models.DecimalField(max_digits=10,decimal_places=2)
    total_discount=models.DecimalField(max_digits=10,decimal_places=2)
    total_cgst=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    total_sgst=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    net_total=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)

    @property
    def total_quantities(self):
        return sum(item.quantity for item in self.items.all())
    
class BillItem(models.Model):
    bill=models.ForeignKey(Bill,on_delete=models.CASCADE,related_name='items')
    sku=models.CharField(max_length=50)
    item_name=models.CharField(max_length=100)
    item_brand=models.CharField(max_length=100)
    quantity=models.PositiveIntegerField(default=0)
    unit_price=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    gross_total=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    discount=models.DecimalField(max_digits=10,decimal_places=2,default=0.00,null=True,blank=True)
    cgst=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    cgst_rate=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    sgst=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    sgst_rate=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)
    net_total=models.DecimalField(max_digits=10,decimal_places=2,default=0.00)


    def __str__(self):
        return f"{self.item_name}({self.quantity}pcs)"
    
class SalesReturn(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Restocked', 'Restocked'),
    ]

    return_id = models.AutoField(primary_key=True)
    billid = models.IntegerField()
    sku = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    item_brand = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_total = models.DecimalField(max_digits=12, decimal_places=2)
    return_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')  # New field

    def __str__(self):
        return f"Return: {self.item_name} (Qty: {self.quantity}) - {self.status}"
