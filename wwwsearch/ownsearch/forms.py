from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from usersettings import userconfig as config

#NB values fetched at server restart, not dynamic

def get_corechoices():
    choice_list=()
    for corenumber in config['Cores']:
       core=config['Cores'][corenumber] 
       choice_list +=((corenumber,config[core]['name']),) #value/label
    print(choice_list)
    return choice_list

SORT_CHOICES = (('relevance', 'Relevance'), ('documentID', 'Document name'),('last_modified','Last Modified'))

class SearchForm(forms.Form):
    CoreChoice= ChoiceField(label='Index: ',choices=get_corechoices(),initial='2')
    search_term = forms.CharField(label='Search Term', max_length=100)
    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial='relevance',choices=SORT_CHOICES)


