from django import forms

class PhoneNumberForm(forms.Form):
    """ validating update of model """
    def __init__(self,*args, **kwargs):
        super(PhoneNumberForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation        
        self.fields['number']= forms.CharField(label='Number:', max_length=30)
        self.fields['name']= forms.CharField(label='Name:', max_length=60,required=False)
        self.fields['verified']=forms.BooleanField(label='Verified',required=False)
        self.fields['personal']=forms.BooleanField(label='Personal',required=False)
        self.fields['name_exmessage']= forms.CharField(label='Name in Message:', max_length=200,required=False)
        self.fields['name_source']= forms.CharField(label='Name source:', max_length=30,required=False)
        self.fields['name_possible']= forms.CharField(label='Possible name:', max_length=30,required=False)
        self.fields['original_ID']= forms.CharField(label='Original_ID:', max_length=10,required=False)
        self.fields['notes']= forms.CharField(label='Notes:', max_length=250,required=False)
            
