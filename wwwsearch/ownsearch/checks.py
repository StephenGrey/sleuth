# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from documents.models import File,Collection,Index,UserEdit
from usersettings import userconfig as config
from ownsearch import solrJson
import logging
log = logging.getLogger('ownsearch.checks')

class SolrIndexTests():
    def check_configs():
        """ Verify config data exists for each solr index """
        corelist=(Index.objects.all())
        print(corelist)
        choice_list=[]
        cores={}
        for core in corelist:
            print (core.__dict__)
            cores[core.id]=solrJson.SolrCore(core.corename)
            corenumber=str(core.id)
            coredisplayname=core.coreDisplayName
            choice_list +=((corenumber,coredisplayname),) #value/label
        try:
            DEFAULTCOREID=int(config['Solr']['defaultcoreid'])
            print(defaultcoreID,cores)
            assert DEFAULTCOREID in cores     
        except Exception as e:
            log.debug('Default core ('+str(DEFAULTCOREID)+') set in userconfigs not found ')
        try:
            log.debug(str(cores)+' '+str(choice_list))
            DEFAULTCOREID=int(choice_list[0][0])#if no default found, take first in list as new default
        except Exception as e:
            log.error('No valid and authorised index set in database: fix in /admin interface')
            log.error(str(e))
