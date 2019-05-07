# -*- coding: utf-8 -*-
import os, logging,hashlib,re,datetime,unicodedata,pickle,time,sys,traceback,shutil,threading
from pathlib import Path
from collections import defaultdict
from . import win_utils, klepto_archive,sql_connect
from send2trash import send2trash

try:
    from django.http import HttpResponse
    from django.template import loader
    from .redis_cache import redis_connection as r

except:
    #usable outside Django
    pass
    
try:
    from documents.models import File,Collection
    MODELS=True
except:
    MODELS=False

try:
    from documents import time_utils
except:
    pass

try:
    #from usersettings import userconfig as config
    from configs import config
    DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore
except:
    #make usable outside the project
    DOCSTORE=''
    pass

try:
#    logging.basicConfig()
#    logging.getLogger().setLevel(logging.DEBUG)
    log = logging.getLogger('ownsearch.docs.file_utils')
#    log.debug('Logging in operation')  
except:
    print('No logging')
    pass

SPECS_FILENAME='.filespecs.p'
ARCH_FILENAME='.kfilespecs.p'

class DoesNotExist(Exception):
    pass

class Not_A_Directory(Exception):
    pass

class EmptyDirectory(Exception):
    pass

class TaskReset(Exception):
    pass

class FileSpecs:
    def __init__(self,path,folder=False,scan_contents=True):
        self.path=normalise(path) #adjust windows longpaths
        self.name=os.path.basename(path)
        self.scan_contents=scan_contents
        self.shortname, self.ext = os.path.splitext(self.name)
        if folder:
            if not os.path.isdir(self.path):
                raise Not_A_Directory
        self.folder=os.path.isdir(self.path)
                
        
    @property
    def length(self):
        if self.exists:
            return os.path.getsize(self.path) #get file length
        else:
            raise DoesNotExist

    @property
    def last_modified(self):
        if self.exists:
            return os.path.getmtime(self.path) #last modified time
        else:
            raise DoesNotExist
            
    @property
    def parent_hash(self):
        return parent_hash(self.path)
    
    @property
    def date_from_path(self):
        """find a date in US format in filename"""
        m=re.match('.*(\d{4})[-_](\d{2})[-_](\d{2})',self.name)
        try:
            if m:
                year=int(m[1])
                if year<2019 and year>1900:
                    month=int(m[2])
                    day=int(m[3])
                    date=datetime.datetime(year=year,month=month,day=day)
                    return date
        except Exception as e:
            pass
        m=re.match('.*(\d{2})[-_](\d{2})[-_](\d{2})',self.name)
        try:
            if m:
                year=int(m[1])
                if year>50:
                    year+=50
                else:
                    year+=2000
                if year<2050 and year>1950:
                    month=int(m[2])
                    day=int(m[3])
                    date=datetime.datetime(year=year,month=month,day=day)
                    return date
        except Exception as e:
            pass
        return None
    
    @property
    def pathhash(self):
        path=Path(self.path).as_posix()  #convert windows paths to unix paths for consistency across platforms
        m=hashlib.md5()
        m.update(path.encode('utf-8')) #encoding avoids unicode error for unicode paths
        return m.hexdigest()
        
    @property
    def contents_hash(self):
        if self.scan_contents:
            return get_contents_hash(self.path)
        else:
            return None

    @property
    def exists(self):
        return os.path.exists(self.path)
        
    def __repr__(self):
        return "File: {}".format(self.path)

class PathIndex:
    def __init__(self,folder,ignore_pattern='X-',job=None):
        self.ignore_pattern=ignore_pattern
        self.folder_path=folder
        self.specs_dict=True
        self.files={}
        self.scan_or_rescan()
        self.job=job


    def scan(self,specs_dict=False,scan_contents=True):
        """make filespecs dict keyed to path"""
        self.specs_dict=specs_dict
        self.counter=0
        self.total= sum([len(subdir)+len(files) for r, subdir, files in os.walk(self.folder_path)])
        if self.job:
            log.info(f'Scanjob: \'{self.job}\'')
        
        #print(self.__dict__)
        log.debug(f'scanning ... {self.folder_path}')
        for dirName, subdirs, fileList in os.walk(self.folder_path): #go through every subfolder in a folder
            log.info(f'Scanning {dirName} ...')
            
            
            if self.job:
                self.update_results()
                
            for filename in fileList: #now through every file in the folder/subfolder
                try:
                    self.counter+=1
                    if self.ignore_pattern and filename.startswith(self.ignore_pattern):
                        pass
                    else:
                        path = os.path.join(dirName, filename)
                        if specs_dict:
                            self.update_record(path,scan_contents=scan_contents)
                        else:
                            self.files[path]=FileSpecs(path)
                        if self.counter%1000==0:
                            log.info(f'Scanned {self.counter} files.. dumping output')
                            self.save()
                        elif self.counter%200==0:
                            log.info(f'Scanned {self.counter} files)')
                except Exception as e:
                    log.warning(e)
                    log.error(f'Error scanning {filename} in {dirName}')
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exc(limit=2, file=sys.stdout)
            for subfolder in subdirs:
                try:
                    self.counter+=1
                    if self.ignore_pattern and subfolder.startswith(self.ignore_pattern):
                        subdirs.remove(subfolder)
                    else:
                        path= os.path.join(dirName,subfolder)
                        path=normalise(path) #handle NT paths; over max length paths
                        self.update_folder(path)
                except Exception as e:
                    log.warning(e)
                    log.error(f'Error scanning {subfolder} in {dirName}')
            self.save()

    def update_results(self):
        if self.job:
            #log.debug(f'scanned files: {self.counter}')
            progress=f'{((self.counter/self.total)*100):.0f}'
            progress_str=f" {self.counter} of {self.total} files/folders " #0- replace 0 for decimal places
#            log.debug(f'Progress: {progress_str}')
#            log.debug(self.total)
#            log.debug(progress)
            r.hmset(self.job,{
                'progress':progress,
                'progress_str':progress_str,
                'total':self.total,
                })

    def update_folder(self,path):
        if self.specs_dict:
            spec=FileSpecs(path,folder=True)
            docspec=spec.__dict__
            self.files[path]=docspec
        else:
            self.files[path]=FileSpecs(path,folder=True)        
        
    
    def check_reset(self):
        if self.job:
            if self.job[8:] in r.smembers('JOBS_TO_KILL'):
                r.srem('JOBS_TO_KILL',self.job[8:])
                raise TaskReset
    
    def hash_scan(self):
        self.hash_index={}

        for filepath in self.files:
            #print(f'Filepath: {filepath}')
            filespec=self.files.get(filepath)
            is_folder=filespec.get('folder') if self.specs_dict else filespec.folder
            if not is_folder:
                contents_hash=filespec.get('contents_hash') if self.specs_dict else filespec.contents_hash
                if contents_hash:
                    #log.debug(f'Contents hash: {contents_hash}')
                    self.hash_index.setdefault(contents_hash,[]).append(filespec)
    
    def hash_remove(self,_hash,path):
        try:
            duplist=self.hash_index[_hash]
            self.hash_index[_hash]=[item for item in duplist if item['path']!=path]
        except AttributeError:
            #log.debug('no hash_index')
            pass
    
    def hash_append(self,_hash,path):
        try:
            duplist=self.hash_index[_hash]
            filespec=self.files.get(path)
            duplist.append(filespec)
            self.hash_index[_hash]=duplist
        except AttributeError:
            #log.debug('no hash_index')
            pass
        
#        self.save()    

    def check_pickle(self):
        return os.path.exists(os.path.join(self.folder_path,SPECS_FILENAME))

    def get_saved_specs(self):
        fullpath=os.path.join(self.folder_path,SPECS_FILENAME)
        #print(fullpath)
        with open(fullpath,'rb') as f:
            storedindex=pickle.load(f)
            try:
                self.files=storedindex.files
            except:
                raise DoesNotExist('No specs stored')
            try:
                self.specs_dict=storedindex.specs_dict
            except:
                self.specs_dict=True
            try:
                self.hash_index=storedindex.hash_index
            except:
                self.hash_index=None
                
    def save(self):
        try:
            with open(os.path.join(self.folder_path,SPECS_FILENAME),'wb') as f:
                pickle.dump(self,f)
        except Exception as e:
            log.warning(e)
            log.warning(f'Cannot save filespecs in {self.folder_path}')


    def scan_and_save(self):
        try:
            self.scan(specs_dict=self.specs_dict)
        except KeyboardInterrupt:
        	   print('keyboard')
        	   return
        except Exception as e:
            log.warning(e)
        self.save()

    def load_filespecs_or_scan(self):
        """scan filespecs, no rescan"""
        if self.check_pickle():
            try:
                self.get_saved_specs()
            except Exception as e:
                log.warning(e)
                log.warning(f'Cannot load stored filespecs, rescanning')
                self.scan_and_save()
        else:
            self.scan_and_save()        
        
    def scan_or_rescan(self):
        """scan filespecs, rescan if exists"""
        if self.check_pickle():
            
            try:
                self.get_saved_specs()
            except Exception as e:
                log.warning(e)
                log.warning(f'Cannot load stored filespecs; fresh new scan')
                self.scan_and_save()
            try:
                self.rescan()
            except TaskReset:
                log.warning('Folder scan cancelled')
            except Exception as e:
                log.warning(e)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exc(limit=2, file=sys.stdout)
            try:
                self.save()
            except Exception as e:
                log.warning(e)
        else:
            self.scan_and_save()
        
        
    def get_and_rescan(self):
        self.get_saved_specs()
        self.rescan()

    def update_changed(self):
        #update changed files
        self.deletedfiles=[]
        for docpath in self.files:
            oldfile=self.files.get(docpath)
            try:
                self.filelist.remove(docpath)  #self.filelist - disk files - leaving list of new files
            except ValueError:
                if not oldfile.get('folder'):
                    log.debug(f'Filepath {docpath} no longer exists - delete from index')
                    self.deletedfiles.append(docpath)
                    continue                    
            log.debug(f'\'{docpath}\' in _index still exists')
            if changed(oldfile):
                log.info(f'File \'{docpath}\' is modified; updating hash of contents')
                self.update_record(docpath)

    def rescan(self):
        """rescan changed files in dictionary of filespecs"""
        log.info(f'rescanning ... {self.folder_path}')
        self.list_directory() #rescan original disk
        
        log.debug('checking changes')
        self.update_changed()
        
        #log.debug(f'stored files: {self.files}')
        
        #add new files    
        log.info(f'Checking {len(self.filelist)} unscanned files')
        self.counter=0
        for docpath in self.filelist:
            try:            
                if os.path.isdir(docpath):
                    self.update_folder(docpath)
                else:
                    self.update_record(docpath)
            except Exception as e:
                log.info(f'Update failed for {docpath}: {e}')
                #debug:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exc(limit=2, file=sys.stdout)
            #log.debug(f'Added {docpath} to index')
            self.counter+=1
            if self.counter%200==0:
                log.info(f'{self.counter} files updated')
                try:
                    self.save()
                except Exception as e:
                    log.info(f'Save failure: {e}')
        try:
            self.save()
        except Exception as e:
            log.info(f'Save failure: {e}')

        self.reload_index()
        for docpath in self.deletedfiles:
            log.debug(f'deleting {docpath} from scan index')
            try:
                self.delete_record(docpath)
            except Exception as e:
                log.debug(f'Delete record failed for {docpath}')
                log.debug(e)
                #log.debug(self.files)
                #log.debug(deletedfiles)
                raise
        if self.deletedfiles:
            try:
                self.sync()
            except Exception as e:
                log.info(f'Save failure: {e}')

    
    def sync(self):
        self.save()
    
    def reload_index(self):
        pass
        
    def delete_record(self,docpath):
        del(self.files[docpath])
    
    def update_record(self,path, scan_contents=True):
        spec=FileSpecs(path)
        if self.specs_dict:
            docspec=spec.__dict__
            docspec.update({'last_modified':spec.last_modified})
            docspec.update({'length':spec.length})
            if scan_contents:
                if spec.length > 1000000:
                    log.debug(f'checking contents of large file {path} ')
                docspec.update({'contents_hash':spec.contents_hash})
            self.files[path]=docspec
        else:
            self.files[path]=FileSpecs(path)
                
    def list_directory(self):
        filelist=[]
        counter=0
        for dirName, subdirs, fileList in os.walk(self.folder_path): #go through every subfolder in a folder
            #log.info(f'Scanning {dirName} ...')
            for filename in fileList: #now through every file in the folder/subfolder
                if self.ignore_pattern and filename.startswith(self.ignore_pattern):
                    pass
                else:
                    path = os.path.join(dirName, filename)
                    filelist.append(path)
                counter+=1
                if counter%500==0:
                    log.info(f'Collecting paths to {counter} files')
            for subfolder in subdirs:
                if self.ignore_pattern and subfolder.startswith(self.ignore_pattern):
                    subdirs.remove(subfolder)
                else:
                    path= os.path.join(dirName,subfolder)
                    filelist.append(path)
        self.filelist=filelist
#        self.save()

    def dups(self):
        return [k for k in self.hash_index if len(self.hash_index[k])>1]




class PathFileIndex(PathIndex):
    """index of FileSpec objects"""
    def __init__(self,folder,specs_dict=False,scan_contents=True,ignore_pattern='X-',job=None):
        self.job=job
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.files={}
        self.scan(specs_dict=specs_dict,scan_contents=scan_contents)



class BigFileIndex(PathIndex):
    """index of Filespec objects using Klepto"""
    def __init__(self,folder,specs_dict=True,scan_contents=True,ignore_pattern='X-',job=None,label='master'):
        
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.specs_dict=specs_dict
        self.job=job
        
        self.files=klepto_archive.files(os.path.join(self.folder_path,ARCH_FILENAME),label=label)
        self.files.load()
        log.debug(f'loaded files ..{len(self.files)}')
        self.scan_or_rescan()
        self.files.load() #after scanning - load back entire folder scan into memory.

    def save(self):
        #print('saving',len(self.files))
        self.files.dump() #save from cache to filestore
        self.files.clear() #clear memory cache

    def sync(self):
        """clear file index and dump cache"""
        self.files.sync(clear=True)
    
    def delete_record(self,docpath):
        _hash=''
        log.debug(f'deleting \"{docpath}\"')
        try:
            _hash=self.files[docpath].get('contents_hash')
            log.debug(_hash)
        except KeyError:
            pass
        try:
            del(self.files[docpath]) #delete from the memory cache
        except KeyError:
            log.debug('not in index')
            pass
#        try:
#            del(self.files.archive[docpath]) #delete from the disk cache
#        except KeyError:
#            pass
        if _hash:    
            self.hash_remove(_hash,docpath)

    def reload_index(self):
        self.files.load()


    def check_pickle(self):
        if self.files:
            return True #the pickled file is loaded or created on _init
        else:
            return False

    def get_saved_specs(self):
        pass


class StoredPathIndex(PathIndex):
    """retrieve pickled index"""
    def __init__(self,folder_path,ignore_pattern='X-'):
        self.folder_path=folder_path
        self.ignore_pattern=ignore_pattern
        if not self.check_pickle():
            raise DoesNotExist('No stored filespecs')

class StoredBigFileIndex(BigFileIndex):
    """retrieved stored file index without rescan"""
    def __init__(self,folder,specs_dict=True,scan_contents=True,ignore_pattern='X-',label='master'):
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.specs_dict=specs_dict
        self.files=klepto_archive.files(os.path.join(self.folder_path,ARCH_FILENAME),label=label)
        self.files.load()
        #print('loaded files ..',len(self.files))
        if not self.check_pickle():
            raise DoesNotExist('No stored filespecs')
        self.hash_scan()
        self.files.load()

def check_paths(_index):
    """deal with poorly formed windows paths"""
    missing=[]
    for path in [p for p in _index.files][:1000000]:
        if path.startswith(r"R:/$RECYCLE.BIN"):
            continue
        if not os.path.exists(path):
            log.debug(f'Path: \'{path}\' does not exist')
            missing.append(path)
    return missing
        
        
class HashIndex(PathIndex):
    def __init__(self,ignore_pattern='X-'):
        self.ignore_pattern=ignore_pattern
        pass

class SqlFileIndex(sql_connect.SqlIndex,PathIndex):
   def __init__(self,folder_path,job=None,ignore_pattern='X-',rescan=False,label=None):
      """index of file objects using sqlite and sqlalchemy"""
      log.debug(f'Thread: {threading.get_ident()}')
      log.debug(f'Job: {job}')
      self.folder_path=folder_path
      if not os.path.exists(folder_path):
          raise DoesNotExist("Folder to index does not exist")
      self.job=job
      self.ignore_pattern=ignore_pattern
      self.specs_dict=True
      self.counter=0
      self.changed_files_count=0
      self.newfiles=0
      self.total=0
      self.deleted_files_count=0
      self.connect_sql()
      #log.debug(f'loaded files ..{self.count_files}')
      if rescan:
          self.scan_or_rescan()
      
   
#   def _add(self,filepath):
#      name=os.path.basename(filepath)
#      entry=File(name='filename',path=path)
#      self.session.add(entry)
#   
   def get_saved_specs(self):
      pass
       
   def check_pickle(self):
      return True
   
   def update_record(self,path, scan_contents=True,existing=None):
      spec=FileSpecs(path)
      docspec=spec.__dict__
      docspec.update({'last_modified':spec.last_modified})
      docspec.update({'length':spec.length})
      docspec.update({'parent_hash':spec.parent_hash})
      if scan_contents:
         if spec.length > 1000000:
            log.debug(f'checking contents of large file {path} ')
         docspec.update({'contents_hash':spec.contents_hash})
      
      self.map_record(docspec,existing=existing)  

   def update_folder(self,path):
      docspec=FileSpecs(path,folder=True).__dict__
      self.map_record(docspec)

   def hash_append(self,_hash,path):
      try:
          duplist=self.hash_index[_hash]
          filespec=lookup_path(self,path)
          log.debug(filespec)
          if filespec:
              duplist.append(filespec.__dict__)
              self.hash_index[_hash]=duplist
      except AttributeError:           #log.debug('no hash_index')
          pass

   def check_path(self,path,is_folder):
       db_file=None
       try:
          if self.ignore_pattern and path.startswith(self.ignore_pattern):
              return
          if os.path.islink(path):
              return
          path=normalise(path) #convert long or malformed nt paths
          db_file=self.lookup_path(path)
          if db_file:
    #              log.debug(db_file)
              db_file.checked=True
              if not is_folder:
                 if changed(db_file.__dict__):
                     log.info(f'File \'{db_file.path}\' is modified; updating hash of contents')
                     self.changed_files_count+=1
                     self.update_record(db_file.path,existing=db_file)
          else:
              self.newfiles+=1
              #log.debug(f'newfile to add: {path} Directory:{os.path.isdir(path)}')
              self.add_new_file(path)
              if self.newfiles%200==0:
                  log.info(f'{self.newfiles} new filepaths updated')
              try:
                  self.save()
              except Exception as e:
                  log.info(f'Save failure: {e}')
       except PermissionError:
           log.info(f'Cannot check {path}; in use or not permitted')
       except UnicodeEncodeError:
           log.info('Cannot check path')
           try:
               sanitised=re.sub(r'[^\x00-\x7F]+','!?!', path)
               log.info(f'Failed path (SANITISED WITH !?! ): {sanitised}') 
           except Exception as e:
               pass
       except Exception as e:
           log.error(f'Error {e } checking {path}; against database entry {db_file}')
           exc_type, exc_value, exc_traceback = sys.exc_info()
           traceback.print_exc(limit=2, file=sys.stdout)
           if db_file:
               db_file.checked=True
               
   
   def add_new_file(self,path):
       try:            
           if os.path.isdir(path):
               self.update_folder(path)
           else:
               self.update_record(path)
       except DoesNotExist:
           log.info(f'Failed to add {path}: does not exist / no access')
       except PermissionError:
           log.info(f'Failed to add {path}: permission error')
       except OSError:
           log.info(f'Failed to add {path}: OS error')
       except Exception as e:
           log.info(f'Update failed for {path} Exception: {e}')
           #debug:
           exc_type, exc_value, exc_traceback = sys.exc_info()
           traceback.print_exc(limit=2, file=sys.stdout)


   
   def move_path(self,oldpath,newpath):
       spec=self.lookup_path(oldpath)
       moved_inside=new_is_inside(newpath,self.folder_path)
       if spec:
           if moved_inside:
               log.debug('alter filepath')
               spec.path=newpath
           else:
               self.delete_record(oldpath)
               log.debug('removed from database')
       elif moved_inside:
               self.update_record(newpath) #add it
               log.debug(f'added new entry inside {self}')
   	    
               
   def update_changed(self):
      """#update changed files"""
      self.check_reset()
      log.debug('setting all files in database as unchecked')
      self.set_all(False) #mark all files to check
      self.counter,self.newfiles,self.changed_files_count=0,0,0
      self.deletedfiles=[]
      #log.debug(self.filelist)
      self.total=len([p for p,s,f in os.walk(self.folder_path)])
      log.info(f'Scanning {self.total} total folders in {self.folder_path}')
      for folder_path,sub_dirs,file_names in os.walk(self.folder_path):
          self.counter+=1
          #log.debug(f'checking {folder_path}')
          self.update_results()
          self.check_reset()
          if self.counter%100==0:
              log.info(f'checking folder #{self.counter} out of {self.total}')
          if self.counter>1000:
              self.save()          
          if self.ignore_pattern and os.path.basename(folder_path).startswith(self.ignore_pattern):
              continue
          for sub_dir in sub_dirs:
              self.check_path(os.path.join(folder_path,sub_dir),True)
          for filename in file_names:
              
              self.check_path(os.path.join(folder_path,filename),False)
      self.save()
      self.deletedfiles=self.checked_false() #fetch files not checked
      self.deleted_files_count=len(self.deletedfiles)
      log.debug(f'Deleted: {self.deleted_files_count}')
      log.debug(f'New files: {self.newfiles}')

#   def delete_record(self,docpath):
#      log.debug(f'trying to delete record {docpath}')
#      pass
      
   def rescan(self):
      """rescan changed files in dictionary of filespecs"""
      log.info(f'rescanning ... {self.folder_path}')
#        self.list_directory() #rescan original disk
      
      log.debug('checking changes')
      self.update_changed()
      
      try:
         self.save()
      except Exception as e:
         log.info(f'Save failure: {e}')

      for deletedfile in self.deletedfiles:
         log.debug(f'deleting {deletedfile.path} from scan index')
         try:
            self.delete_file(deletedfile)
         except Exception as e:
           log.debug(f'Delete record failed for {deletedfile.path}')
           log.debug(e)
           raise
      if self.deletedfiles:
         try:
            self.sync()
         except Exception as e:
            log.info(f'Save failure: {e}')

def sql_dupscan(folder_path,label=None,job=None):
    log.debug(f'Creating new sql file scanner connection, with job: {job} on folder {folder_path}')
    specs=SqlFileIndex(folder_path,label=label,job=job)
    try:
        specs.scan_or_rescan()
        specs.session.commit()
        return specs
    except Exception as e:
        log.error(f'Exception in dup scanning: {e}')
        specs.session.rollback()
        raise
    finally:
        specs.session.close()

class Index_Maker():
#index_maker
    def __init__(self, path,index_collections,specs=None,masterindex=None, rootpath=DOCSTORE, hidden_files=False,max_depth=1,check_index=True,next_url=''):
        log.info(f'Indexmaker PATH: {path}, ROOTPATH: {rootpath}')
        def _index(root,depth,index_collections,max_depth=1):
            log.debug(f'Root :{root} Depth: {depth}')
            try:
                is_windows_drivelist=win_utils.is_drivelist(root)
                
                files = self.dir_list(root)
                for mfile in files:

                    t = os.path.join(root, mfile)

                    if  is_windows_drivelist:
                        relpath=t
                    elif rootpath=='/':
                        relpath=t
                    else:
                        relpath=os.path.relpath(t,rootpath)


                    #log.debug(f'FILE/DIR: {t} MFILE:{mfile}')
                    if self.isdir(t,is_windows_drivelist):    
                        #log.debug(f"{t},{index_collections}")
                        if check_index:
                            is_collection_root,is_inside_collection=inside_collection(t,index_collections)
                        else:
                            is_collection_root,is_inside_collection=False,False
                        #log.debug(is_inside_collection)
                        if depth==max_depth-1:
                            yield self.folder_html_nosub(mfile,relpath,path,is_collection_root,is_inside_collection)
                        else:
                            subfiles=_index(os.path.join(root, t),depth+1,index_collections)
                            #log.debug(f'ROOT:{root},SUBFILES:{subfiles}')
                            yield self.folder_html(mfile,relpath,subfiles,path,is_collection_root,is_inside_collection)
                        continue
                    else:
                        #files
                        if MODELS and check_index:
                            _stored,_indexed=model_index(t,index_collections)
                        else:
                            _stored,_indexed=None,None
                        try:
                            dupcheck=SqlDupCheck(t,specs,masterindex)
                        except Exception as e:
                            log.error(e)
                        #log.debug(f'Local check: {t},indexed: {_indexed}, stored: {_stored}')
                        #log.debug(f'Dupcheck: {dupcheck.__dict__}')
                        yield self.file_html(mfile,_stored,_indexed,dupcheck,relpath,path)
                        continue
            except PermissionError:
                log.debug(f'Permission error while reading: {root}')
        basepath=os.path.join(rootpath,path)
        try:
            file_count=len([filename for filename in os.listdir(basepath)]) if hidden_files else len([filename for filename in os.listdir(basepath) if not is_hidden_file(filename)])
        except PermissionError as e:
            log.info(f'Permission error accessing {basepath}')
            raise EmptyDirectory('Permission denied to display contents of folder')
        if file_count==0:
            raise EmptyDirectory('No files to display in folder')
        
        #log.debug('Basepath: {}'.format(basepath))
        if os.path.isdir(basepath):
            self._index=_index(basepath,0,index_collections,max_depth=max_depth)
        else:
            raise Not_A_Directory('not a valid path to a folder')
    
    @staticmethod
    def dir_list(root):
        if win_utils.is_drivelist(root):
            return win_utils.get_drives()
        else:
            return os.listdir(root)

    @staticmethod    
    def isdir(path,is_windows_drivelist):
        if is_windows_drivelist:
            return True
        else:
            return os.path.isdir(path)
        
    @staticmethod
    def file_html(mfile,_stored,_indexed,dupcheck,relpath,path):	
        return loader.render_to_string('documents/filedisplay/p_file.html',{
                            'file': mfile, 
                            'local_index':_stored,
                            'indexed':_indexed,                    
                            	})
                            	
    @staticmethod
    def folder_html(mfile,relpath,subfiles,path,is_collection_root,is_inside_collection):
        return loader.render_to_string('documents/filedisplay/p_folder.html',
        {'file': mfile,
         'filepath':relpath,
         'rootpath':path,
         'subfiles': subfiles,
         'is_collection_root':is_collection_root,
         'is_inside_collection':is_inside_collection,
         })
         
    @staticmethod
    def folder_html_nosub(mfile,relpath,path,is_collection_root,is_inside_collection):
        return loader.render_to_string('documents/filedisplay/p_folder_nosub.html',
            {'file': mfile,
             'filepath':relpath,
             'rootpath':path,
             'is_collection_root':is_collection_root,
             'is_inside_collection':is_inside_collection,
            })
#
class Dups_Index_Maker(Index_Maker):
    @staticmethod
    def file_html(mfile,_stored,_indexed,dupcheck,relpath,path):
        return loader.render_to_string('dups/p_file.html',{
                            'file': mfile, 
                            'local_index':_stored,
                            'indexed':_indexed,
                            'dupcheck':dupcheck,
                            'filepath':relpath,
                            'rootpath':path,
                            	})
    @staticmethod
    def folder_html(mfile,relpath,subfiles,path,is_collection_root,is_inside_collection):
        return loader.render_to_string('dups/p_folder.html',
        {'file': mfile,
         'filepath':relpath,
         'rootpath':path,
         'subfiles': subfiles,
         'is_collection_root':is_collection_root,
         'is_inside_collection':is_inside_collection,
         })
         
    @staticmethod
    def folder_html_nosub(mfile,relpath,path,is_collection_root,is_inside_collection):
        return loader.render_to_string('dups/p_folder_nosub.html',
            {'file': mfile,
             'filepath':relpath,
             'rootpath':path,
             'is_collection_root':is_collection_root,
             'is_inside_collection':is_inside_collection,
            })


def update_file(_file):
    newspecs=FileSpecs(_file.filepath,scan_contents=False)
    _file.last_modified = time_utils.timestamp2aware(newspecs.last_modified)
    _file.filesize = newspecs.length
    _file.save()

def changed_file(_file):
    newspecs=FileSpecs(_file.filepath,scan_contents=False)
    
    
    log.debug(f'Comparing.. LAST-MOD Old: {_file.last_modified} New: {time_utils.timestamp2aware(newspecs.last_modified)} LENGTH Old: {_file.filesize} New: {newspecs.length}')
    
    if _file.last_modified != time_utils.timestamp2aware(newspecs.last_modified) or _file.filesize != newspecs.length:
        log.debug('file changed')
        return True
    return False


class Dups_Lister(Dups_Index_Maker):
    def __init__(self):
        pass
    

def changed(oldspecs):
    #log.debug(oldspecs)
    if not oldspecs.get('folder'): #ignore folders
        if 'path' not in oldspecs:
            return True
        try:
            docpath=oldspecs['path']
            newspecs=FileSpecs(docpath,scan_contents=False)
            #log.debug(f'LastM:{newspecs.last_modified},LEN: {newspecs.length}')
            if oldspecs['last_modified'] != newspecs.last_modified or oldspecs['length'] != newspecs.length:
                return True
        except DoesNotExist:
            log.debug(f'\'{docpath}\'Does not exist')
        except Exception as e:
            log.debug(e)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exc(limit=2, file=sys.stdout)
            return True
    return False



    

def filespecs(parent_folder,specs_dict=False,scan_contents=True,job=None): #  
    specs=PathFileIndex(parent_folder,specs_dict=specs_dict,scan_contents=scan_contents,job=job)
    return specs.files

def hashspecs(parent_folder): #  
    """return filespecs dict keyed to hash; ignore folders"""
    hashspecs={}
    for dirName, subdirs, fileList in os.walk(parent_folder): #go through every subfolder in a folder
        for filename in fileList: #now through every file in the folder/subfolder
            path = os.path.join(dirName, filename)
            specs=FileSpecs(path)
            hashspecs[specs.contents_hash]=specs
    return hashspecs


#DOWNLOADS / SERVE FILE

def make_download(file_path):
    return make_file(file_path,'application/force-download')
    
def make_file(file_path,content_type):    
    if not os.path.exists(file_path):
        raise DoesNotExist
    cleanfilename=slugify(os.path.basename(file_path))
    with open(file_path, 'rb') as thisfile:
            #response=HttpResponse(thisfile.read(), )
            response=HttpResponse(thisfile.read(), content_type=content_type)
            response['Content-Disposition'] = 'inline; filename=' + cleanfilename
    return response

#HASH FILE FUNCTIONS

def parent_hashes(filepaths):
    "list of hashes of parent paths of files"""
    if isinstance(filepaths, list):
        pathhashes=[]
        for path in filepaths:
            pathhashes.append(parent_hash(path))
        return pathhashes
    else:
        return [parent_hash(filepaths)]

def parent_hash(filepath):
    """hash of a file's parent directory"""
    parent,filename=os.path.split(filepath)
    return pathHash(parent)
        
def pathHash(path):
    path=Path(path).as_posix()  #convert windows paths to unix paths for consistency across platforms
    m=hashlib.md5()
    m.update(path.encode('utf-8')) #encoding avoids unicode error for unicode paths
    return m.hexdigest()

def get_contents_hash(path,blocksize = 65536):
    afile = open(path, 'rb')
    hasher = hashlib.sha256()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return hasher.hexdigest()

#SCANNING

def file_tree(folder):
    """generator to scan directory tree"""
    for dirName, subdirs, fileList in os.walk(folder):
        for filename in fileList:
            yield os.path.join(dirName,filename)

#CHECK DUPS
def check_local_dups(folder,scan_index=None,master_index=None):
    """generator of dups within scan folder"""
    _t=file_tree(folder)
    for path in _t: 
        ck=DupCheck(path,scan_index,master_index)
        if ck.local_dup:
            yield ck

def check_master_dups(folder,scan_index=None,master_index=None):
    """generator of dups within scan folder"""
    _t=file_tree(folder)
    for path in _t: 
        ck=DupCheck(path,scan_index,master_index)
        if ck.master_dup:
            yield ck

def check_master_dups_html(folder,scan_index=None,master_index=None,rootpath=''):
    dupLister=Dups_Lister()
    #slice_start=0
    slice_stop=500
    log.debug(f'Looking for dups inside {folder}')
    sqldups=master_index.dups_inside(folder,limit=slice_stop)
    for dup,_hash,dupcount in sqldups:
        log.debug(f'checking {dup.path}')
        ck=DupCheckFile(dup,scan_index,master_index,master_dupcount=dupcount)
        _stored,_indexed=None,None
        filename=os.path.basename(dup.path)
        relpath=os.path.relpath(dup.path,rootpath)
        log.debug(f'Relpath: {relpath}')
        yield dupLister.file_html(filename,_stored,_indexed,ck,relpath,folder)

def check_local_dups_html(folder,scan_index=None,master_index=None,rootpath='',combo=None,orphans=False):
    dupLister=Dups_Lister()
    slice_start=0
    slice_stop=500
    
    if combo:
        if orphans:
            duplist=combo.orphans[slice_start:slice_stop]
        else:
            duplist=combo.dups[slice_start:slice_stop]
        for dup,_hash,dupcount in duplist:
            #log.debug(f'checking {dup.path} with rootpath{rootpath}')
            #ck=DupCheckFile(dup,scan_index,master_index,master_dupcount=dupcount)
            
            try:
                ck=SqlDupCheck(dup.path,scan_index,master_index,)
            except Exception as e:
                log.error(e)
                continue
            _stored,_indexed=None,None
            #log.debug(ck.__dict__)
            filename=os.path.basename(dup.path)
            relpath=dup.path if rootpath=='/' else os.path.relpath(dup.path,rootpath)
            #log.debug(f'Relpath: {relpath}')
            yield dupLister.file_html(filename,_stored,_indexed,ck,relpath,folder)

#    _t=file_tree(folder)
#    
#    dupLister=Dups_Lister()
#    
#    for path in _t: 
#        log.debug(f'checking {path}')
#        ck=SqlDupCheck(path,scan_index,master_index)
#        if ck.master_dup:
##            if MODELS:
##                _stored,_indexed=model_index(t,index_collections)
##            else:
#            _stored,_indexed=None,None
#            
#            filename=os.path.basename(path)
#            relpath=os.path.relpath(path,rootpath)
#            yield dupLister.file_html(filename,_stored,_indexed,ck,relpath,folder)
#


def check_local_orphans(folder,scan_index=None,master_index=None):
    """generator of locally-unique files within scan folder"""
    _t=file_tree(folder)
    for path in _t: 
        ck=SqlDupCheck(path,scan_index,master_index)
        if not ck.local_dup:
            yield ck
        
def check_master_orphans(folder,scan_index=None,master_index=None):
    """generator of locally-unique files within scan folder"""
    _t=file_tree(folder)
    for path in _t: 
        ck=SqlDupCheck(path,scan_index,master_index)
        if not ck.master_dup:
            yield ck
        


#DELETE FILES

def delete_file(path):
    if os.path.exists(path):
        try:
            send2trash(path)
        except Exception as e:
            log.error(e)
        return not os.path.exists(path)
    else:
        return False

#MOVE FILES

def move_file(source,dest):
    """move file, no overwrite"""
    if os.path.exists(dest):
        log.info(f'Move failed: destination file \'{dest}\' exists already.')
        return False
    if not os.path.exists(source):
        log.info(f'Move failed: source file \'{source}\' does not exist')
        return False
    shutil.move(source,dest)
    return True
    


#PATH METHODS

def is_inside(filepath, folder):
    """filepath inside a folder"""
    path=os.path.realpath(filepath)
    return path.startswith(folder)

def new_is_inside(filepath,folder):
    """filepath inside a folder"""
    if filepath.startswith(folder):
        if os.path.commonpath([filepath,folder])==folder:
            return True
        else:
            return False
    else:
        return False

def is_down(relpath, root=DOCSTORE):
    """is down folder tree"""
    path=os.path.abspath(os.path.join(root,relpath))
    return path.startswith(root)

def is_absolute(path,root=DOCSTORE):
    return path.startswith(root)
    
def relpath_exists(relpath,root=DOCSTORE):
    if root:
        return os.path.exists(os.path.join(root,relpath))
    else:
        return False

def make_relpath(path,docstore=''):
    if not docstore:
        docstore=DOCSTORE
    return os.path.relpath(path,start=docstore)


def relpath_valid(relpath,root=DOCSTORE):
    """check relative path exists, is a sub of the docstore, and is not an absolute path"""
    return relpath_exists(relpath,root=root) and not is_absolute(relpath,root=root) and is_down(relpath,root=root)
    

def is_hidden_file(filename):
    return filename.startswith('.')
    #TODO CHECKS FOR WINDOWS

def directory_tags(path,isfile=False):
    """make subfolder tags from full filepath"""
    #returns fullrelativepath,folder,basename,hash_relpath
    log.debug('Path: {}'.format(path))
    drive,path_and_file=os.path.splitdrive(path)
    a,b=os.path.split(path_and_file)
    if drive:
        a=os.path.join(drive,a)
    #print (drive,a,b)
    if isfile:
        tags=[]
    else:
        a_hash=pathHash(path)
        tags=[(path,a,b,a_hash)]
    path=a
    while True:
        drive,path_and_file=os.path.splitdrive(path)
        a,b=os.path.split(path_and_file)
        if drive:
            a=os.path.join(drive,a)
        #print (drive,a,b)
        if drive and b=='' and a !='':
            #print('root')
            b=drive
            a=''
            
        elif b=='/' or b=='' or b=='\\':
            break
        a_hash=pathHash(path)
        tags.append((path,a,b,a_hash))
        path=a
        
    tags=tags[::-1]
    log.debug(f'Tags: {tags}')
    return tags

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value, fileExt = os.path.splitext(value)
    originalvalue=value
    try:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')        
        value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
        value = unicode(re.sub('[-\s]+', '-', value))
    except NameError: #python3
    #except IndexError:
        value = unicodedata.normalize('NFKD', originalvalue).encode('ascii', 'ignore').decode()
        value = re.sub('[^\w\s-]', '', value).strip().lower()
        value = re.sub('[-\s]+', '-', value) if value else 'filename'
        #value=value.encode('ascii','ignore')      
    return value+fileExt

def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def check_paths(folder):
    """check filenames can be scanned on an windows system"""
    for dir,subdirs, files in os.walk(folder):
        for subdir in subdirs:
            x=os.path.join(dir,subdir)
            x=normalise(x)
            if not os.path.exists(x):
                log.error(f'Cannot find subfolder {x}')
        for filepath in files:
            x=os.path.join(dir,filepath)
            x=normalise(x)
            if not os.path.exists(x):
                log.error(f'Cannot find file {x}')
    


def normalise(path):
    """handle long windows filenames or paths ending in spaces"""
    try:
        path=os.path.normpath(path)
        if os.name=='nt' and len(path)>255 and not path.startswith("\\\\?\\"):
            return u"\\\\?\\"+path
        elif os.name=='nt' and (path.endswith(" ") or path.endswith("."))and not path.startswith("\\\\?\\"):
            return u"\\\\?\\"+path
        else:
            return path
    except Exception as e:
        log.warning(e)
        return path

def safe_hash(_hash):
    if len(_hash)<201:
        if re.match("^[a-z0-9]+$", _hash):
            return True
    return False
    
    
    


#FILE MODEL METHODS
def model_index(path,index_collections,hashcheck=False):
    """check if True/False file in collection is in database, return File object"""
    
    if not index_collections:
        return None,None
    
    stored=File.objects.filter(filepath=path, collection__in=index_collections)
    #log.debug(stored)
    if stored:
        indexed=stored.exclude(solrid='')
        #log.debug(indexed)
        return True,indexed
    else:
        return None,None
        
def find_database_files(path):
    return File.objects.filter(filepath=path)
    
    
def find_live_files(path):
    l=find_database_files(path)
    return [f for f in l if f.collection.live_update]

def find_live_collections(path):
    match_collections=[]
    for collection in live_collections():
        if is_inside(path, collection.path) and path !=collection.path:
            match_collections.append(collection)
    return match_collections    

def live_collections():
    return [c for c in Collection.objects.all() if c.live_update]            
        
def find_collections(path):
    match_collections=[]
    for collection in Collection.objects.all():
        if is_inside(path, collection.path) and path !=collection.path:
            match_collections.append(collection)
    return match_collections

def inside_collection(path,_collections):
    """return is collection path or inside collection"""
    if not _collections:
        return False,False
    for collection in _collections:
#        log.debug(path)
#        log.debug(collection.path)
        if new_is_inside(path, collection.path):
            if path==collection.path:
                return True,False
            else:
                return False,True
    return False,False

    
#DUP CHECKS
class DupCheck:
    def __init__(self,filepath,specs,masterindex):
        self.filepath=filepath
        self.specs=specs
        self.masterindex=masterindex
        #log.debug(self.__dict__)
        #log.debug(self.specs.files)
        self.dups=None
        self.local_dup=False
        self.master_dup=None
        try:
            self.check()
        except Exception as e:
            log.error(f'Exception {e}')
            raise
    def check(self):
        self.contents_hash=''
        if self.masterindex:
            #print(f'FILES: {masterindex.files}')
            self.master_scan=True if self.filepath in self.masterindex.files else False
            if self.master_scan:
                master_filespec=self.masterindex.files.get(self.filepath)
                if master_filespec:
                    self.master_changed=changed(master_filespec)
                    if not self.master_changed:
                        self.contents_hash=master_filespec.get('contents_hash')
                        self.size=sizeof_fmt(master_filespec.get('length'))
        if self.specs: 
            self.local_scan=True if self.filepath in self.specs.files else False
            if self.local_scan:
                filespec=self.specs.files[self.filepath]
                #log.debug(f'Filespec: {filespec}')
                self.local_changed=changed(filespec)
                if not self.local_changed:
                    self.contents_hash=filespec.get('contents_hash')
                    self.size=sizeof_fmt(filespec.get('length'))

        if self.contents_hash:
            if self.masterindex:
                self.hash_in_master=True if self.contents_hash in self.masterindex.hash_index else False
            if self.specs:
                if self.specs.hash_index:
                    dupcount=len(self.specs.hash_index.get(self.contents_hash,[]))
                    if dupcount>1:
                        self.local_dup=True
                        self.dups=dupcount
                    else:
                        self.local_dup=False
                        
            if self.masterindex:
                if self.masterindex.hash_index:     
                    if self.contents_hash in self.masterindex.hash_index:
                        #log.debug(self.masterindex.hash_index[self.contents_hash])
                        dupcount=len(self.masterindex.hash_index[self.contents_hash])
                        if dupcount>1:
                            self.master_dup=True
                            self.m_dups=dupcount
                        else:
                            self.master_dup=False
                            
                    else:
                        self.master_dup=False

class SqlDupCheck(DupCheck):
    def check(self):
        self.contents_hash=''
        if not os.path.exists(self.filepath):
            raise DoesNotExist("Checking nonexistent file")
        if self.masterindex:
            #print(f'FILES: {masterindex.files}')
            
            master_filespec=self.masterindex.lookup_path(self.filepath)
            #log.debug(master_filespec)
            #log.debug(master_filespec.__dict__)
            self.master_scan=True if master_filespec else False
            if master_filespec:
                if True:
                    self.master_changed=changed(master_filespec.__dict__)
                    if not self.master_changed:
                        self.contents_hash=master_filespec.contents_hash
                        self.size=sizeof_fmt(master_filespec.length)
        if self.specs: 
            filespec=self.specs.lookup_path(self.filepath)
            self.local_scan=True if filespec else False
            if filespec:
                #log.debug(f'Filespec: {filespec}')
                self.local_changed=changed(filespec.__dict__)
                if not self.local_changed:
                    self.contents_hash=filespec.contents_hash
                    self.size=sizeof_fmt(filespec.length)

        if self.contents_hash:
            if self.specs:
                dupcount=self.specs.count_hash(self.contents_hash)
                if dupcount>1:
                    self.local_dup=True
                    self.dups=dupcount
                else:
                    self.local_dup=False
                        
            if self.masterindex:
                master_dupcount=self.masterindex.count_hash(self.contents_hash)
                #log.debug(f'Dupchek for {self} hash: {self.contents_hash} count:{master_dupcount}')
                self.hash_in_master=True if master_dupcount>0 else False
                if master_dupcount>1:
                    self.master_dup=True
                    self.m_dups=master_dupcount
                else:
                    self.master_dup=False


class DupCheckFile():
    def __init__(self,_file,specs,masterindex,master_dupcount=None):
        self.specs=specs
        self.masterindex=masterindex
        self._file=_file
        self.master_dupcount=master_dupcount
        #log.debug(self.__dict__)
        #log.debug(self.specs.files)
        self.dups=None
        self.local_dup=False
        self.master_dup=None
        self.check()


    def check(self):
        self.contents_hash=''
        
        if self.masterindex:
            #print(f'FILES: {masterindex.files}')
            self.master_scan=True
            #master_filespec=self.masterindex.lookup_path(self.filepath)
            #log.debug(master_filespec)
            #log.debug(master_filespec.__dict__)
            self.master_changed=changed(self._file.__dict__)
            if not self.master_changed:
                self.contents_hash=self._file.contents_hash
                self.size=sizeof_fmt(self._file.length)
                
                
#        if self.specs: 
#            filespec=self.specs.lookup_path(self.filepath)
#            self.local_scan=True if filespec else False
#            if filespec:
#                #log.debug(f'Filespec: {filespec}')
#                self.local_changed=changed(filespec.__dict__)
#                if not self.local_changed:
#                    self.contents_hash=filespec.contents_hash
#                    self.size=sizeof_fmt(filespec.length)

        if self.contents_hash:
#            if self.specs:
#                dupcount=self.specs.count_hash(self.contents_hash)
#                if dupcount>1:
#                    self.local_dup=True
#                    self.dups=dupcount
#                else:
#                    self.local_dup=False
                        
            if self.masterindex:
                if not self.master_dupcount:
                    self.master_dupcount=self.masterindex.count_hash(self.contents_hash)
                #log.debug(f'Dupchek for {self} hash: {self.contents_hash} count:{master_dupcount}')
                self.hash_in_master=True if self.master_dupcount>0 else False
                if self.master_dupcount>1:
                    self.master_dup=True
                    self.m_dups=self.master_dupcount
                else:
                    self.master_dup=False


                            
def specs_list(_index,_hash):
    return [f for f in _index.lookup_hash(_hash)]

def specs_path_list(_index,_hash):
    duplist=specs_list(_index,_hash)
    path_list=[]
    for dup in duplist:
        path_list.append(dup.path)
    return path_list
    

class SqlFolderIndex(SqlFileIndex):


   
   def rescan(self):

       self.rescan_folders()
       self.rescan_files
   
   def rescan_files(self):
       self.changed_files_count=0
       n=0
       deleted_dbfiles=[]
       deleted_files=0
       new_files,self.counter=0,0

       self.delete_folder_files() # remove db files in deleted folders
       
       
       for _folder in self.folders:
           #log.debug(_folder)
           
           
           self.counter+=1
           self.update_results() #update cache progress meter
           self.check_reset()
           if self.counter%100==0:
               log.info(f'checking folder #{self.counter} out of {self.total}')
           if self.counter>1000:
               self.save()          
           if self.ignore_pattern and os.path.basename(_folder.path).startswith(self.ignore_pattern):
               continue
           try:    
               files_on_disk=[f.path for f in os.scandir(_folder.path)]
           except FileNotFoundError:
               log.info(f'Folder not found {_folder.path}')
               continue
           for db_file in self.list_folder(_folder.path):
               try:
                   files_on_disk.remove(db_file.path)#check if db_file exists
               except ValueError:
                   deleted_dbfiles.append(db_file)
                   deleted_files+=1
               if not db_file.folder:
                   if changed(db_file.__dict__):
                       log.info(f'File \'{db_file.path}\' is modified; updating hash of contents')
                       self.changed_files_count+=1
                       self.update_record(db_file.path,existing=db_file)
                       n+=1
#               if n>20:
#                   raise Exception
           #files remaining are new
           if files_on_disk:
               print(f'New files in folder ({_folder.path}): {len(files_on_disk)}')
               for path in files_on_disk:
                   if self.ignore_pattern and path.startswith(self.ignore_pattern):
                       continue
                   if os.path.islink(path):
                       continue
                   path=normalise(path) #convert long or malformed nt paths
                   self.add_new_file(path)
           #delete the deleted files
           if deleted_dbfiles:
               for deletedfile in deleted_dbfiles:
                   self.delete_dbfile(deletedfile)
               try:
                   self.sync()
               except Exception as e:
                   log.info(f'Save failure: {e}')
                   
      
   def rescan_folders(self):
      """rescan changed files in dictionary of filespecs"""

      log.info(f'rescanning folders in ... {self.folder_path}')      
      self.check_reset()
      self.counter,self.newfolders=0,0
      self.deleted_folders=[]

      #self.total=len([p for p,s,f in os.walk(self.folder_path)])
      
      #make dictionary of files in db
      folders_in_db={}
      for f in self.folders:
          folders_in_db[f.path]=f

      self.total=len(folders_in_db)
      log.info(f'Scanning folders in {self.folder_path}')
      log.debug(f'Found {self.total} in database already')

      newfolders=[]
      for _folder,sub_dirs,file_names in os.walk(self.folder_path):
          fullpath=normalise(os.path.join(self.folder_path,_folder))
          try:
              #print(fullpath)
              folders_in_db.pop(fullpath)
          except KeyError:
              log.debug(f'Folder not in db : {fullpath}')
              newfolders.append(fullpath)
      self.dbfolders_to_delete=folders_in_db
      
      #remove deleted folders from folders table
      log.debug(f'Deleted folders (first 10) of {len(self.dbfolders_to_delete)}: {[f for f in self.dbfolders_to_delete][:10]}')
      self.delete_dbfolders()

      #add new folders to db
      log.debug(f'Adding {len(newfolders)} new folders')
      for f in newfolders:
          if self.ignore_pattern and os.path.basename(f).startswith(self.ignore_pattern):
              continue
          self.check_folder_path(f)

      try:
         self.save()
      except Exception as e:
         log.info(f'Save failure: {e}')
         

   def delete_dbfolders(self):
       """delete files from db folder table"""
       for folderpath in self.dbfolders_to_delete:
           try:
               self.delete_file(self.dbfolders_to_delete[folderpath])
               self.deleted_folders.append(folderpath)
           except Exception as e:
               log.debug(f'Delete record failed for {deletedfolder.path}')
               log.debug(e)
           
           
           
   def delete_folder_files(self):
       """delete db files inside a folder path""" 
       log.debug('Removing db files from deleted folders')
       while True:
           try:
               folderpath=self.deleted_folders.pop()
               for db_file in self.list_folder(folderpath):
                   log.debug(f'deleting {db_file.path} from scan index')
                   self.delete_dbfile(db_file)               
           except IndexError:
               break
       try:
           self.sync()
       except Exception as e:
           log.info(f'Save failure: {e}')

       
   def delete_dbfile(self,db_file):
       try:
           self.delete_file(db_file)
       except Exception as e:
           log.debug(f'Delete record failed for {db_file.path}')
           log.debug(e)
           #raise

   def list_folder(self,folder_path):
       _hash=pathHash(folder_path)
       #log.debug(_hash)
       return self.lookup_parent_hash(_hash)
       
   
   def check_folder_path(self,path):
       db_folder=None
       try:
          if self.ignore_pattern and path.startswith(self.ignore_pattern):
              return
          if os.path.islink(path):
              return
          path=normalise(path) #convert long or malformed nt paths
          db_folder=self.lookup_folder(path)
          if db_folder:
              db_folder.checked=True
          else:
              self.newfolders+=1
              log.debug(f'New folder to add: {path} Directory:{os.path.isdir(path)}')
              try:            
                  if os.path.isdir(path):
                       self.add_folder(path)
                  else:
                      pass
              except DoesNotExist:
                  log.info(f'Failed to add {path}: does not exist / no access')
              except PermissionError:
                  log.info(f'Failed to add {path}: permission error')
              except OSError:
                  log.info(f'Failed to add {path}: OS error')
              except Exception as e:
                  log.info(f'Update failed for {path} Exception: {e}')
                  #debug:
                  exc_type, exc_value, exc_traceback = sys.exc_info()
                  traceback.print_exc(limit=2, file=sys.stdout)
              if self.newfolders%200==0:
                  log.info(f'{self.newfolders} new folders updated')
              try:
                  self.save()
              except Exception as e:
                  log.info(f'Save failure: {e}')
       except PermissionError:
           log.info(f'Cannot check {path}; in use or not permitted')
       except UnicodeEncodeError:
           log.info('Cannot check path')
           try:
               sanitised=re.sub(r'[^\x00-\x7F]+','!?!', path)
               log.info(f'Failed path (SANITISED WITH !?! ): {sanitised}') 
           except Exception as e:
               pass
       except Exception as e:
           log.error(f'Error {e } checking {path}; against database entry {db_folder}')
           exc_type, exc_value, exc_traceback = sys.exc_info()
           traceback.print_exc(limit=2, file=sys.stdout)
           if db_folder:
               db_folder.checked=True


def add_parent_hashes(_index):
    maxid=_index.max_id
    n=0
    while n*1000<maxid:
        pagestart=n*1000
        pageend=((n+1)*1000)-1
        for f in _index.id_range(pagestart,pageend):
            f.parent_hash=parent_hash(f.path)
        n+=1
        if n%100==0:
            print (n)
            _index.save()
    _index.save()
                   