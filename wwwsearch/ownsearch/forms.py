from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from configs import config
from documents.models import Index as sc
from django.db.utils import OperationalError
#NB values fetched at server restart, not dynamic
from functools import partial
DateInput = partial(forms.DateInput, {'class': 'datepicker'})

SORT_CHOICES = (('relevance', 'Relevance'), ('docname', 'Document name'),('date','Date (oldest to newest)'),('dateR','Date (newest to oldest)'))

class SearchForm(forms.Form):
    """ Form to select authorised Solr index, input search term """
    def __init__(self, choice_list, initial_core, initial_sort, initial_search,start_date,end_date,*args, **kwargs):
        self.choicelist=choice_list
        self.initial_core=initial_core
        self.initial_sort=initial_sort
        self.initial_search=initial_search
        self.initial_start_date=start_date
#        print("INITIAL DATE: {}".format(self.initial_start_date))
        self.initial_end_date=end_date
#        self.choicelist=get_corechoices(self.request.user)
        super(SearchForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation
        #print ('choices',self.choicelist)
        #dynamically set core choice based on user
        self.fields['CoreChoice']=ChoiceField(label='Index: ',choices=self.choicelist,initial=self.initial_core)
        self.fields['SortType']=ChoiceField(label='\nSort by :',widget=RadioSelect(attrs={'class': 'radio', 'name':'opt-radio'}), initial=self.initial_sort,choices=SORT_CHOICES)   
        self.fields['search_term'] = forms.CharField(label='Search Terms:', max_length=100,initial=self.initial_search) #,widget=forms.Textarea(attrs={'rows': 1, 'cols': 60})
        self.fields['start_date']=forms.DateField(widget=DateInput(format='%d-%m-%Y'),required=False,initial=self.initial_start_date, input_formats=['%d-%m-%Y','%d/%m/%Y','%d/%m/%y'])
        self.fields['end_date']=forms.DateField(widget=DateInput(format='%d-%m-%Y'),required=False, initial=self.initial_end_date, input_formats=['%d-%m-%Y','%d/%m/%Y','%d/%m/%y'])

class TagForm(forms.Form):
    """ Input user-defined tags """
    def __init__(self, initialtags,*args, **kwargs):
        self.initialtags=initialtags
        super(TagForm, self).__init__(*args, **kwargs) #having overridden initialisation; now run parent initialisation
        self.fields['keywords'] = CommaSeparatedCharField(label='User tags', min_length=1,max_length=30,initial=self.initialtags, required=False, widget=forms.Textarea(attrs={'rows': 1, 'cols': 75, 'pattern':'[A-Za-z ]+', 'blank': True}))
        self.fields['doc_id']=forms.CharField(max_length=255,initial=None,required=False)

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
