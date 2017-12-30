from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from usersettings import userconfig as config
from documents.models import SolrCore as sc
from django.db.utils import OperationalError
#NB values fetched at server restart, not dynamic



SORT_CHOICES = (('relevance', 'Relevance'), ('docname', 'Document name'),('date','Date (received or modified)'))

class SearchForm(forms.Form):

    def __init__(self, choice_list, initial_core, initial_sort, initial_search,*args, **kwargs):
        self.choicelist=choice_list
        self.initial_core=initial_core
        self.initial_sort=initial_sort
        self.initial_search=initial_search
#        self.choicelist=get_corechoices(self.request.user)
        super(SearchForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation
        #print ('choices',self.choicelist)
        #dynamically set core choice based on user
        self.fields['CoreChoice']=ChoiceField(label='Index: ',choices=self.choicelist,initial=self.initial_core)
        self.fields['SortType']=ChoiceField(label='\nSort by :',widget=RadioSelect, initial=self.initial_sort,choices=SORT_CHOICES)   
        self.fields['search_term'] = forms.CharField(label='Search Term', max_length=100,initial=self.initial_search)
#    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial=self.initial_sort,choices=SORT_CHOICES)


class TagForm(forms.Form):
    def __init__(self, initialtags,*args, **kwargs):
        self.initialtags=initialtags
        super(TagForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation
        self.fields['keywords'] = forms.CharField(label='User tags', max_length=100,initial=self.initialtags)
