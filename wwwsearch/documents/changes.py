# -*- coding: utf-8 -*-
import json,time
from .models import File,Collection
from documents import file_utils,time_utils
#from ownsearch.hashScan import FileSpecTable as filetable
#from ownsearch.hashScan import hashfile256 as hexfile
#from ownsearch.hashScan import pathHash
from ownsearch import solrJson
import logging,os
log = logging.getLogger('ownsearch.docs.changes')

from .redis_cache import redis_connection as r


class ChangesError(Exception):
    pass

class Scanner:
    def __init__(self,collection,test=False,job=None):
        if not isinstance(collection, Collection):
            raise ChangesError('Not a valid collection')
        self.collection=collection
        self.test=test
        self.unchanged_files,self.changed_files,self.moved_files,self.new_files,self.deleted_files=[],[],[],[],[]
        self.missing_files,self.new_files_hash={},{}
        self.scan_error=False
        self.job=job
        
        self.total_files()
        self.update_results()
        self.process()
        self.update_results()
    
    
    def total_files(self):
        self.total= sum([len(subdir)+len(files) for r, subdir, files in os.walk(self.collection.path)])
        log.debug(f'Total files counted: {self.total}')
    
    def process(self):
        self.scan()
        self.find_on_disk()
        self.scan_new_files()
        self.new_or_missing()
        self.count_changes()
        log.info('NEWFILES>>>>>{}'.format(self.new_files))
        log.info('DELETEDFILES>>>>>>>{}'.format(self.deleted_files))
        log.info('MOVED>>>>:{}'.format(self.moved_files))
        #print('NOCHANGE>>>',self.unchanged_files)
        log.info('CHANGEDFILES>>>>>>{}'.format(self.changed_files))
          
    def scan(self):
        """1. scan all files in collection"""
        self.files_in_database=File.objects.filter(collection=self.collection)
        self.files_on_disk=file_utils.filespecs(self.collection.path,job=self.job) #get dict of specs of files in disk folder(and subfolders)
        log.debug(self.files_in_database)
        log.debug(self.files_on_disk)
        self.total=len(self.files_on_disk)
        
    def find_on_disk(self):
        """2. loop through files in the database"""
        self.update_progress('Comparing files on disk with database')
        for database_file in self.files_in_database:
            if database_file.filepath in self.files_on_disk:
                self.find_unchanged(database_file)
            else: #file has been deleted or moved
                self.missing_files[database_file.filepath]=database_file.hash_contents

    def find_unchanged(self,database_file):
        """2a. For a database file found on disk - add to changed or unchanged list/dict"""
        file_meta=self.files_on_disk.pop(database_file.filepath)
        
        #log.debug(file_meta)
#        path_date=time_utils.timeaware(file_meta.date_from_path)
#        if database_file.content_date != path_date:
#            log.debug(f'Path date modified: database: {database_file.content_date} local: {path_date}')
#        
        latest_lastmodified=time_utils.timestamp2aware(file_meta.last_modified)

        latestfilesize=file_meta.length
        if database_file.last_modified==latest_lastmodified and latestfilesize==database_file.filesize:
            #print(path+' hasnt changed')
            self.unchanged_files.append(database_file.filepath)
        else:
            #print(path+' still there but has changed')
            self.changed_files.append(database_file.filepath)
            log.debug('Changed file: \nStored date: {} New date {}\n Stored filesize: {} New filesize: {}'.format(database_file.last_modified,latest_lastmodified,database_file.filesize,latestfilesize))

    def scan_new_files(self):
        """3. make index of remaining files found on disk, using contents hash)"""
        self.update_progress('Adding new files to database')
        log.debug('Adding new files to database')
        #time.sleep(10)
        for newpath in self.files_on_disk:
            if not self.files_on_disk[newpath].folder:
                try:
                    self.update_working_file(newpath)
                    newhash=file_utils.get_contents_hash(file_utils.normalise(newpath)) #normalise to adjust for windows quirks, e.g. cope with long paths
                    if newhash in self.new_files_hash:
                        self.new_files_hash[newhash].append(newpath)
                    else:
                        self.new_files_hash[newhash]=[newpath]
                except Exception as e:
                    log.error(e) 
            else:
                #print('New folder found: {}'.format(newpath))
                self.new_files.append(newpath)
        self.update_working_file('')

    def new_or_missing(self):        
        """4. now work out which new files have been moved """
        self.update_progress('Identifying moved files')
        log.debug('Identifying moved files')
        for missingfilepath in self.missing_files:
            missinghash=self.missing_files[missingfilepath]
            
            newpaths=self.new_files_hash.get(missinghash)
            if newpaths:
                #take one of the new files from list (no particular logic on which is moved / new)
                newpath=newpaths.pop()
                #put back the reduced list
                self.new_files_hash[missinghash]=newpaths
                #print(os.path.basename(missingfilepath)+' has moved to '+os.path.dirname(newpath))
                self.moved_files.append([newpath,missingfilepath])
            else: #remaining files have been deleted
                self.deleted_files.append(missingfilepath)
      
      #remaining files in newfilehash are new 
        for newhash in self.new_files_hash:
            newpaths=self.new_files_hash[newhash]
            for newpath in newpaths:
                self.new_files.append(newpath)
                
    def update_database(self):
        """update file database with changes"""
        filelist=File.objects.filter(collection=self.collection)
        if self.new_files:
            for path in self.new_files:
                newfile(path,self.collection)
        if self.moved_files:
            #print((len(self.moved_files),' to move'))
            for newpath,oldpath in self.moved_files:
                #print(newpath,oldpath)
                _files=filelist.filter(filepath=oldpath)
                for _file in _files:
                    movefile(_file,newpath)
                
        if self.changed_files:
            log.debug('{} changed file(s) '.format(len(self.changed_files)))
            for filepath in self.changed_files:
                log.debug('Changed file: {}'.format(filepath))
                _files=filelist.filter(filepath=filepath)
                for _file in _files:
                    changefile(_file)

    def count_changes(self):
        self.new_files_count=len(self.new_files)
        self.deleted_files_count=len(self.deleted_files)
        self.moved_files_count=len(self.moved_files)
        self.unchanged_files_count=len(self.unchanged_files)
        self.changed_files_count=len(self.changed_files)
        self.scanned_files=self.new_files_count+self.deleted_files_count+self.moved_files_count+self.unchanged_files_count+self.changed_files_count
        
        
    def update_progress(self,message):
        if self.job:
            progress_str=f"{message}"
            r.hmset(self.job,{
            'progress_str':progress_str,
            'show_taskbar': 0,
            })
    
    def update_working_file(self,_filename):
        if self.job:
            r.hset(self.job,'working_file',_filename)
        
    def update_results(self):
        if self.job:
            self.count_changes()
            #log.debug(f'scanned files: {self.scanned_files}')
            progress=f'{((self.scanned_files/self.total)*100):.0f}'
            progress_str=f"{self.scanned_files} of {self.total} files" #0- replace 0 for decimal places
            log.debug(f'Progress: {progress_str}')
            r.hmset(self.job,{
            'progress':progress,
            'progress_str':progress_str,
            'total':self.scanned_files,
            'new':self.new_files_count,
            'deleted':self.deleted_files_count,
            'moved':self.moved_files_count,
            'unchanged':self.unchanged_files_count,
            'changed':self.changed_files_count
            })
        else:
            log.debug('No redis job defined')


def movefile(_file,newpath):
    oldpath=_file.filepath
    updatefiledata(_file,newpath) #check all metadata;except contentsHash
    #if the file has been already indexed, flag to correct solr index meta
    if _file.indexedSuccess:
        add_oldpaths(_file,oldpath) #store old filepath to delete from solr
        _file.indexUpdateMeta=True  #flag to correct solrindex
        _file.save()

def add_oldpaths(_file,oldpath):
    existing_oldpaths_raw=_file.oldpaths_to_delete
    oldpaths=json.loads(existing_oldpaths_raw) if existing_oldpaths_raw else []
    if oldpath not in oldpaths:
        oldpaths.append(oldpath)
        oldpaths_raw=json.dumps(oldpaths)
        _file.oldpaths_to_delete=oldpaths_raw
        _file.save()

def newfile(path,collection):
    if os.path.exists(file_utils.normalise(path))==True: #check file exists
        #now create new entry in File database
        try:
            _newfile=File(collection=collection)
            updatefiledata(_newfile,path,makehash=True)
            _newfile.indexedSuccess=False #NEEDS TO BE INDEXED IN SOLR
            _newfile.save()
            return _newfile
        except Exception as e:
            print(e)
            return None
    else:
        log.error(('ERROR: ',path,' does not exist'))

def changefile(file):
    updatesuccess=updatefiledata(file,file.filepath)
    if file.is_folder:
        if file.indexedSuccess: #if already indexed in solr
            file.indexUpdateMeta=True  #flag to correct meta only in
    else:
        #check if contents have changed and solr index needs changing
        oldhash=file.hash_contents
        newhash=file_utils.get_contents_hash(file.filepath)
        if newhash!=oldhash:
            #contents change, flag for index
            file.indexedSuccess=False
            file.hash_contents=newhash
        #NB the solrid field is not cleared = the index checks it exists and deletes the old doc
        #otherwise if no change in hash and file already indexed, flag to correct meta only in solr 
        elif file.indexedSuccess:
            file.indexUpdateMeta=True  #flag to correct solrindex
        #else no change in contents - no need to flag for index
    file.save()
    return True


def updatefiledata(file,path,makehash=False):
    """calculate all the metadata and update database; default don't make hash"""
    try:
        specs=file_utils.FileSpecs(file_utils.normalise(path))
        file.filepath=path #
        file.hash_filename=specs.pathhash #get the HASH OF PATH
        file.filename=specs.name
        shortName, fileExt = specs.shortname, specs.ext
        file.fileext=fileExt   
        file.content_date,file.last_modified=parse_date(specs)
        file.is_folder=specs.folder
        if not file.is_folder and makehash:
            file.hash_contents=specs.contents_hash
        file.filesize=specs.length
        file.save()
        return True
    except Exception as e:
        log.debug(f'Failed to update file database data for {path}')
        log.debug(f'Error in updatefiledata ({e}): ')
        raise ChangesError("Failed to update file database")


def parse_date(specs):
    modTime = specs.last_modified
    last_modified=time_utils.timestamp2aware(modTime) #use GMT aware last modified
    pathdate=specs.date_from_path
    content_date=time_utils.timeaware(pathdate) if pathdate else None
    return content_date,last_modified


def countchanges(changes):
    return [len(changes['newfiles']),len(changes['deletedfiles']),len(changes['movedfiles']),len(changes['unchanged']),len(changes['changedfiles'])]

def path_date_changed(file,existingdoc):
    log.debug(existingdoc.date)
    
    
    
