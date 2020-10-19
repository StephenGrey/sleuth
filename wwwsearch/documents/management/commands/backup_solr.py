from django.core.management.base import BaseCommand, CommandError
#import argparse
from documents import indexSolr
from documents.indexSolr import BadParameters
from ownsearch import solrJson

class ExtractFailure(Exception):
    pass

class Command(BaseCommand):
    help = 'Backup solr index'
    
    def add_arguments(self, parser):
        
        parser.add_argument('corename', type=str, help='Name of solr core to backup')

        # Optional argument
        parser.add_argument(
       		'-c','--check', action='store_true', help='check status of backup operation')
        parser.add_argument(
       		'-l','--location', type=str, help='location to store backup snapshot')
            
    def handle(self, *args,  **options):
        #print(f"with arguments {args} and {kwargs}")
        
        corename = options['corename']
        dargs={}
        print(corename)
        #check=kwargs['check']
        
        check=options.get('check')
        location=options.get('location')
        if check:
            print(f'Checking progress of backup to index {corename}')
        else:
            print(f'Attempting solr backup of index: {corename} to location: {location} ')
        
        s=solrJson.SolrCore(corename)
        res=s.backup(location=location,check=check)
        print(f'Result of backup request: {res}')


