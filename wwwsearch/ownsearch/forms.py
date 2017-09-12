from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from usersettings import userconfig as config

#NB values fetched at server restart, not dynamic

def get_corechoices():
    choice_list=()
    for core in config['Cores']:
        choice_list +=((core,config['Cores'][core]),)
    return choice_list

SORT_CHOICES = (('relevance', 'Relevance'), ('documentID', 'Document name'),('last_modified','Last Modified'))

class SearchForm(forms.Form):
    CoreChoice= ChoiceField(label='Index: ',choices=get_corechoices())
    search_term = forms.CharField(label='Search Term', max_length=100)
    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial='relevance',choices=SORT_CHOICES)


