import sys,datetime,time, logging, redis

from SearchBox.tools import wwwsearch_connect #Connect to Django project
from django.conf import settings
from documents import file_utils,utils,changes,updateSolr,indexSolr
from documents.models import File,Collection
logging.config.dictConfig(settings.LOGGING)
log = logging.getLogger('ownsearch.watch_dispatch')
if (log.hasHandlers()):
    print('has handler')

log.info('This is test log entry')

r=redis.Redis()

"""

watcher thread:  - watching file system
report file events to wait q

wait thread: acts on threads
#delay before action - reindex after a few mins 
q of fileevents


worker thread: take action on fileevents


"""
MODIFIED_FILES={}
MODIFIED_TIMES={}

class Index_Dispatch:
    def __init__(self,event_type,sourcepath,destpath):
        self.event_type=event_type
        self.sourcepath=sourcepath
        self.destpath=destpath
        self.check_base()
        self.process()
        
    def process(self):
        log.info(f'EVENT: {self.event_type}  PATH: {self.sourcepath}  (DESTPATH: {self.destpath})')
        if self.event_type=='created':
            self.create()
        elif self.event_type=='modified':
            self.modify()
        elif self.event_type=='delete':
            self.delete()
        elif self.event_type=='moved':
            self.moved()
        self._index()
        log.debug(f'Modification queues: {MODIFIED_FILES}, TIMES: {MODIFIED_TIMES}')
        
    def create(self):
        if self.source_in_database:
            #exists already
            self.modify() #just check it's all ok
            return
            
        _collections=file_utils.find_collections(self.sourcepath)
        if not _collections:
            log.debug('Not in any collection - no modification of database')
            return
            
        for _collection in _collections:
            _newfile=changes.newfile(self.sourcepath,_collection)
            if _newfile:
                self.source_in_database.append(_newfile)
                log.debug(f'Created new record in Collection: \'{_collection}\' in Index: \'{_collection.core}\'')    
    
    def modify(self):
        if self.source_in_database:
            MODIFIED_TIMES[self.sourcepath]=time.time()
            for _file in self.source_in_database:
                #putting modified file in q
                #MODIFIED_FILES.setdefault(self.sourcepath,set()).add(_file.id)
                r.sadd('MODIFIED_FILES',_file.id)
                r.set(f'MODIFIED.{_file.id}',time.time())
                print(f'Added: \'{_file}\' with id {_file.id}to modification queue')
#                if changes.changefile(_file):
#                    print(f'Modified: \'{_file}\' in Index: \'{_file.collection.core}\'')
        else:
            self.create()

    def moved(self):
        if self.dest_in_database and self.source_in_database:
            self.delete() #delete the origin - the destination will be picked up with move event
        elif self.dest_in_database and not self.source_in_database:
            pass #ignore as overwrite - will be picked up as modified event
        elif self.source_in_database and not self.dest_in_database:
            for _file in self.source_in_database:
                changes.movefile(_file,self.destpath)
        else:
            self.sourcepath=self.destpath #send new location to source path to create file record
            self.create() #create if within a collection
    
    def delete(self):
        """delete both from database and solr index, if indexed"""
        if self.source_in_database:
            for _file in self.source_in_database:
                deletefiles=[_file.filepath]
                collection=_file.collection
                updateSolr.removedeleted(deletefiles,collection) #docstore= use default in user settings
        else:
            log.debug(f'File not in database - nothing to delete')
            
            
    def check_base(self):
        _database_files=File.objects.filter(filepath=self.sourcepath)
        log.debug(f'Existing files found: {_database_files}')
        if len(_database_files)>0:
            self.source_in_database=_database_files
        else:
            self.source_in_database=[]
        
        if self.destpath:
            _database_files=File.objects.filter(filepath=self.destpath)
            if len(_database_files)>1:
                self.dest_in_database=_database_files
            else:
                self.dest_in_database=None            
    
    
    def _index(self):
        for _file in self.source_in_database:
            if not _file.indexedSuccess:
                log.debug(f'Now should index {_file} in solr')
                index_file(_file)
            elif _file.indexUpdateMeta:
                log.debug(f'Now should update solr meta for {_file}')
                updateSolr.metaupdate_rawfile(_file)

def index_file(_file):
    extractor=indexSolr.ExtractSingleFile(_file)
    print(extractor.__dict__)
    """options: forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE """
    if extractor.failed==0:
        return True
    else:
        print('Extraction failed')
        return False

def index_file2(_file):
    pass


def update_file(_file):
    if file_utils.changed_file(_file):
        #print('This file needs updating')
        _file.hash_contents=''
        _file.indexedSuccess=False
        _file.indexedTry=False
        _file.save()
        return index_file(_file)
        

def update_filepath(filepath):
    #print(filepath,MODIFIED_FILES)
    file_ids=MODIFIED_FILES.pop(filepath)
    #print(f'Now modifying {file_ids}')
    files=files_from_id(file_ids)
    result=True
    for _file in files:
        if not update_file(_file):
            result=False
    return result

def files_from_id(_ids):
    return [File.objects.get(id=_id) for _id in _ids]
#
#if __name__ == "__main__":
#    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    
#    event_handler = LoggingEventHandler()



