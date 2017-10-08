# -*- coding: utf-8 -*-
# 
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
import os, logging
import re
from documents.models import File,Collection
from documents.models import SolrCore as sc
from usersettings import userconfig as config

class MissingConfigData(Exception): 
    pass

class SolrCore:
    def __init__(self,mycore):
        try:
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

log = logging.getLogger('ownsearch')
defaultcore=config['Cores']['1'] #the name of the index to use within the Solr backend
mydefaultcore=SolrCore(defaultcore) #instantiate a default core object


def getSortAttrib(sorttype,core=mydefaultcore):
    if sorttype == 'documentID':
        sortattrib = core.docsort
    elif sorttype == 'last_modified':
        sortattrib = core.datesort
    else: #this is the default - sort by relevance
        sortattrib = ''
    return sortattrib

def solrSearch(q,sorttype,startnumber,core=mydefaultcore):
    args=core.hlarguments+str(startnumber)+getSortAttrib(sorttype)
    #print('args',args)
    try:
        soup=getSolrResponse(q,args,core=core)
        #print(soup.prettify())    
        reslist,numbers=getlist(soup,startnumber,core=core)
    except requests.exceptions.RequestException as e:
        reslist=[]
        numbers=-2
        print 'Connection error to Solr'
    return reslist,numbers

def getSolrResponse(searchterm,arguments,core):
    searchurl=core.url+'/select?q='+searchterm+arguments
    #print (searchurl)
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    soup=BS(res.content,"html.parser")
    #print(soup.prettify())
    return soup


def getlist(soup,counter,core=mydefaultcore,linebreaks=False,big=False): #this parses the list of results, starting at 'counter'
    try:
        numberfound=int(soup.response.result['numfound'])
        result=soup.response.result
        results=[]
        for doc in result:
            document={}
            counter+=1
            solrid=doc.str.text
            document['id']=solrid #this is the main file ID used by Solr
            #now go through all fields returned by the solr search
            for arr in doc:
                document[arr.attrs['name']]=arr.text
            #give the KEY ATTRIBS standard names
            if core.docnamefield in document:
                document['docname']=document[core.docnamefield]
            else:
                document['docname']=''
            if core.docsizefield in document:
                document['solrdocsize']=document[core.docsizefield]
            else:
                document['solrdocsize']=''
            if core.rawtext in document:
                document['rawtext']=document.pop(core.rawtext)
            else:
                document['rawtext']=''
            if core.docnamefield in document:
                document['docname']=document[core.docnamefield]
            else:
                document['docname']=''
            if core.datefield in document:
                document['date']=document.pop(core.datefield)
            elif 'date' not in document:
                document['date']=''
            if core.docpath in document:
                document['docpath']=document[core.docpath]
            else:
                document['docpath']=''
            if core.hashcontentsfield in document:
                document['hashcontents']=document[core.hashcontentsfield]
            else:
                document['hashcontents']=''
            #look up this in our model database, to see if additional data on this doc >>>SHOULD BE MOVED
            try: #lookup to see if hash of filecontents is id 
                f=File.objects.get(hash_contents=document['hashcontents'])
                #print('FILE',f)
                document['path']=f.filepath
                document['filesize']=f.filesize
            except Exception as e:
                #print('Cannot look up file in database',e)
                document['path']=''
                document['filesize']=0
            document['resultnumber']=counter
            results.append(document)
    except Exception as e: 
        print('error in get list',e)
        results=[]
        numberfound=0
    #add the highlighting strings to the results 
    if results:
        if big is True:
            highlights=getbighighlights(soup)
        else:
            highlights=gethighlights(soup,linebreaks=linebreaks)
        if highlights:
              highlightedresults=[]
              for result in results:
                   try:
                       result['highlight']=highlights[result['id']]
                       highlightedresults.append(result)
                   except KeyError:
                       result['highlight']=''
                       highlightedresults.append(result)
              results=highlightedresults
    #print (results)
    return results,numberfound

#print(results)
def gethighlights(soup,linebreaks=False):
    highlights={}
    highlights_all=soup.response.result.next_sibling
    #print ('highlightsall',highlights_all)
    try:
        highlights_all['name']=='highlighting'
    except:
        #no highlights
        return {}
    for item in highlights_all:
        #print (item)
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


def getcontents(docid,core=mydefaultcore):
    searchterm=r'id:"'+docid+r'"'
    #print (searchterm,contentarguments)
    args=core.contentarguments
    sp=getSolrResponse(searchterm,args,core=core)
    res,numbers=getlist(sp,0,core=core)
    return res
    
def bighighlights(docid,core,q):
    searchterm=r'id:'+docid
    args=core.hlarguments+'0&hl.fragsize=5000&hl.snippets=50&hl.q={}&hl.alternateField={}&hl.maxAlternateFieldLength=50000'.format(q,core.rawtext)
    print(args)
    sp=getSolrResponse(searchterm,args,core)
    #print(sp)
#    return getbighighlights(sp)
#    res=getbighighlights(sp)
    res,numbers=getlist(sp,0,core=core,linebreaks=True, big=True)#   
#res,numbers=getlist(sp,0,core=core)
    return res

def getbighighlights(soup):
    highlights={}
    highlights_all=soup.response.result.next_sibling
    #print ('highlightsall',highlights_all)
    try:
        highlights_all['name']=='highlighting'
    except:
        #no highlights
        return {}
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

def gettrimcontents(docid,core,q):
    searchterm=r'id:'+docid
    
    fieldargs='&fl=id,{},{},{},{}&start=0'.format(core.docnamefield,core.docsizefield,core.hashcontentsfield,core.docpath)
#this exploits a quirk in solr to return length-restricted contents as a "highlight"; it depends on a null return on the emptyfield
    hlargs='&hl=on,hl.fl=emptyfield&hl.fragsize=0&hl.alternateField={}&hl.maxAlternateFieldLength=50000'.format(core.rawtext)    
    args=fieldargs+hlargs
#    print (args)
    sp=getSolrResponse(searchterm,args,core)
    res,numbers=getlist(sp,0,core=core,linebreaks=True,big=False)
#    print (sp)
    return res


def hashlookup(hex,core=mydefaultcore):
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
    for coredoc in sc.objects.all():
        core=coredoc.corename
        corenumber=coredoc.coreID
#    for corenumber in config['Cores']:
#        core=config['Cores'][corenumber]
#        name=config[core]['name']
        try:
            cores[corenumber]=SolrCore(core)
        except MissingConfigData:
            print('Missing data in usersettings.config for core number '+corenumber)
    return cores



