from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect

SORT_CHOICES = (('relevance', 'Relevance'), ('documentID', 'Document name'),('last_modified','Last Modified'))

class SearchForm(forms.Form):
    search_term = forms.CharField(label='Search Term', max_length=100)
    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial='relevance',choices=SORT_CHOICES)



