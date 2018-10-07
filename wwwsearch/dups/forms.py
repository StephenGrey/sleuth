from django import forms
#from django.core.exceptions import ValidationError
#from django.forms.fields import ChoiceField
#from django.forms.widgets import RadioSelect
#from django.db.utils import OperationalError

class ScanForm(forms.Form):
    """ Form to select authorised Solr index, input search term """
    scanpath=forms.CharField(label='Path', max_length=250,initial='') #,widget=forms.Textarea(attrs={'rows': 1, 'cols': 60})
#
#class MasterForm(forms.Form):
#    masterpath=forms.FilePathField(path='/Volumes',label='Path',
#    initial='',
#    allow_files=False,
#    allow_folders=True,
#    recursive=True,
#    widget=forms.Textarea(attrs={'rows': 1, 'cols': 30})
#    )    
##    
#    attrs={'multiple': True}
#    	
#    	
#    	widget=forms.Textarea(attrs={'rows': 1, 'cols': 30}))
