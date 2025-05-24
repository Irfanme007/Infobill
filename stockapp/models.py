from django.db import models
from datetime import datetime
from django.db.models.signals import post_save
from django.core.validators import MaxLengthValidator
from django.utils.text import slugify
from django.dispatch import receiver

# Create your models here.
class Suppliers(models.Model):
    supplier_name=models.CharField(max_length=100)
    supplier_gstin=models.CharField(unique=True,max_length=15)
    supplier_address=models.TextField(validators=[MaxLengthValidator(1000)])
    supplier_phone=models.CharField(max_length=10)
    supplier_email=models.EmailField(null=True,blank=True)

class Products(models.Model):
    CATEGORY_CHOICES = [
        ('Computers', 'Computers'),  # Laptops, Desktop PCs
        ('Networking Devices', 'Networking Devices'),  # Routers, Modems, Switches
        ('CCTV & Surveillance', 'CCTV & Surveillance'),  # Cameras, DVR/NVR
        ('Printers & Accessories', 'Printers & Accessories'),  # Printers, Ink, Cartridges
        ('Peripherals', 'Peripherals'),  # Keyboards, Mouse, Monitors, Headphones
        ('Storage Devices', 'Storage Devices'),  # SSDs, HDDs, USB Drives
        ('Hardware Components', 'Hardware Components'),  # CPU, GPU, RAM, etc.
        ('Accessories', 'Accessories'),  # Miscellaneous items (Adapters, cables, etc.)
    ]
    name=models.CharField(max_length=255,help_text='Product Name')
    category=models.CharField(max_length=50,choices=CATEGORY_CHOICES,help_text='Product Category')
    description=models.TextField(blank=True,help_text='Detailed Description')
    brand=models.CharField(max_length=100,help_text='Brand or Manufacturer')
    purchase_price=models.DecimalField(max_digits=10,decimal_places=2,help_text='Purchase Price')
    gst=models.DecimalField(max_digits=4,decimal_places=2,help_text='18.00')
    selling_price=models.DecimalField(max_digits=10,decimal_places=2,help_text='Selling Price including GST')
    stock=models.PositiveBigIntegerField(help_text='Items in stock',default=0)
    purchase_date=models.DateTimeField(auto_now_add=True)   
    sku=models.CharField(max_length=50,unique=True)
    is_deleted=models.BooleanField(default=False)
    supplier_name = models.CharField(max_length=100, blank=True, null=True, help_text='Supplier Name')  # NEW FIELD
    supplier_id = models.IntegerField(null=True, blank=True, help_text="Supplier ID")  # NEW FIELD


    def __str__(self):
        return self.name
    
    def generate_sku(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.name[:3].upper()}{timestamp}{self.brand[:4].upper()}"

    def save(self,*args,**kwargs):
        self.name=self.name.upper()
        self.brand=self.brand.upper()
        if not self.sku:
            self.sku=self.generate_sku()

        self.is_deleted=self.stock==0

        super(Products, self).save(*args, **kwargs)

    

class PurchaseReports(models.Model):
    name=models.CharField(max_length=255,help_text='Product Name')
    category=models.CharField(max_length=50,help_text='Product Category')
    description=models.TextField(blank=True,help_text='Detailed Description')
    brand=models.CharField(max_length=100,help_text='Brand or Manufacturer')
    purchase_price=models.DecimalField(max_digits=10,decimal_places=2,help_text='Purchase Price')
    gst=models.DecimalField(max_digits=4,decimal_places=2,help_text='GST%')
    selling_price=models.DecimalField(max_digits=10,decimal_places=2,help_text='Selling Price including GST')
    stock=models.PositiveBigIntegerField(help_text='Items Purchased',default=0)
    purchase_date=models.DateTimeField(auto_now_add=True)  
    sku=models.CharField(max_length=50,unique=True,blank=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True, help_text='Supplier Name')  # NEW FIELD
    supplier_gstin=models.CharField(max_length=15)

    def save(self,*args,**kwargs):
        self.name=self.name.upper()
        self.brand=self.brand.upper()
        super(PurchaseReports,self).save(*args,**kwargs)

class PurchaseReturn(models.Model):
    sku = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    item_brand = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    return_date = models.DateTimeField(auto_now_add=True)
    supplier_name=models.CharField(max_length=100)
    supplier_id=models.IntegerField()
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super(PurchaseReturn, self).save(*args, **kwargs)


class Tallyreport(models.Model):
    opening_stock=models.IntegerField()
    total_purchases=models.IntegerField()
    total_purchase_returns=models.IntegerField()
    total_sales_quantity=models.IntegerField()
    total_sales_return=models.IntegerField()
    closing_stock=models.IntegerField()
    created_at=models.DateTimeField(auto_now_add=True)