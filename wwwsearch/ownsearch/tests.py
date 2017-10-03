# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.test import TestCase
from usersettings import userconfig as config
import unicodedata, re, os
from bs4 import BeautifulSoup as BS

# Create your tests here.
import solrSoup, requests

defaultcore=config['Cores']['1'] #the name of the index to use within the Solr backend

class Core:
    def __init__(self,core):
        self.url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of$
        self.hlarguments=config[core]['highlightingargs']
        self.dfltsearchterm=config['Test']['testsearchterm']
        self.docpath=config[core]['docpath']
        self.docnamefield=config[core]['docname']

def testcore():
    mydefaultcore=Core(defaultcore)
    return mydefaultcore

def getcores():
    cores={}
    for corenumber in config['Cores']:
        core=config['Cores'][corenumber]
#        name=config[core]['name']
        cores[corenumber]=solrSoup.SolrCore(core)
    return cores

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    shortName, fileExt = os.path.splitext(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    return value+fileExt

def getSolrResponse(searchterm,arguments,core):
    searchurl=core.url+'/select?q='+searchterm+arguments
    print (searchurl)
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    soup=BS(res.content,"html.parser")
    #print(soup.prettify())
    return soup

def bighighlights(docid,core):
    searchterm=r'id:'+docid
    args=core.hlarguments+'0&hl.fragsize=1000&hl.snippets=20&hl.q=Trump'
    print(args)
    sp=solrSoup.getSolrResponse(searchterm,args,core)
    #print(sp)
    res=getbighighlights(sp)
#    res,numbers=getlist(sp,0,core=core)
    return res,sp
    
def getbighighlights(soup):
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
        hl=[]
        if item.arr:
#remove line returns and tabs
            
            highlight=item.arr.text.replace('\n','').replace('\t',' ')
#split by em tags to enable highlighting
            print highlight
            for scrap in highlight.split('<em>'):
                print 'scrap',scrap
                scrap=scrap.split('</em>')
                hl.append(scrap)
            #highlight=[highlight.split('<em>')[0]]+highlight.split('<em>')[1].split('</em>')
        else:
            highlight=''
        highlights[id]=hl
    return highlights
"""
What you're looking for is the highlighting hl.maxAlternateFieldLength (http://wiki.apache.org/solr/HighlightingParameters#hl.maxAlternateFieldLength).

You will need to define the field as its own alternate field. If you want to highlight the field Description, the highlight query parameters would be:

hl=true
hl.fl=Description
f.Description.hl.alternateField=Description
hl.maxAlternateFieldLength=300
"""
