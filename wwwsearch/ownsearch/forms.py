from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from usersettings import userconfig as config
from documents.models import SolrCore as sc
from django.db.utils import OperationalError
#NB values fetched at server restart, not dynamic



SORT_CHOICES = (('relevance', 'Relevance'), ('docname', 'Document name'),('date','Last Modified'))

class SearchForm(forms.Form):

    def __init__(self, choice_list, initial, *args, **kwargs):
        self.choicelist=choice_list
        self.initial=initial
#        self.choicelist=get_corechoices(self.request.user)
        super(SearchForm, self).__init__(*args, **kwargs)
        #print ('choices',self.choicelist)
        #dynamically set core choice based on user
        self.fields['CoreChoice']=ChoiceField(label='Index: ',choices=self.choicelist,initial=self.initial)   
    search_term = forms.CharField(label='Search Term', max_length=100)
    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial='relevance',choices=SORT_CHOICES)
