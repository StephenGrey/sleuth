from django.core.management.base import BaseCommand, CommandError
from documents import indexSolr
from documents.indexSolr import BadParameters
from documents.models import Collection,Source,Index
import os,re

class BadParameters(Exception):
    pass



class Command(BaseCommand):
    help = 'Extract a folder of documents to solr index'
    
    def add_arguments(self, parser):
        
        parser.add_argument('corename', type=str, help='Name of solr core to index collection documents')
        parser.add_argument('collection_path',type=str, help='File path to collection folder')
        
        # Optional argument
        parser.add_argument('-s', '--source', type=str, help='Short name of source of documents in folder')
        parser.add_argument('-sD', '--sourcedisplay', type=str, help='Display name of the source')
            
    def handle(self, *args, **kwargs):
        print(f"with arguments {args} and {kwargs}")
        
        self.corename = kwargs['corename']

        self.path=kwargs['collection_path']
        self.dargs={}
        
        sourcetext= kwargs['source']
        self.dargs.update({'sourcetext':sourcetext}) if sourcetext else None        

        sourcedisplay=kwargs['sourcedisplay']
        self.dargs.update({'sourcedisplay':sourcedisplay}) if sourcedisplay else None        
        self.live_update=False

        try:
            self.args_check()
        
            self.collection,self.created=make(self.path,self.sourceID,self._index,live_update=self.live_update)
            if not self.created:
                print('Collection already existed')
            else:
                print(f'Collection created: {self.collection.__dict__}')
        
        except BadParameters as e:
            print(e)
        


    
    def args_check(self):
        
        try:
            self._index=Index.objects.get(corename=self.corename)
        except:
            message=f'Indexname \"{self.corename}\" does not exist'
            raise BadParameters(f'Indexname \"{self.corename}\" does not exist')
        
        try:
            self.collection=Collection.objects.get(path=self.path,core=self._index)
            raise BadParameters("Collection exists already")
        except Collection.DoesNotExist:
            pass
        
        try:
            assert os.path.exists(self.path)
        except:
            raise BadParameters("Collection filepath does not exist")
                    
        try:
            sourcetext=self.dargs.get('sourcetext')
            if not sourcetext:
                message='Sourcename? (max 10 alpha-numeric characters)'
                maxlen=10
                sourcetext=get_inputtext(message,maxlen)
                    
            self.source,created=Source.objects.get_or_create(sourcename=sourcetext)
            if created:
                sourcedisplay=self.dargs.get('sourcedisplay')
                if not sourcedisplay:
                    make_sourcedisplay(self.source)
            else:
                sourcedisplay=self.source.sourceDisplayName
                if not sourcedisplay:
                    make_sourcedisplay(self.source)
        except Exception as e:
            print(e)
            raise BadParameters("Error getting or creating source text for collection")
    
def make(path,source,_index,live_update=False):
    """make or fetch a collection of documents"""

    collection,created=Collection.objects.get_or_create(path=path,core=_index,live_update=live_update,source=source)

    return collection,created

def make_sourcedisplay(source):
    message='Displayname for source? (max 30 alpha-numeric characters)'
    maxlen=30
    sourcedisplay=get_inputtext(message,maxlen)
    source.sourceDisplayName=sourcedisplay
    source.save()
    

def get_inputtext(message,maxlen):
    displayname=input(message)
    if len(displayname)>maxlen:
        raise BadParameters('too long')
    matches=re.match('[\w\s\\-\"\'\(\)\[\]|!]*',displayname)
    if matches:
        clean_name=matches[0]
        if  clean_name!= displayname:
            raise BadParameters('Bad characters')
    else:
        raise BadParameters('Bad characters')
    return displayname
     