from django import forms
from .models import Products,Suppliers

class AddproductForm(forms.ModelForm):
    quantity=forms.IntegerField(min_value=1,required=True,help_text='Enter the Quantity to add')
    class Meta:
        model=Products
        fields=['name','category','description','brand','purchase_price','selling_price','gst']

    def __init__(self,*args,**kwargs):
        super(AddproductForm,self).__init__(*args,**kwargs)
        for field in self.fields.values():
            field.widget.attrs['placeholder']=field.help_text


class supplier_form(forms.ModelForm):
    class Meta:
        model = Suppliers
        fields = ['supplier_name', 'supplier_phone', 'supplier_email', 'supplier_gstin', 'supplier_address']

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get('supplier_phone')

        if phone:
            try:
                # Fetch existing supplier if present
                supplier = Suppliers.objects.get(supplier_phone=phone)
                for field, value in cleaned_data.items():
                    setattr(supplier, field, value)  # Update fields dynamically
                supplier.save()  # Save the updated supplier details
                self.instance = supplier  # Assign the updated supplier to the form instance

            except Suppliers.DoesNotExist:
                pass  
        
        return cleaned_data
