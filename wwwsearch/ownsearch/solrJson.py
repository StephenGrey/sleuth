# -*- coding: utf-8 -*-
from __future__ import unicode_literals
#from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
import os, logging
import re, json
from documents.models import File,Collection
from documents.models import SolrCore as sc
from django.db.utils import OperationalError
from usersettings import userconfig as config
from django.utils import timezone
import pytz, iso8601 #support localising the timezone
from datetime import datetime
#log = logging.getLogger('ownsearch.solrSoup')

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
    
class SolrCore:
    def __init__(self,mycore):
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
            self.hashcontentsfield=config[core]['hashcontents']
            self.datefield=config[core]['datefield']
            self.docnamesourcefield=config[core]['docnamesource']
            #optional:
            self.tags1field=config[core].get('tags1field','')
            self.usertags1field=config[core].get('usertags1field','')
            self.sourcefield=config[core].get('sourcefield','')
            self.emailmeta=config[core].get('emailmeta','')
            if not fieldexists(self.tags1field,self): #check if the tag field is defined in index
                self.tags1field=''

        except KeyError:
            raise MissingConfigData
    def test(self):
        args=self.hlarguments+'0'
        jres=getJSolrResponse(self.dfltsearchterm,args,core=self)
        res,numbers,facets,facets2,facets3=getlist(jres,0,core=self)
        return res,jres
    def ping(self):
        try:
            res=requests.get(self.url+'/admin/ping')
            if res.status_code==404:
                raise SolrCoreNotFound('Core not found')
            jres=json.loads(res.content)
            if jres['status']=='OK':
                return True
            else:
                log.debug('Core status: '+str(jres))
                return False
        except requests.exceptions.ConnectionError as e:
#            print('no connection to solr server')
            raise SolrConnectionError('Solr Connection Error')
            return False

    def __str__(self):
        return self.name

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
            self.docname=self.data.pop(core.docnamefield,'')
            self.id=self.data.pop('id','')
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
            self.data['hashcontents']=self.data.pop(core.hashcontentsfield,'')
            self.data['tags1']=self.data.pop(core.tags1field,'')
            if isinstance(self.data['tags1'], basestring):
                self.data['tags1']=[self.data['tags1']]

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
                    log.debug('No facets found')
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
                            assert isinstance(tag,basestring)
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
                            assert isinstance(tag,basestring)
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
                            assert isinstance(tag,basestring)
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


log = logging.getLogger('ownsearch.solrJson')

   
#MAIN SEARCH METHOD  (q is search term)
def solrSearch(q,sorttype,startnumber,core,filters={},faceting=False):
    core.ping()
    #create arguments
    facetargs=''
    if faceting:
        facetargs='&facet=on&facet.limit=10'
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
    log.debug('Filter dict: {}'.format(filters))
    for filtertag in filters:
        filtertext=filters[filtertag]
        if filtertag=='tag1':
            filterfield=core.tags1field
        elif filtertag=='tag2':
            filterfield=core.usertags1field
        elif filtertag=='tag3':
            filterfield=core.sourcefield
        else:
            continue
        args=args+'&fq={}:"{}"'.format(filterfield,filtertext)
    log.debug('args: {}'.format(args))
    
# get the response
    try:
        jres=getJSolrResponse(q,args,core=core)
        #print(jres)
        #print(soup.prettify())    
        reslist,numbers,facets,facets2,facets3=getlist(jres,startnumber,core=core)
    except requests.exceptions.RequestException as e:
        reslist=[]
        numbers=-2
        log.warning('Connection error to Solr')
    return reslist,numbers,facets,facets2,facets3

#JSON 
def getJSolrResponse(searchterm,arguments,core):
#    print(searchterm,arguments,core)
    searchurl='{}/select?&q={}{}'.format(core.url,searchterm,arguments)
#    log.debug('GET URL '+searchurl)
    content=resGet(searchurl)
    jres=json.loads(content)
    return jres

def resGet(url,timeout=1):
    ses = requests.Session()
# the session instance holds the cookie. So use it to get/post later
    try:
        res=ses.get(url, timeout=timeout)
        if res.status_code==404:
            raise Solr404('404 error - URL not found')
        else:
            return res.content
    except requests.exceptions.ConnectTimeout as e:
        raise SolrTimeOut
    except requests.exceptions.ConnectionError as e:
#            print('no connection to solr server')
        raise SolrConnectionError('Solr Connection Error')

#Requests won't successfully post if unicode filenames in the header; so converted below
def resPostfile(url,path,timeout=1):
    try:
        simplefilename=os.path.basename(path).encode('ascii','ignore')
#        simplefilename=path.encode('ascii','ignore')
    except:
        simplefilename='Unicode filename DECODE error'
    try:
        with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file,timeout=timeout)
            resstatus=res.status_code
            log.debug('RESULT STATUS: {}'.format(resstatus))
            if resstatus==404:
                raise Solr404('404 error - URL not found')
            elif resstatus==200:
                return res       
            else:
                log.debug('Post result {}'.format(res.content))
                raise PostFailure(resstatus)
    except requests.exceptions.ConnectTimeout as e:
        raise SolrTimeOut
    except requests.exceptions.ReadTimeout as e:
        raise SolrTimeOut
    except requests.exceptions.RequestException as e:
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
    searchterm=r'id:'+docid
    
    #MAKE ARGUMENTS FOR TRIMMED CONTENTS
    fieldargs='&fl=id,{},{},{},{},{},{},{},{},{},{},{}&start=0'.format(core.docnamefield,core.docsizefield,core.hashcontentsfield,core.docpath,core.tags1field, core.usertags1field,core.sourcefield,'preview_html','SBdata_ID',core.datefield,core.emailmeta)
#this exploits a quirk in solr to return length-restricted contents as a "highlight"; it depends on a null return on the nullfield (any field name that does not exist)
    hlargs='&hl=on,hl.fl=nullfield&hl.fragsize=0&hl.alternateField={}&hl.maxAlternateFieldLength={}'.format(core.rawtext,maxlength)    
    args=fieldargs+hlargs
#    print (args)

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
    searchterm=r'id:'+docid
    #make snippets of max length 5000 with searchterm highlighted; if searchterm not found, return maxlength sample
    maxanalyse=1000000 #number of characters checked for the highlight phrase
    args=core.hlarguments+'0&hl.fragsize=5000&hl.snippets=50&hl.q={}&hl.alternateField={}&hl.maxAlternateFieldLength={}&hl.maxAnalyzedChars={}'.format(q,core.rawtext,contentsmax,maxanalyse)
    log.debug('{} {} {}'.format(searchterm,args,core.url))
    jres=getJSolrResponse(searchterm,args,core)
    SR=SolrResult(jres,core,startcount=0)
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=True,bighighlights=True)
    return SR

def getlist(jres,counter,core,linebreaks=False,big=False): #this parses the list of results, starting at 'counter'
    SR=SolrResult(jres,core,startcount=counter)
#    log.debug([doc.data['resultnumber'] for doc in SR.results])
    SR.addstoredmeta()
    SR.addfacets()
    SR.addhighlights(linebreaks=linebreaks,bighighlights=big)
    return SR.results,SR.numberfound,SR.facets,SR.facets2,SR.facets3

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


def getcontents(docid,core):
    searchterm=r'id:"'+docid+r'"'
    #print (searchterm,contentarguments)
    args=core.contentarguments
    jres=getJSolrResponse(searchterm,args,core=core)
    #print(args,sp)
    res,numbers,facets,facets2,facets3=getlist(jres,0,core=core)
    return res

def getmeta(docid,core):
    searchterm=r'id:"'+docid+r'"'
    args='&fl=id'
    args+=","+core.docpath+","+core.datefield+","+core.docsizefield+","+core.datefield+","+core.docnamefield
    jres=getJSolrResponse(searchterm,args,core=core)
    #print(args,sp)
    res,numbers,facets,facets2,facets3=getlist(jres,0,core=core)
    return res
    

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
            corenumber=coredoc.coreID
#    for corenumber in config['Cores']:
#        core=config['Cores'][corenumber]
#        name=config[core]['name']
            try:
                cores[corenumber]=SolrCore(core)
            except MissingConfigData:
                log.error('Missing data in usersettings.config for core number '+corenumber)
    except OperationalError: #catching if solrcore table not created yet
        pass
    return cores

#defaultcore=getcores()['1'] #config['Cores']['1'] #the name of the index to use within the Solr backend
#mydefaultcore=SolrCore(defaultcore) #instantiate a default core object



#def timefromSolr(timestring):
#    if timestring:
#        parseraw=datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%SZ")
#        parsetimezone=pytz.timezone("Europe/London").localize(parseraw, is_dst=True)
#        return parsetimezone
#    else:
#        return ''

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
    
def getSortAttrib(sorttype,core):
    if sorttype == 'documentID':
        sortattrib = core.docsort
    elif sorttype == 'last_modified':
        sortattrib = core.datesort
    else: #this is the default - sort by relevance
        sortattrib = ''
    return sortattrib

def ISOtimestring(timeobject_aware):
    return timeobject_aware.astimezone(pytz.utc).isoformat()[:19]+'Z'

def easydate(timeobject):
    return timeobject.strftime("%b %d, %Y")

def parseISO(timestring):
    return iso8601.parse_date(timestring)