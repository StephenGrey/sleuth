# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
import os, logging
import re
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

class SolrCoreNotFound(Exception):
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
#            self.dfltsearchterm=config['Test']['testsearchterm']
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
            

        except KeyError:
            raise MissingConfigData
    def test(self):
        args=self.hlarguments+'0'
        soup=getSolrResponse(self.dfltsearchterm,args,core=self)
        res,numbers=getlist(soup,0,core=self)
        return res,soup
    def ping(self):
        try:
            res=requests.get(self.url+'/admin/ping')
            soup=BS(res.content,"html.parser")
#            print(soup)
            if soup.title:
                if soup.title.text == u'Error 404 Not Found':
                    raise SolrCoreNotFound('core not found')
            statusline=soup.response.lst.next_sibling
            if statusline.attrs['name']==u'status' and statusline.text=='OK':
#                print('Good connection')
                return True
            else:
                log.debug('Core status: ',soup)
                return False
        except requests.exceptions.ConnectionError as e:
#            print('no connection to solr server')
            raise SolrConnectionError('solr connection error')
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

            for arr in doc: #detects string, datefields and long integers
                if arr.str:
                    self.data[arr.attrs['name']]=arr.str.text
                elif arr.date:
                    dates=[]
                    for date in arr:
                        dates.append(date.text)
                    self.data[arr.attrs['name']]=dates
                elif arr.long:
                    ints=[]
                    for longn in arr:
                        ints.append(longn.text)
                    self.data[arr.attrs['name']]=ints
                else:
                    self.data[arr.attrs['name']]=arr.text
                #print(arr.text)
            #give the KEY ATTRIBS standard names
            self.docname=self.data.pop(core.docnamefield,'')
            self.id=self.data.pop('id','')
            self.date=self.data.pop(core.datefield,'')
            try:
                self.datetext=easydate(parseISO(self.date[0]))
            except Exception as e:
                print(e)
                self.datetext=''
            self.data['solrdocsize']=self.data.pop(core.docsizefield,'')
            self.data['rawtext']=self.data.pop(core.rawtext,'')                
            self.data['docpath']=self.data.pop(core.docpath,'')
            self.data['hashcontents']=self.data.pop(core.hashcontentsfield,'')
#    def __str__(self):
#        return self.docname

class SolrResult:
    def __init__(self,soup,mycore,startcount=0):
#        print(soup)
        self.soup=soup #store unparsed result
        self.mycore=mycore #store the core
        self.results=[] #default no response
        self.counter=startcount
        self.numberfound=0
        try:
            if soup.response:
                result=soup.response.result
                if result.has_attr('numfound'):
                    self.numberfound=int(result['numfound'])
                    #loop through each doc in resultset
                    if self.numberfound>0:
                        for doc in result:
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
#                            log.debug([doc.__dict__ for doc in self.results])
#            log.debug([doc.data['resultnumber'] for doc in self.results])                    
        except Exception as e:
            log.error(str(e))
#            log.debug('Unparsed result: '+str(soup))
            print(e)
            
    def addstoredmeta(self):
        if True:
            for i, document in enumerate(self.results):
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

    def addhighlights(self,linebreaks=False,bighighlights=False):
        #check for and add highlights
        if self.results:
            try:
                soup=self.soup
                nextlist=soup.response.result.next_sibling
    #            print('NEXTLIST',nextlist)
                if nextlist['name']=='highlighting':
                    highlights=nextlist
                    #print('HIGHLIGHTS',highlights)
                else:
                    nextlist=soup.response.result.next_sibling.next_sibling
                    #print('NEXTLIST2',nextlist)
                    if nextlist['name']=='highlighting':
                        highlights=nextlist
                        #rint('HIGHLIGHTS',highlights)
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


log = logging.getLogger('ownsearch.solrSoup')

#MAIN SEARCH METHOD  (q is search term)
def solrSearch(q,sorttype,startnumber,core):
    core.ping()
    args=core.hlarguments+str(startnumber) #+getSortAttrib(sorttype,core)
#ignoring sorttype - other sorting methods now handled by re-sorting
    #print('args',args)
    try:
        soup=getSolrResponse(q,args,core=core)
        #print(soup.prettify())    
        reslist,numbers=getlist(soup,startnumber,core=core)
    except requests.exceptions.RequestException as e:
        reslist=[]
        numbers=-2
        log.warning('Connection error to Solr')
    return reslist,numbers

def getSolrResponse(searchterm,arguments,core):
    searchurl='{}/select?q={}{}'.format(core.url,searchterm,arguments)
    #print (searchurl)
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    #parse the result with beautiful soup
    soup=BS(res.content,"html.parser")
    return soup


#GET CONTENTS OF A DOCUMENT UP TO A MAX SIZE
def gettrimcontents(docid,core,maxlength):
    searchterm=r'id:'+docid
    
    #MAKE ARGUMENTS FOR TRIMMED CONTENTS
    fieldargs='&fl=id,{},{},{},{},{},{},{}&start=0'.format(core.docnamefield,core.docsizefield,core.hashcontentsfield,core.docpath,'preview_html','SBdata_ID',core.datefield)
#this exploits a quirk in solr to return length-restricted contents as a "highlight"; it depends on a null return on the nullfield (any field name that does not exist)
    hlargs='&hl=on,hl.fl=nullfield&hl.fragsize=0&hl.alternateField={}&hl.maxAlternateFieldLength={}'.format(core.rawtext,maxlength)    
    args=fieldargs+hlargs
#    print (args)

    #DO THE SOLR LOOKUP
    sp=getSolrResponse(searchterm,args,core)
    SR=SolrResult(sp,core,startcount=0)
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=True,bighighlights=False)
    #print(vars(SR))
    return SR

#GET CONTENTS OF LARGE DOCUMENT
def bighighlights(docid,core,q,contentsmax):
    searchterm=r'id:'+docid
    #make snippets of max length 5000 with searchterm highlighted; if searchterm not found, return maxlength sample
    args=core.hlarguments+'0&hl.fragsize=5000&hl.snippets=50&hl.q={}&hl.alternateField={}&hl.maxAlternateFieldLength={}'.format(q,core.rawtext,contentsmax)
    sp=getSolrResponse(searchterm,args,core)
#    res,numbers=getlist(sp,0,core=core,linebreaks=True, big=True)#
    
#    getlist(soup,counter,core,linebreaks=False,big=False)
    
    SR=SolrResult(sp,core,startcount=0)
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=True,bighighlights=True)
       
    return SR


def getlist(soup,counter,core,linebreaks=False,big=False): #this parses the list of results, starting at 'counter'
    SR=SolrResult(soup,core,startcount=counter)
#    log.debug([doc.data['resultnumber'] for doc in SR.results])
    SR.addstoredmeta()
    SR.addhighlights(linebreaks=linebreaks,bighighlights=big)
    return SR.results,SR.numberfound

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
    for item in highlights_all:
#        print ('ITEM:',item)
        id=item['name']
        if item.arr:
#remove line returns
            highlight=item.arr.text
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
    return highlights


def getcontents(docid,core):
    searchterm=r'id:"'+docid+r'"'
    #print (searchterm,contentarguments)
    args=core.contentarguments
    sp=getSolrResponse(searchterm,args,core=core)
    #print(args,sp)
    res,numbers=getlist(sp,0,core=core)
    return res

def getmeta(docid,core):
    searchterm=r'id:"'+docid+r'"'
    args='&fl=id'
    args+=","+core.docpath+","+core.datefield+","+core.docsizefield+","+core.datefield+","+core.docnamefield
    sp=getSolrResponse(searchterm,args,core=core)
    #print(args,sp)
    res,numbers=getlist(sp,0,core=core)
    return res
    

def parsebighighlights(highlights_all):
    highlights={}
#    highlights_all=soup.response.result.next_sibling
#    #print ('highlightsall',highlights_all)
#    try:
#        highlights_all['name']=='highlighting'
#    except:
#        #no highlights
#        return {}
    for highlightlist in highlights_all:
        #print (item)
        id=highlightlist['name']
        hls=[]
        if highlightlist.arr:
            for highlighttag in highlightlist.arr:
                hl=[]
                highlight=highlighttag.text #.replace('\n','').replace('\t',' ')
#remove huge chunks of white space
                highlight=re.sub('(\n[\s]+\n)+', '\n', highlight)
#split by em tags to enable highlighting
            #print highlight
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

def hashlookup(hex,core):
    searchterm='extract_id:'+hex
    #print (searchterm,contentarguments)
    args=core.hlarguments+'0'
    #print (args)
    sp=getSolrResponse(searchterm,args,core=core)
    res,numbers=getlist(sp,0,core=core)
    return res

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

def timefromSolr(timestring):
    if timestring:
        parseraw=datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%SZ")
        parsetimezone=pytz.timezone("Europe/London").localize(parseraw, is_dst=True)
        return parsetimezone
    else:
        return ''

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