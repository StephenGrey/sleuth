from django.core.management.base import BaseCommand, CommandError
from documents import indexSolr
from documents.indexSolr import BadParameters

class ExtractFailure(Exception):
    pass

class Command(BaseCommand):
    help = 'Extract a folder of documents to solr index'
    
    def add_arguments(self, parser):
        
        parser.add_argument('corename', type=str, help='Name of solr core to extract documents')

        # Optional argument
        parser.add_argument('-p', '--path', type=str, help='Path of collection folder')
        parser.add_argument('-cID', '--collectionID', type=int, help='ID of collection')
        parser.add_argument('-OCR', type=bool, help='OCR True/FALSE - default False')
        parser.add_argument('-d', '--docstore',type=str, help='Path to root of document store')
            
    def handle(self, *args, **kwargs):
        print(f"with arguments {args} and {kwargs}")
        
        corename = kwargs['corename']
        dargs={}
        
        path= kwargs['path']
        dargs.update({'path':path}) if path else None        

        collectionID= kwargs['collectionID']
        dargs.update({'collectionID':collectionID}) if collectionID else None        

        ocr=kwargs['OCR']
        dargs.update({'ocr':ocr}) if ocr else None        

        docstore=kwargs['docstore']
        dargs.update({'docstore':docstore}) if docstore else None 
        
        try:
            print(f'Extracting {corename} index with args: {dargs}')
            indexSolr.ExtractFolder(corename,**dargs)
        except BadParameters as e:
            print(e)
        
