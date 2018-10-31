# -*- coding: utf-8 -*-
#from django.contrib.auth.models import User, Group, Permission
#from django.db.utils import OperationalError
#from documents.models import Index
#from ownsearch import solrJson,pages, solr_indexes
#from django.db.migrations.executor import MigrationExecutor
#from django.db import connections, DEFAULT_DB_ALIAS

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from ownsearch import  solr_indexes #solrJson,pages,
from . import setup
from documents.models import Index
#import getpass,re


class Command(BaseCommand):
    help = 'Test manage.py make_index'
    
    def handle(self, *args, **options):
        print('\nThis command will install a new empty index\n')
        
        if setup.answer_yes('Add new index to the solr server? (y/n)'):
            indexname,displayname=setup.make_new_index()
        
        print()
        missing=get_existing_index()
        if missing and setup.answer_yes('Register a solr index to Searchbox users? (y/n)'):
            while True:          
                answer=input('What index to register? ')
                try:
                    indexname=missing[int(answer)]
                    break
                except:
                    continue    
            print(f'... registering {indexname} to database ...')
            displayname=setup.make_new_displayname()
            add_index_to_database(indexname,displayname)
        
        print("""
Completed setting up new index
                            """)

def add_index_to_database(indexname,displayname):
    usergroup=choose_group()

    s,screated=Index.objects.get_or_create(corename=indexname,usergroup=usergroup, coreDisplayName=displayname)
    if screated:
        print('Solr index installed: {}'.format(s))
        s.save()
    elif not screated:
        print('\'{}\' solr index already installed, or failed to create'.format(corename))

def choose_group():
    groups_available=Group.objects.all()
    print('\nChoose which group the index belongs to:')
    for n, group in enumerate(groups_available):
        print(f'{n}: {group.name}')
    while True:          
        answer=input('Choose group? ')
        try:
            group=groups_available[int(answer)]
            return group
        except:
            continue   
    

def solr_indexes():
    #check existing indexes in solr server
    server=setup.solr_indexes.SolrServer()
    server.status_check()
    return [key for key in server.status]    

def indexes_not_in_database(current_solr_indexes,database_indexes):
    """find a solr index not registerd in database"""
    missing=[]
    try:
        #remove indexes only for testing
        current_solr_indexes.remove('tests_only')
        current_solr_indexes.remove('movetest')
    except:
        pass
    
    
    
    for _index in current_solr_indexes:
        if _index not in database_indexes:
            missing.append(_index)
    return missing

def get_existing_index():
    
    current_solr_indexes=solr_indexes()
    database_indexes=[_index.corename for _index in Index.objects.all()]    
    missing=indexes_not_in_database(current_solr_indexes,database_indexes)
    
    if missing:
        print('The following solr indexes are not registered:')
        for n, _index in enumerate(missing):
            print(f'{n}: {_index}')
        return missing
    else:
        return None
        
        


#    _index=Index.objects.get(corename=_indexname)
#    print(_index.__dict__)
#    
#    indexname=''
#    while not indexname:
#        indexname=setup.get_corename()                        
#
#
#    displayname=''
#    while not displayname:
#        displayname=setup.get_displayname()

#        
#    
    
    return _index
    
    