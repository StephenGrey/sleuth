# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase
from usersettings import userconfig as config
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

mydefaultcore=Core(defaultcore)

def getcores():
    cores={}
    for corenumber in config['Cores']:
        core=config['Cores'][corenumber]
#        name=config[core]['name']
        cores[corenumber]=solrSoup.SolrCore(core)
    return cores

