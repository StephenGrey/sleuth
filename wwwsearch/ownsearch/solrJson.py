# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from builtins import str #backwards to 2.X
#from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
from requests.exceptions import ConnectionError, RequestException, ConnectTimeout, ReadTimeout
import os, logging
import re, json
from documents.models import File,Collection
from documents.file_utils import slugify
from documents.models import Index as sc
from django.db.utils import OperationalError
from configs import config
from django.utils import timezone
import pytz, iso8601 #support localising the timezone
from datetime import datetime, timedelta
try:
    from urllib.parse import quote_plus #python3
except ImportError:
    from urllib import quote_plus #python2
 

class MissingConfigData(Exception): 
    pass
    
class SolrConnectionError(Exception):
    pass

class SolrTimeOut(Exception):
    pass
    
class SolrCoreNotFound(Exception):
    pass
class Solr404(Exception):
    pass
class PostFailure(Exception):
    pass
class SolrAuthenticationError(Exception):
    pass
class SolrDocNotFound(Exception):
    pass
    
class SolrCore:
    def __init__(self,mycore,test=False):
        try:
            #if mycore is integer, make it string
            mycore=str(mycore)
            if mycore not in config:
                core='defaultcore'
            else:
                core=mycore
            
            #variables that are specific to this core
            self.url=config['Solr']['url']+mycore # Solr:url is the network address of the Solr backend
            self.name=mycore
            
            #variables that can take the defautls
            
            self.unique_id=config[core]['unique_id']
            self.hlarguments=config[core]['highlightingargs']
            self.dfltsearchterm='animal' #any old search term
            self.docpath=config[core]['docpath']
            self.docnamefield=config[core]['docname']
            self.contentarguments=config[core]['contentarguments']
            self.docsort=config[core]['docsort']
            self.datesort=config[core]['datesort']
            self.rawtext=config[core]['rawtext']
            self.cursorargs=config[core]['cursorargs']
            self.docsizefield=config[core]['docsize']
            self.docsizesourcefield1=config[core]['docsizesourcefield1']
            self.docsizesourcefield2=config[core]['docsizesourcefield2']
            self.hashcontentsfield=config[core]['hashcontents']
            self.pathhashfield=config[core]['hashpath']
            self.datefield=config[core]['datefield']
            self.docnamesourcefield=config[core]['docnamesource']
            self.docnamesourcefield2=config[core]['docnamesource2']
            self.datesourcefield=config[core]['datesourcefield']
            #optional:
            self.datesourcefield2=config[core].get('datesourcefield2')
            self.parenthashfield=config[core].get('parentpath_hash','')
            self.tags1field=config[core].get('tags1field','')
            self.usertags1field=config[core].get('usertags1field','')
            self.sourcefield=config[core].get('sourcefield','')
            self.emailmeta=config[core].get('emailmeta','')
            self.nextfield=config[core].get('nextfield','')
            self.beforefield=config[core].get('beforefield','')
            self.sequencefield=config[core].get('sequencefield','')
            self.preview_url=config[core].get('preview_url','')
            if test==False:
                if not fieldexists(self.tags1field,self): #check if the tag field is defined in index
                    self.tags1field=''
        except KeyError:
            raise MissingConfigData('Missing configuration data')

    def __repr__(self):
        return "SolrCore object: \'{}\'".format(self.name)

    def test(self):
        args=self.hlarguments+'0'
        jres=getJSolrResponse(self.dfltsearchterm,args,core=self)
        res=getlist(jres,0,core=self)
        return res.results,jres

    def solr_session(self):
        return SolrSession()
    
    def ping(self):
        try:
            res=self.solr_session().get(self.url+'/admin/ping')
            if res.status_code==404:
                raise SolrCoreNotFound('Core not found')
            elif res.status_code==401:
                raise SolrAuthenticationError('Need to log-in')
            #jres=json.loads(res.content)
            jres=res.json()
            if jres.get('status')=='OK':
                return True
            else:
                log.debug('Core status: '+str(jres))
                return False
        except ConnectionError as e:
            log.debug(e)
#            print('no connection to solr server')
            raise SolrConnectionError('Solr Connection Error')
            return False
            

class RemoteCore(SolrCore):
    """ link to another solr server"""
    def __init__(self,*args, **kwargs):
        super(RemoteCore,self).__init__(*args, **kwargs)
        if 'Remote' not in config:
            raise MissingConfigData('Add \"Remote\" section to usersettings.config')
        if 'url' not in config['Remote']:
            raise MissingConfigData('Add \"url\" to \"Remote\" configs')
        self.url=config['Remote']['url']+self.name
        log.debug(self.url)
        self.ping()

    def solr_session(self):
        return RemoteSolrSession()

class Solrdoc:
    def __init__(self,data={},date='',datetext='',docname='',id=''):
            self.id=id
            self.data=data
            self.date=date
            self.datetext=datetext
            self.docname=docname
            self.resultnumber=0

    def parse(self,doc,core):
            #now go through all fields returned by the solr search
            #log.debug('{}'.format(doc))
            for field in doc: #detects string, datefields and long integers
                if True:
                    try:
                        if isinstance(doc[field],list):
                            if len(doc[field])>1:
                                self.data[field]=[item for item in doc[field]]
                            else:
                                self.data[field]=doc[field][0]
                        else:
                            self.data[field]=doc[field]
                    except Exception as e:
                        print(e)
            #give the KEY ATTRIBS standard names
            self.id=self.data.get(core.unique_id,'') #leave copy in data
            self.docname=self.data.pop(core.docnamefield,'')
            
            self.content_type_raw=self.data.pop('content_type','')
            
            self.content_type='email' if self.content_type_raw=='application/vnd.ms-outlook' else self.content_type_raw
            
            if self.docname.startswith('Folder:'):
                self.folder=True
            else:
                self.folder=False
            
            self.date=self.data.pop(core.datefield,'')
            if isinstance(self.date,list):
                self.date=self.date[0]
            try:
                if self.date:
                    self.datetext=easydate(parseISO(self.date))
                else:
                    self.datetext=''
            except iso8601.ParseError:
                log.debug('Cannot parse datetext from datefield: \"{}\"'.format(self.date))
                self.datetext=''
            except Exception as e:
                log.debug(str(e))
                log.debug(str(self.date))
                self.datetext=''
            self.data['solrdocsize']=self.data.pop(core.docsizefield,'')
            self.data['rawtext']=self.data.pop(core.rawtext,'')                
            
            self.data['docpath']=self.data.pop(core.docpath,'')
            if isinstance(self.data['docpath'], str):
                self.data['docpath']=[self.data['docpath']]
                            
            self.data['hashcontents']=self.data.pop(core.hashcontentsfield,'')
            self.data['tags1']=self.data.pop(core.tags1field,'')
            if self.data['tags1']:
                if isinstance(self.data['tags1'], str):
                    tag=self.data['tags1']
                    self.data['tags1']=[(tag,quote_plus(tag))]
                else:
                    self.data['tags1']=[(tag,quote_plus(tag)) for tag in self.data['tags1']]
                    log.debug("tags1: {}".format(self.data['tags1']))
            self.data['preview_url']=self.data.pop(core.preview_url,'')
            self.next_id=self.data.get(core.nextfield,'')
            self.before_id=self.data.get(core.beforefield,'')
            self.sequence=self.data.get(core.sequencefield,'')

class SolrResult:
    def __init__(self,jres,mycore,startcount=0):
        self.json=jres #store unparsed result
        self.mycore=mycore #store the core
        self.results=[] #default no response
        self.counter=startcount
        self.numberfound=0
        self.nextcursormark=self.json.get('nextCursorMark','')
        try:
            if 'response' in jres:
                result=jres['response']
                if 'numFound' in result:
                    self.numberfound=int(result['numFound'])
                    #loop through each doc in resultset
                    if self.numberfound>0:
                        for doc in result['docs']:
                            #get standardised result
                            resultsdoc=Solrdoc(data={})
                            resultsdoc.parse(doc,mycore)
#                            print(resultsdoc.id)
#                            log.debug(resultsdoc.__dict__)
                            self.counter+=1
                            resultsdoc.data['resultnumber']=self.counter
                            resultsdoc.resultnumber=self.counter
#                            log.debug(resultsdoc.data['resultnumber'])
                            self.results.append(resultsdoc)
#                            print([doc.__dict__ for doc in self.results])
#                            log.debug([doc.__dict__ for doc in self.results])
#            log.debug([doc.data['resultnumber'] for doc in self.results])                    
        except Exception as e:
            log.error(str(e))
            print(e)
            
    def addstoredmeta(self,collection=False):
        if True:
            for i, document in enumerate(self.results):
                if collection:
                    filelist=File.objects.filter(hash_contents=document.data['hashcontents'],collection=collection)
                else:
                    filelist=File.objects.filter(hash_contents=document.data['hashcontents'])
                    #print('FILE',filelist)
                if len(filelist)>0:
                    f=filelist[0]
                    document.data['path']=f.filepath
                    document.data['filesize']=f.filesize
                else:
                    document.data['path']=''
                    document.data['filesize']=0
#                log.debug(document.data)
                self.results[i]=document

    def addfacets(self):
        #check for facets
        self.facets=[]
        self.facets2=[]
        self.facets3=[]
        if self.results:
            try:
                jres=self.json
                if 'facet_counts' in jres:
                    facets=jres['facet_counts']
                else:
                    facets=''
                    #log.debug('No facets found')
                if facets:
                    log.debug('facets exist')
#GET FIRST LIST OF FACETS
                    try:
#                        log.debug('All facets :{}'.format(facets['facet_fields']))
                        taglist=facets['facet_fields'][self.mycore.tags1field]
                        n=0
                        while n<len(taglist):
                            tag=taglist[n]
                            count=taglist[n+1]
                            assert isinstance(tag,str)
                            assert isinstance(count,int)
                            n+=2
                            self.facets.append((tag,count))
#                        log.debug(self.facets)
                    except Exception as e:
                        log.debug(str(e))
#GET SECOND LIST OF FACETS
                    try:
                        taglist=facets['facet_fields'][self.mycore.usertags1field]
                        n=0
                        while n<len(taglist):
                            tag=taglist[n]
                            count=taglist[n+1]
                            assert isinstance(tag,str)
                            assert isinstance(count,int)
                            n+=2
                            self.facets2.append((tag,count))
                        log.debug(self.facets2)
                    except Exception as e:
                        log.debug(str(e))
#GET SOURCE FACETS
                    try:
                        taglist=facets['facet_fields'][self.mycore.sourcefield]
                        n=0
                        while n<len(taglist):
                            tag=taglist[n]
                            count=taglist[n+1]
                            assert isinstance(tag,str)
                            assert isinstance(count,int)
                            n+=2
                            self.facets3.append((tag,count))
                        log.debug(self.facets3)
                    except Exception as e:
                        log.debug(str(e))

            except Exception as e:
                log.debug('No facets found')
                log.debug('Exception: '+str(e))
                #no action required - no facets
                pass


    def addhighlights(self,linebreaks=False,bighighlights=False):
        #check for and add highlights
        if self.results:
            try:
                jres=self.json
                if 'highlighting' in jres:
                    highlights=jres['highlighting']
                    #print('HIGHLIGHTS',highlights)
                else:
                    highlights=''
                if highlights:
                    log.debug('highlights exist')
                    #log.debug(highlights)
                    if bighighlights:
                        highlightsdict=parsebighighlights(highlights)
                    else:
                        highlightsdict=parsehighlights(highlights,linebreaks=linebreaks)
                    if highlightsdict:
                        for n, document in enumerate(self.results):
                            try:
                                document.data['highlight']=highlightsdict[document.id]
                            except KeyError:
                                document.data['highlight']=''
                            self.results[n]=document
                
            except KeyError as e:
                log.debug('No highlights found')
                log.debug('Exception: '+str(e))
                #no action required - no highlights
                pass

class SolrSession(requests.Session):
    def __init__(self):
        super(SolrSession, self).__init__()
        if SOLR_USER and SOLR_PASSWORD:
            self.auth=(SOLR_USER,SOLR_PASSWORD)
        if SOLR_CERT:
            self.verify=SOLR_CERT
            
class RemoteSolrSession(requests.Session):
    def __init__(self):
        super(RemoteSolrSession, self).__init__()
        if REMOTE_SOLR_USER and REMOTE_SOLR_PASSWORD:
            self.auth(REMOTE_SOLR_USER,REMOTE_SOLR_PASSWORD)
        if REMOTE_SOLR_CERT:
            self.verify=REMOTE_SOLR_CERT
            
        log.debug(self.verify)
    
log = logging.getLogger('ownsearch.solrJson')
#server variables
try:
    SOLR_USER=config['Solr'].get('user',None)
    SOLR_PASSWORD=config['Solr'].get('password',None)
    SOLR_CERT=config['Solr'].get('cert',None)
except Exception as e:
    log.error(e)
    raise MissingConfigData

#remote variables
try:
    REMOTE_SOLR_USER=config['Remote'].get('user',None)
    REMOTE_SOLR_PASSWORD=config['Remote'].get('password',None)
    REMOTE_SOLR_CERT=config['Remote'].get('cert',None) 
except:
    log.info('No remote solr server configured')

def pagesearch(page):
    page.results,page.resultcount,page.facets,page.facets2,page.facets3=solrSearch(page.searchterm,page.sorttype,page.startnumber,page.mycore,filters=page.filters,faceting=page.faceting,start_date=page.start_date,end_date=page.end_date)
    page.make_facets_safe()

    return

#MAIN SEARCH METHOD  (q is search term)
def solrSearch(q,sorttype,startnumber,core,filters={},faceting=False,start_date=None,end_date=None):
    core.ping()

    #make date filter
#    print('DATES',start_date,end_date)
    datefilter=make_datefilter(start_date,end_date)

    #create arguments
    facetargs=''
    if faceting:
        facetargs='&facet=on&facet.limit=20'
        if core.tags1field:
            facetargs+='&facet.field={}'.format(core.tags1field)
        if core.usertags1field:
            facetargs+='&facet.field={}'.format(core.usertags1field)
        if core.sourcefield:
            facetargs+='&facet.field={}'.format(core.sourcefield)
    args='{}{}{}'.format(facetargs,core.hlarguments,startnumber) #+getSortAttrib(sorttype,core)
    if sorttype=='date':
        args+='&sort={} asc'.format(core.datefield)
    elif sorttype=='dateR':
        args+='&sort={} desc'.format(core.datefield)
    elif sorttype=='docname':
        args+='&sort={} asc'.format(core.docnamefield)
    elif sorttype=='docnameR':
        args+='&sort={} desc'.format(core.docnamefield)
    
    #make filters
    log.debug('Filter dict: {}'.format(filters))
    for filtertag in filters:
        filtertext=filters[filtertag]
        if filtertag=='tag1':
            filterfield=core.tags1field
        elif filtertag=='tag2':
            filterfield=core.usertags1field
        elif filtertag=='tag3':
            filterfield=core.sourcefield
        elif filtertag=='path':
            filterfield=core.docpath
        else:
            continue
        args=args+'&fq={}:"{}"'.format(filterfield,filtertext)
    if datefilter:
        args+='&fq={}:{}'.format(core.datefield,datefilter)
    log.debug('args: {}'.format(args))
    
# get the response
    try:
        jres={}
        log.debug('q:{},args:{},core{}'.format(q,args,core.name))
        jres=getJSolrResponse(q,args,core=core)
        #print(soup.prettify())    

        res=getlist(jres,startnumber,core=core)
    except RequestException as e:
        reslist=[]
        numbers=-2
        if jres:
            log.debug('Jres: {}'.format(jres))
        log.warning('Connection error to Solr: {}'.format(e))
        return None,None,None,None,None
    return res.results,res.numberfound,res.facets,res.facets2,res.facets3
    
#JSON 
def getJSolrResponse(searchterm,arguments,core):
#    print(searchterm,arguments,core)
    searchurl='{}/select?&q={}{}'.format(core.url,searchterm,arguments)
#    log.debug('GET URL '+searchurl)
    res=resGet(searchurl)
    jres=res.json()
    return jres

def resGet(url,timeout=10):
    ses = SolrSession()
# the session instance holds the cookie. So use it to get/post later
    try:
        res=ses.get(url, timeout=timeout)
        if res.status_code==404:
            log.error('URL: {}'.format(url))
            raise Solr404('404 error - URL not found')
            
        else:
            return res
    except ConnectTimeout as e:
        log.error('url{} error:{}'.format(url,e))
        raise SolrTimeOut
    except ConnectionError as e:
        log.error('url{} error:{}'.format(url,e))
#            print('no connection to solr server')
        raise SolrConnectionError('Solr Connection Error')

def resPostfile(url,path,timeout=1):
    #python3: use bytes object for filepath
    bytes_path=path.encode('utf-8')
    simplefilename=slugify(os.path.basename(path))
    
#needed for python2
#    try:
#        simplefilename=os.path.basename(path).encode('ascii','ignore')
##        simplefilename=path.encode('ascii','ignore')
#    except:
#        simplefilename='Unicode filename DECODE error'
    try:
        with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            log.debug('Posting filename: {}'.format(simplefilename))
            ses=SolrSession()
            res=ses.post(url,files=file,timeout=timeout)
            resstatus=res.status_code
            log.debug('RESULT STATUS: {}'.format(resstatus))
            if resstatus==404:
                raise Solr404('404 error - URL not found')
            elif resstatus==200:
                return res       
            else:
                log.debug('Post result {}'.format(res.content))
                raise PostFailure(resstatus)
    except ConnectTimeout as e:
        raise SolrTimeOut
    except ReadTimeout as e:
        raise SolrTimeOut
    except RequestException as e:
        log.debug('Exception in postSolr: {}{}'.format(str(e),e))
        raise PostFailure
    except ValueError as e:
        log.error(str(e))
        log.debug('Post result {}'.format(res.content))
        raise PostFailure

def fieldexists(field,core):
    try:
        jres = getJSolrResponse(field+':[* TO *]','&rows=0',core)
        assert jres['responseHeader']['status']==0
        return True
    except AssertionError as e:
        log.debug('Field \"{}\" does not exist in index {}'.format(field,core))
    except requests.exceptions.ConnectionError as e:
        raise SolrConnectionError('Solr Connection Error')
    except Exception as e:
        pass
#        log.debug(str(e))
#    log.debug('Error checking if field {} exists in index {}'.format(field,core))
    return False
 
#GET CONTENTS OF A DOCUMENT UP TO A MAX SIZE
def gettrimcontents(docid,core,maxlength):
    searchterm='{}:\"{}\"'.format(core.unique_id,docid)
    
    #MAKE ARGUMENTS FOR TRIMMED CONTENTS
    fieldargs='&fl={},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}'.format(core.unique_id,core.docnamefield,core.docsizefield,core.hashcontentsfield,core.docpath,core.tags1field, core.preview_url,core.usertags1field,core.sourcefield,'extract_base_type','content_type','preview_html','SBdata_ID',core.datefield,core.emailmeta,core.parenthashfield)
    fieldargs+=","+core.beforefield if core.beforefield else ""
    fieldargs+=","+core.nextfield if core.nextfield else ""
    fieldargs+=","+core.sequencefield if core.sequencefield else ""
    fieldargs+="&start=0"

    core.nextfield,core.beforefield,core.sequencefield
#this exploits a quirk in solr to return length-restricted contents as a "highlight"; it depends on a null return on the nullfield (any field name that does not exist)
    hlargs='&hl=on,hl.fl=nullfield&hl.fragsize=0&hl.alternateField={}&hl.maxAlternateFieldLength={}'.format(core.rawtext,maxlength)    
    args=fieldargs+hlargs
    log.debug(args)

    #DO THE SOLR LOOKUP
    sp=getJSolrResponse(searchterm,args,core)
    SR=SolrResult(sp,core,startcount=0)
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=True,bighighlights=False)
#    log.debug('{}'.format(SR.results[0].__dict__))
    return SR

#GET CONTENTS OF LARGE DOCUMENT
def bighighlights(docid,core,q,contentsmax):
    #contents max = max length of snippet to avoid loading up huge file
    searchterm=r'{}:{}'.format(core.unique_id,docid)
    #make snippets of max length 5000 with searchterm highlighted; if searchterm not found, return maxlength sample
    maxanalyse=1000000 #number of characters checked for the highlight phrase
    args=core.hlarguments+'0&hl.fragsize=5000&hl.snippets=50&hl.q={}&hl.alternateField={}&hl.maxAlternateFieldLength={}&hl.maxAnalyzedChars={}'.format(q,core.rawtext,contentsmax,maxanalyse)
    log.debug('{} {} {}'.format(searchterm,args,core.url))
    jres=getJSolrResponse(searchterm,args,core)
    SR=SolrResult(jres,core,startcount=0)
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=True,bighighlights=True)
    return SR

def getlist(jres,counter,core,linebreaks=False,big=False):
 #this parses the list of results, starting at 'counter'
    SR=SolrResult(jres,core,startcount=counter)
#    log.debug([doc.data['resultnumber'] for doc in SR.results])
    SR.addstoredmeta()
    SR.addfacets()
    SR.addhighlights(linebreaks=linebreaks,bighighlights=big)
    return SR
#    .results,SR.numberfound,SR.facets,SR.facets2,SR.facets3

def gethighlights(soup,linebreaks=False):
    highlights_all=soup.response.result.next_sibling
#    print ('highlightsall',highlights_all)
    try:
        highlights_all['name']=='highlighting'
        return parsehighlights(highlights_all,linebreaks)
    except:
        #no highlights
        return {}
    
def parsehighlights(highlights_all,linebreaks):
    highlights={}
    for id in highlights_all:
#        print ('ITEM:',item)
        highlightdict=highlights_all[id]
#remove line returns
        if highlightdict:
            #print (highlightdict)
            for field in highlightdict:
                highlight=highlightdict[field][0]
                #just take the first highlight
                break
            if linebreaks is False:
                highlight=highlight.replace('\n','') 
    #split by em tags to enable highlighting
            try:
                highlight=[highlight.split('<em>')[0]]+highlight.split('<em>')[1].split('</em>')
            except IndexError:
                pass
        else:
            highlight=''
        highlights[id]=highlight
    #print highlights
    return highlights


"""Main methods to look up a single Solr doc """
def getcontents(docid,core):
    searchterm='{}:\"{}\"'.format(core.unique_id,docid)
    #print (searchterm,contentarguments)
    args=core.contentarguments
    args="&fl=id,{},{},{},{},{},{},{},{},{},{},{}".format(core.unique_id,core.docpath,core.datefield,core.docnamefield,core.tags1field,core.sourcefield,core.usertags1field,core.rawtext,core.docsize,core.emailmeta)
    jres=getJSolrResponse(searchterm,args,core=core)

    log.debug('{} {}'.format(args,jres))
    res=getlist(jres,0,core=core)
    return res.results

def getmeta(docid,core):
    searchterm='{}:\"{}\"'.format(core.unique_id,docid)
    args='&fl={}'.format(core.unique_id)
    args+=","+core.docpath+","+core.datefield+","+core.docsizefield+","+core.datefield+","+core.docnamefield
    args+=","+core.parenthashfield if core.parenthashfield else ""
    args+=","+core.beforefield if core.beforefield else ""
    args+=","+core.nextfield if core.nextfield else ""
    args+=","+core.sequencefield if core.sequencefield else ""
    args+=","+core.sourcefield if core.sourcefield else ""
    jres=getJSolrResponse(searchterm,args,core=core)
    #log.debug(args,jres)
    res=getlist(jres,0,core=core)
    return res.results
    

def getfield(docid,field,core):
    """return contents of single field in solr doc"""
    searchterm='{}:\"{}\"'.format(core.unique_id,docid)
    args='&fl={}'.format(field)
    jres=getJSolrResponse(searchterm,args,core=core)
    log.debug(jres)
    try:
        results=SolrResult(jres,core,startcount=0).results
        if len(results)>0:
            result=results[0]
            log.debug(result.__dict__)
            if field in result.data:
                return result.data[field]
            else:
                field_text=getattr(result,field,None)
                if field_text:
                    return field_text
                else:
                    log.debug('Field {} not found in solrdoc {}'.format(field,docid))
                    return None
        else:
            log.debug('Solrdoc {} not found on index {}'.format(docid,core.name))
            raise SolrDocNotFound
    except KeyError:
        log.debug('Error on search for {} with field {} in index {}'.format(docid,field,core.name))
        return None

def parsebighighlights(highlights_all):
    highlights={}
    #log.debug(highlights_all)
    for id in highlights_all:
        highlightdict=highlights_all[id]
        hls=[]
        if highlightdict:
            for field in highlightdict:
                highlight=highlightdict[field][0]
                #log.debug(highlight)
                #just take the first highlight
#remove huge chunks of white space
                #highlight=re.sub('(\n[\s]+\n)+', '\n', highlight)
                highlight=re.sub('\n \xc2\xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
                highlight=re.sub('\n \xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
            #    print('SPACECLEANE'+repr(highlight[:400]))
                highlight=re.sub('(\n[\s]+\n)+', '\n', highlight) #cleaning up chunks of white space

#split by em tags to enable highlighting
            #print highlight
                hl=[]
                for scrap in highlight.split('<em>'):
                #print 'scrap',scrap
                    scrap=scrap.split('</em>')
                    hl.append(scrap)
#            highlight=[highlight.split('<em>')[0]]+highlight.split('<em>')[1].split('</em>')
#                print('firstscrap',hl[0])
                hl[0]=['',hl[0][0]]
                hls.append(hl)
        else:
            highlight=''
        highlights[id]=hls
        #print('extracted highlights:',highlights)
    return highlights

#find a extracted solr doc from hex of original doc ; and optionally find its children (attachments or embeded images etc)
def hashlookup(hex,core,children=False):
    if children:
        searchterm='{}:{}'.format('extract_root',hex)
    else:
        searchterm='{}:{}'.format(core.hashcontentsfield,hex)
    args=core.hlarguments+'0'
    SR=SolrResult(getJSolrResponse(searchterm,args,core=core),core)
    return SR

#make a dictionary of SolrCore objects, so different indexes can be selected from form
def getcores():
    cores={}
    try:
        for coredoc in sc.objects.all():
            core=coredoc.corename
            corenumber=coredoc.id
            try:
                cores[corenumber]=SolrCore(core)
            except MissingConfigData:
                log.error('Missing data in usersettings.config for core number '+corenumber)
    except OperationalError: #catching if solrcore table not created yet
        pass
    return cores

def core_from_collection(_collection):
    return SolrCore(_collection.core.corename)
    

def getSortAttrib(sorttype,core):
    if sorttype == 'documentID':
        sortattrib = core.docsort
    elif sorttype == 'last_modified':
        sortattrib = core.datesort
    else: #this is the default - sort by relevance
        sortattrib = ''
    return sortattrib



##TIME FUNCTIONS  >>> COPIED TO TIME_UTILS.PY

def make_datefilter(start_date,end_date):
    assert isinstance(start_date,datetime) or not start_date
    assert isinstance(end_date,datetime) or not end_date
    if not start_date and not end_date:
        return None
    start_stamp=timestringGMT(start_date) if start_date else '*'
    end_stamp=timestringGMT(end_date+timedelta(days=1)) if end_date else '*'
    return "[{} TO {}]".format(start_stamp,end_stamp)
    
def timestamp2aware(timestamp):
    return timeaware(timefromstamp(timestamp))

def timefromstamp(timestamp):
    return datetime.fromtimestamp(timestamp)

def timeaware(dumbtimeobject):
    return pytz.timezone("GMT").localize(dumbtimeobject)
#Mac / Linux stores all file times etc in GMT, so localise to GMT

def timestring(timeobject):
    return "{:%B %d,%Y %I:%M%p}".format(timeobject)
    
def timestringGMT(timeobject):
    return timeobject.strftime("%Y-%m-%dT%H:%M:%SZ")
    

def ISOtimestring(timeobject_aware):
    return timeobject_aware.astimezone(pytz.utc).isoformat()[:19]+'Z'

def easydate(timeobject):
    return timeobject.strftime("%b %d, %Y")

def parseISO(timestring):
    return iso8601.parse_date(timestring)
    
    