from django import forms
from django.forms.fields import ChoiceField
#from django.forms.widgets import RadioSelect
from usersettings import userconfig as config
from documents.models import Index
#NB values fetched at server restart, not dynamic
from django.db.utils import OperationalError

def get_corechoices():
    cores={}
    choice_list=()
    try:
        for coredoc in Index.objects.all():
            corenumber=coredoc.id
            coredisplayname=coredoc.coreDisplayName
            choice_list +=((corenumber,coredisplayname),) #value/label
    except OperationalError:
        pass #catching solr table not created yet
    #print('Choicelist: {}'.format(choice_list))
    return choice_list

class IndexForm(forms.Form):
    corechoice= ChoiceField(label='Index: ',choices=get_corechoices(),widget=forms.Select(attrs={"onChange":'this.form.submit();'}))
    	

class TestForm(forms.Form):
    testfield = forms.CharField(label='Search Terms:', max_length=100) 	
    corechoice=forms.ChoiceField(label='Index',choices=get_corechoices())
    
    