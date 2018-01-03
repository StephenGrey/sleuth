from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
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
        self.fields['search_term'] = forms.CharField(label='Search Terms:', max_length=100,initial=self.initial_search,widget=forms.Textarea(attrs={'rows': 1, 'cols': 60}))
#    SortType = ChoiceField(label='\nSort by :',widget=RadioSelect, initial=self.initial_sort,choices=SORT_CHOICES)


class TagForm(forms.Form):
    def __init__(self, initialtags,*args, **kwargs):
        self.initialtags=initialtags
        super(TagForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation
#        self.fields['keywords'] = forms.CharField(label='User tags', max_length=100,initial=self.initialtags,widget=forms.Textarea(attrs={'rows': 1, 'cols': 80}))
        self.fields['keywords'] = CommaSeparatedCharField(label='User tags', min_length=1,max_length=30,initial=self.initialtags,widget=forms.Textarea(attrs={'rows': 1, 'cols': 80, 'pattern':'[A-Za-z ]+'}))

class MinLengthValidator(validators.MinLengthValidator):
    message = 'Ensure this value has at least %(limit_value)d elements (it has %(show_value)d).'

class MaxLengthValidator(validators.MaxLengthValidator):
    message = 'Ensure this value has at most %(limit_value)d elements (it has %(show_value)d).'

#credit: https://gist.github.com/eerien/7002396
class CommaSeparatedCharField(forms.Field):
    def __init__(self, dedup=True, max_length=None, min_length=None, *args, **kwargs):
        self.dedup, self.max_length, self.min_length = dedup, max_length, min_length
        super(CommaSeparatedCharField, self).__init__(*args, **kwargs)
#        self.validators.append(validators.RegexValidator(r'^[0-9a-zA-Z]*$', 'Only alphanumeric characters are allowed.'))
        if min_length is not None:
            self.validators.append(MinLengthValidator(min_length))
        if max_length is not None:
            self.validators.append(MaxLengthValidator(max_length))

    def to_python(self, value):
        if value in validators.EMPTY_VALUES:
            return []
        value = [item.strip() for item in value.split(',') if item.strip()]
        if self.dedup:
            value = list(set(value))

        return value

    def clean(self, value):
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value
