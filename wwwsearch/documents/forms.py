from django import forms
from django.forms.fields import ChoiceField
#from django.forms.widgets import RadioSelect
from usersettings import userconfig as config

#NB values fetched at server restart, not dynamic

def get_corechoices():
    choice_list=()
    for corenumber in config['Cores']:
       core=config['Cores'][corenumber]
       choice_list +=((corenumber,config[core]['name']),) #value/label
#    print(choice_list)
    return choice_list

class IndexForm(forms.Form):
    CoreChoice= ChoiceField(label='Index: ',choices=get_corechoices(),initial='2',widget=forms.Select(attrs={"onChange":'this.form.submit();'}))

