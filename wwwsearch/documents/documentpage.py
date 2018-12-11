# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ownsearch.pages import Page
import logging
log=logging.getLogger('ownsearch.documentpage')
from ownsearch import authorise
from .forms import IndexForm, get_corechoices
from .models import Collection,Index
from .file_utils import make_relpath

class NoValidCore(Exception):
    pass

class CollectionPage(Page):
    def __init__(self,path=''):
        self.docpath=path
    
    def getcores(self,this_user,stored_core=None):
        """get authorised solr cores , choosed stored core or default """
        self.getindexes(this_user)
        if stored_core==None or stored_core=='':
            self.stored_core=None
            if self.defaultcoreID:
                self.coreID=int(self.defaultcoreID)
                
            else:
                raise NoValidCore
        else:
            self.stored_core=stored_core
            self.coreID=int(stored_core)
        self.mycore=self.cores[self.coreID]
            
    def post_indexform(self,form):
        """change index"""
        #log.debug('Form: {} Valid: {}'.format(form.__dict__,form.is_valid()))
        if form.is_valid():
            self.coreID=int(form.cleaned_data['corechoice'])
            self.validform=True
            self.form=form
            log.debug('change core to {}'.format(self.coreID))
            
        else:
            log.warning('posted form is not valid: {}'.format(form.errors))
            self.validform=False
            self.form=None

    def getindexes(self,thisuser):
        #set up solr indexes
        try:
            authcores=authorise.AuthorisedCores(thisuser)      
        except Exception as e:
            log.warning('No valid indexes defined in database')
            self.defaultcoreID='' #if no indexes, no valid default
        self.cores=authcores.cores
        self.defaultcoreID=authcores.defaultcore
        log.debug('CORES: '+str(self.cores)+' DEFAULT CORE:'+str(self.defaultcoreID))
        
    def chooseindexes(self,request_method,request_postdata='',test=False):
        #log.debug(request_method)
        if request_method=='POST': #if data posted => switch core
            form=IndexForm(request_postdata)
            if test:
            #NOT CLEAR WHY THIS SHOULD BE NECESSARY
                form.fields['corechoice'].choices=get_corechoices()
            self.post_indexform(form)
            self.form=IndexForm(initial={'corechoice':self.coreID})
            self.mycore=self.cores[self.coreID]
        else:
            self.form=IndexForm(initial={'corechoice':self.coreID})
            #log.debug('Form created: {} with choices: {}'.format(self.form.__dict__,self.form.fields['corechoice'].__dict__))
            self.mycore=self.cores[self.coreID]
            
    def get_collections(self):
        self.myindex=Index.objects.get(id=self.coreID)
        log.debug('my Index: {}'.format(self.myindex))
        self.authorised_collections=Collection.objects.filter(core=self.myindex)
        self.authorised_collections_relpaths=[(make_relpath(c.path),c.id) for c in self.authorised_collections]

    
class FilesPage(CollectionPage):
    pass
    
class SolrFilesPage(CollectionPage):
    pass
        
        