# -*- coding: utf-8 -*-
# 
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
import os, logging
import re
from documents.models import File,Collection
from usersettings import userconfig as config

class SolrCore:
    def __init__(self,core):
        self.url=config['Solr']['url']+core # Solr:url is the network address of the Solr backend
        self.hlarguments=config[core]['highlightingargs']
        self.dfltsearchterm=config['Test']['testsearchterm']
        self.docpath=config[core]['docpath']
        self.docnamefield=config[core]['docname']
        self.contentarguments=config[core]['contentarguments']
        self.docsort=config[core]['docsort']
        self.datesort=config[core]['datesort']
        self.rawtext=config[core]['rawtext']
        self.cursorargs=config[core]['cursorargs']
        self.docsizefield=config[core]['docsize']
        self.hashcontentsfield=config[core]['hashcontents']
        self.name=core
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

def getSolrResponse(searchterm,arguments,core=mydefaultcore):
    searchurl=core.url+'/select?q='+searchterm+arguments
    #print (searchurl)
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    soup=BS(res.content,"html.parser")
    #print(soup.prettify())
    return soup


def getlist(soup,counter,core=mydefaultcore): #this parses the list of results, starting at 'counter'
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
        highlights=gethighlights(soup)
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
def gethighlights(soup):
    highlights={}
    highlights_all=soup.response.result.next_sibling
#    print ('highlightsall',highlights_all)
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
            highlight=item.arr.text.replace('\n','') 
#split by em tags to enable highlighting
            highlight=[highlight.split('<em>')[0]]+highlight.split('<em>')[1].split('</em>')
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
    for corenumber in config['Cores']:
        core=config['Cores'][corenumber]
#        name=config[core]['name']
        cores[corenumber]=SolrCore(core)
    return cores



