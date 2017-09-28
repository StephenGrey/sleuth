# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.test import TestCase
from usersettings import userconfig as config
import unicodedata, re, os

# Create your tests here.
import solrSoup

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



