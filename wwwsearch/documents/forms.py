from django import forms
from django.forms.fields import ChoiceField
#from django.forms.widgets import RadioSelect
from usersettings import userconfig as config
from documents.models import SolrCore as sc
#NB values fetched at server restart, not dynamic

def get_corechoices():
    cores={}
    choice_list=()
    for coredoc in sc.objects.all():
        corenumber=coredoc.coreID
        coredisplayname=coredoc.coreDisplayName
       #print corenumber,core
        choice_list +=((corenumber,coredisplayname),) #value/label
    #print(choice_list)
    return choice_list
	
#    choice_list=()
#    for corenumber in config['Cores']:
#       core=config['Cores'][corenumber]
#       #print corenumber,core
#       if core in config: 
#           if 'name' in config[core]:
#               choice_list +=((corenumber,config[core]['name']),) #value/label
#    #print(choice_list)
#    return choice_list


class IndexForm(forms.Form):
    CoreChoice= ChoiceField(label='Index: ',choices=get_corechoices(),initial='2',widget=forms.Select(attrs={"onChange":'this.form.submit();'}))

