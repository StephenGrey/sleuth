from django.core.management.base import BaseCommand, CommandError
from documents import utils
from documents.indexSolr import BadParameters
from documents.models import Collection
import os,re

class BadParameters(Exception):
    pass

class Command(BaseCommand):
    help = 'Extract a folder of documents to solr index'
    
#    def add_arguments(self, parser):
#        
#        parser.add_argument('corename', type=str, help='Name of solr core to index collection documents')
#        parser.add_argument('collection_path',type=str, help='File path to collection folder')
#        
#        # Optional argument
#        parser.add_argument('-s', '--source', type=str, help='Short name of source of documents in folder')
#        parser.add_argument('-sD', '--sourcedisplay', type=str, help='Display name of the source')
            
    def handle(self, *args, **kwargs):
        print(f"with arguments {args} and {kwargs}")
        
        utils.listc()