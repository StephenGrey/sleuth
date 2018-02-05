# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import urllib
from .forms import TagForm

class Page(object):
    def __init__(self,searchterm=''):
        self.searchterm=searchterm
    
    def safe_searchterm(self):
        self.searchterm_urlsafe=self.searchterm
        self.searchterm=urllib.unquote_plus(self.searchterm)

    def add_filters(self):
        self.filters={self.tag1field:self.tag1,self.tag2field:self.tag2,self.tag3field:self.tag3}
        self.filters.pop('','') #remove blank filters
        if self.tag1 or self.tag2 or self.tag3:
            self.tagfilters=True
        else:
            self.tagfilters=False


class SearchPage(Page):
    def __init__(self,page_number=0,searchterm='',direction='',pagemax=0,sorttype='',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3=''):
        super(SearchPage,self).__init__(searchterm=searchterm)
        self.page_number=page_number
        self.direction=direction
        self.pagemax=pagemax
        self.sorttype=sorttype
        self.tag1field=tag1field
        self.tag1=tag1
        self.tag2field=tag2field
        self.tag2=tag2
        self.tag3field=tag3field
        self.tag3=tag3
        self.resultlist=[]        
        
    def clear_(self):
        self.facets=[]
        self.facets2=[]
        self.facets3=[]
        self.tag1=''
        self.results=[]
        self.backpage,self.nextpage='',''
        self.resultcount=0
        self.pagemax=''

    def nextpages(self, results_per_page):
        pagemax=int(self.resultcount/results_per_page)+1
        if self.page_number>1:
            self.backpage=self.page_number-1
        else:
            self.backpage=''
        if self.page_number<pagemax:
            self.nextpage=self.page_number+1
        else:
            self.nextpage=''
 
    
class ContentPage(Page):
    def __init__(self,doc_id='',searchterm='',tagedit='False'):
        super(ContentPage,self).__init__(searchterm=searchterm)
        self.doc_id=doc_id
        self.tagedit=tagedit
    
    def process_result(self,result):
        self.result=result
        self.docsize=result.data.get('solrdocsize')
        self.docpath=result.data.get('docpath')
        self.rawtext=result.data.get('rawtext')
        self.docname=result.docname
        self.hashcontents=result.data.get('hashcontents')
        self.highlight=result.data.get('highlight','')
        self.datetext=result.datetext 
        self.data_ID=result.data.get('SBdata_ID','') #pulling ref to doc if stored in local database
        #if multivalued, take the first one
        if isinstance(self.data_ID,list):
            page.data_ID=data_ID[0]
        self.tags1=self.result.data.get('tags1',[False])[0]
        if self.tags1=='':
            self.tags1=False
        self.html=self.result.data.get('preview_html','')


    
    def tagform(self):
        self.initialtags=self.result.data.get(self.mycore.usertags1field,'')
        if not isinstance(self.initialtags,list):
            self.initialtags=[self.initialtags]
        self.tagstring=','.join(map(str, self.initialtags))
        return TagForm(self.tagstring)
       
        
        
    
    
    
        