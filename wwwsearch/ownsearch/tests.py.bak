# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.test import TestCase
from usersettings import userconfig as config
import unicodedata, re, os
from bs4 import BeautifulSoup as BS

# Create your tests here.
import solrSoup, requests

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
    
def bighighlights(docid,core,q):
    searchterm=r'id:'+docid
    args=core.hlarguments+'0&hl.fragsize=100&hl.snippets=10&hl.q='+q
    #print(args)
    sp=getSolrResponse(searchterm,args,core)
    #print(sp)
    res=solrSoup.getbighighlights(sp)
#    res,numbers=getlist(sp,0,core=core,big=True)#   
#res,numbers=getlist(sp,0,core=core)
    return sp,res