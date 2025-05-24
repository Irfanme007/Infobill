from django import forms
from .models import *

class CustomerForm(forms.ModelForm):
    class Meta:
        model=Customers
        fields=['phone','name','email','address']

    def clean(self):
        cleaned_data=super().clean()
        phone=cleaned_data.get('phone')

        if phone:
            try:
                customer=Customers.objects.get(phone=phone)
                self.instance=customer
            except Customers.DoesNotExist:
                pass
        return cleaned_data
    
class BillForm(forms.ModelForm):
    class Meta:
        model=Bill
        fields=['customer_name','customer_phone','customer_email']

class BillItemForm(forms.ModelForm):
    class Meta:
        model=BillItem
        fields=['item_name','item_brand','quantity','unit_price']
    
    item_name=forms.CharField(widget=forms.TextInput(attrs={'id':'item-name','autocomplete':'off'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item_brand'].widget.attrs['readonly'] = True
        self.fields['unit_price'].widget.attrs['readonly'] = True