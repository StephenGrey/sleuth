# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime
from django.urls import reverse
from django.contrib.staticfiles.templatetags.staticfiles import static
try:
    from urllib.parse import unquote_plus
except ImportError:
    from urllib import unquote_plus
try:
    from urllib.parse import quote_plus #python3
except ImportError:
    from urllib import quote_plus #python2
    
import os,logging
log = logging.getLogger('ownsearch.pages')
from .forms import TagForm
from documents import file_utils
from .solrJson import get_email_meta
import mimetypes
MIMETYPES={
}


try:
    from configs import config
    BASEDIR=config['Models']['collectionbasepath'] #get base path of the docstore
except:
    BASEDIR=None

class Page(object):
    def __init__(self,searchterm=''):
        self.searchterm=searchterm
    
    def safe_searchterm(self):
        self.searchterm_urlsafe=self.searchterm
        self.searchterm=unquote_plus(self.searchterm)

    def add_filters(self):
        self.filters={}
        if self.tag1field and self.tag1:
            self.filters.update({self.tag1field:self.tag1})
        if self.tag2field and self.tag2:
            self.filters.update({self.tag2field:self.tag2})
        if self.tag3field and self.tag3:
            self.filters.update({self.tag3field:self.tag3})
        if self.tag1 or self.tag2 or self.tag3:
            self.tagfilters=True
        else:
            self.tagfilters=False
        self.filters.pop('None',None)
        log.debug('filters {}, tagfilters: {}'.format(self.filters,self.tagfilters))    

    @property
    def path_tags(self,isfile=True):
        return file_utils.directory_tags(self.docpath,isfile=isfile)

    @property
    def dirpath_tags(self,isfile=False):
        return file_utils.directory_tags(self.docpath,isfile=isfile)

    
    @property
    def path_exists(self):
        return file_utils.relpath_exists(self.docpath)

    @property
    def relpath_valid(self):
        return file_utils.relpath_valid(self.docpath) 

    def parse_dates(self):
        self.start_date=parse_digitstring(self.start_date_raw)
        self.end_date=parse_digitstring(self.end_date_raw)
        
    def static_check(self):
        print(static('glyphicons-halflings-regular.woff2'))
        
    def make_facets_safe(self):
        if self.facets:
            self.facets=self.safe_list(self.facets)
        if self.facets2:
            self.facets2=self.safe_list(self.facets2)
        if self.facets3:
            self.facets3=self.safe_list(self.facets3)
    
    def safe_list(self,unsafelist):
        return [(item,counter,quote_plus(item)) for item,counter in unsafelist]


class SearchPage(Page):
    def __init__(self,searchurl='',page_number=0,searchterm='',direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3='',start_date='',end_date=''):
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
        self.start_date_raw=start_date
        self.end_date_raw=end_date
        self.resultlist=[]
        self.searchurl=searchurl
        super(SearchPage,self).safe_searchterm()
        super(SearchPage,self).add_filters()
        super(SearchPage,self).parse_dates()
                
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

    def process_page_meta(self):
        self.filterlist=[(tag,self.filters[tag]) for tag in self.filters]
        #log.debug(self.filterlist)
        self.params={'page_number':1}
        if self.start_date:
            self.start_date_urlstring=time_digitstring(self.start_date)
            self.params.update({'start_date':self.start_date_urlstring})
        if self.end_date:
            self.end_date_urlstring=time_digitstring(self.end_date)
            self.params.update({'end_date':self.end_date_urlstring})
        self.params.update({'sorttype':self.sorttype})
        self.searchterm_urlsafe=quote_plus(self.searchterm.encode('utf-8')) #type Ascii
        self.params.update({'searchterm':self.searchterm_urlsafe})
        self.searchurl=reverse('searchpageview',kwargs=self.params)
        try:
            if self.nextpage:
                self.nextparams=self.params
                self.nextparams.update({'page_number':self.nextpage})
                self.searchurl_next=reverse('searchpageview',kwargs=self.nextparams)
                log.debug('nextparams: {}'.format(self.nextparams))
        except AttributeError:
            self.searchurl_next=None
        

        try:
            if self.backpage:
                self.backparams=self.params
                self.backparams.update({'page_number':self.backpage})
                self.searchurl_back=reverse('searchpageview',kwargs=self.backparams)
        except AttributeError:
            self.searchurl_back=None
        
        if self.tagfilters and self.backpage:
            self.backparams_tags=self.backparams
            for n in range(3):
                try:
                    if self.filterlist[n][0]:
                        self.backparams_tags.update({'tag{}field'.format(n+1):self.filterlist[n][0],'tag{}'.format(n+1):self.filterlist[n][1]})
                except:
                    pass
                    #backparams_tags.update({'tag{}field'.format(n+1):None,'tag{}'.format(n+1):None})
            self.searchurl_back_tags=reverse('searchpagefilters',kwargs=self.backparams_tags)
            
        if self.tagfilters and self.nextpage:
            self.nextparams_tags=self.nextparams
            #log.debug('nextparams_tags: {}'.format(self.nextparams_tags))
            for n in range(3):
                try:
                    if self.filterlist[n][0]:
                        self.nextparams_tags.update({'tag{}field'.format(n+1):self.filterlist[n][0],'tag{}'.format(n+1):self.filterlist[n][1]})
                except:
                    pass
                    #self.nextparams_tags.update({'tag{}field'.format(n+1):'','tag{}'.format(n+1):''})
            self.searchurl_next_tags=reverse('searchpagefilters',kwargs=self.nextparams_tags)
            
         
            
        
class ContentPage(Page):
    def __init__(self,doc_id='',searchterm='',tagedit='False'):
        super(ContentPage,self).__init__(searchterm=searchterm)
        self.doc_id=doc_id
        self.tagedit=tagedit
    
    def process_result(self,result):
        self.result=result
        self.docsize=result.data.get('solrdocsize')

        #deal with dups with multi-value paths
        self.docpaths=result.data.get('docpath')
        try:
            self.docpath=self.docpaths[0]
        except:
            self.docpath=None
        self.rawtext=result.data.get('rawtext')
        self.docname=result.docname
        self.hashcontents=result.data.get('hashcontents')
        self.highlight=result.data.get('highlight','')
        self.datetext=result.datetext 
        self.data_ID=result.data.get('SBdata_ID','') #pulling ref to doc if stored in local database
        #if multivalued, take the first one
        if isinstance(self.data_ID,list):
            page.data_ID=data_ID[0]
        self.tags1=self.result.data.get('tags1')
        if self.tags1=='' or not self.tags1:
            self.tags1=False
        self.html=self.result.data.get('preview_html','')
        self.preview_url=self.result.data.get('preview_url','')
        
#        if result.content_type=='email':
#            log.info('EMAIL EMAIL')
#            res=get_email_meta(self.doc_id,self.)
        
    
    @property
    def mimetype(self):
        mimetype=self.result.data.get('extract_base_type')
        if not mimetype:
            mimetype=self.result.data.get('content_type')
        if not mimetype and self.docname.startswith('Folder:'):
            mimetype='folder'	
        if not mimetype:
            mimetype,self.encoding=mimetypes.guess_type(os.path.basename(self.docpath), strict=False)
        if not mimetype:
            if self.docpath.startswith('http:') or self.docpath.startswith('www.') or self.docpath.startswith('https:'):
                mimetype='text/html'
        if not mimetype:
            root,ext=os.path.splitext(os.path.basename(self.docpath))
            mimetype=MIMETYPES.get(ext)
        return mimetype
    
    def tagform(self):
        self.initialtags=self.result.data.get(self.mycore.usertags1field,'')
        if not isinstance(self.initialtags,list) and self.initialtags:
            self.initialtags=[self.initialtags]
        self.tagstring=','.join(map(str, self.initialtags))
        #log.debug(f'{self.tagstring},{self.initialtags}')
        return TagForm(self.tagstring)
       


def time_digitstring(timeobject):
    return "{:%Y%m%d}".format(timeobject)

def time_from_digitstring(digitstring):
    return datetime.strptime(digitstring,'%Y%m%d')

def parse_digitstring(digitstring):
    if digitstring:
        try:
            return time_from_digitstring(digitstring)
        except Exception as e:
            print(e)
            return None
    else:
        return None

        
    
    
    
        