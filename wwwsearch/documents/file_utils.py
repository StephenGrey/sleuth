# -*- coding: utf-8 -*-
import os, logging,hashlib,re,datetime,unicodedata,pickle,time
from pathlib import Path
from collections import defaultdict
from klepto.archives import *

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

class FileSpecs:
    def __init__(self,path,folder=False,scan_contents=True):
        self.path=path
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
            
            
            for subfolder in subdirs:
                self.counter+=1
                if self.ignore_pattern and subfolder.startswith(self.ignore_pattern):
                    subdirs.remove(subfolder)
                else:
                    path= os.path.join(dirName,subfolder)
                    self.update_folder(path)
            self.save()

    def update_results(self):
        log.debug(f'scanned files: {self.counter}')
        progress=f'{((self.counter/self.total)*100):.0f}'
        progress_str=f" disk {self.counter} of {self.total} files/folders " #0- replace 0 for decimal places
        log.debug(f'Progress: {progress_str}')
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
        
    
    def hash_scan(self):
        self.hash_index={}

        for filepath in self.files:
            #print(f'Filepath: {filepath}')
            filespec=self.files.get(filepath)
            is_folder=filespec.get('folder') if self.specs_dict else filespec.folder
            #print(f'Folder: {is_folder}')
            #print(f'Filespecs: {filespec}')
            if not is_folder:
                contents_hash=filespec.get('contents_hash') if self.specs_dict else filespec.contents_hash
                if contents_hash:
                    #log.debug(f'Contents hash: {contents_hash}')
                    self.hash_index.setdefault(contents_hash,[]).append(filespec)

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
            except Exception as e:
                log.warning(e)
            try:
                self.save()
            except Exception as e:
                log.warning(e)
        else:
            self.scan_and_save()
        
        
    def get_and_rescan(self):
        self.get_saved_specs()
        self.rescan()
        
    def rescan(self):
        """rescan changed files in dictionary of filespecs"""
        log.info(f'rescanning ... {self.folder_path}')
        self.list_directory() #rescan original disk
        deletedfiles=[]
        

        #update changed files
        for docpath in self.files:
            oldfile=self.files.get(docpath)
            try:
                self.filelist.remove(docpath)  #self.filelist - disk files - leaving list of new files
            except ValueError:
                if not oldfile.get('folder'):
                    log.debug(f'Filepath {docpath} no longer exists - delete from index')
                    deletedfiles.append(docpath)
                    continue                    
            if changed(oldfile):
                log.info(f'File \'{docpath}\' is modified; updating hash of contents')
                self.update_record(docpath)
        
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
        for docpath in deletedfiles:
            log.debug(f'deleting {docpath} from scan index')
            try:
                self.delete_record(docpath)
            except Exception as e:
                log.debug(e)
                log.debug(self.files)
                log.debug(deletedfiles)
                raise
        if deletedfiles:
            try:
                self.save()
            except Exception as e:
                log.info(f'Save failure: {e}')

    
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
    def __init__(self,folder,specs_dict=True,scan_contents=True,ignore_pattern='X-',job=None):
        
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.specs_dict=specs_dict
        self.job=job
        
        self.files=file_archive(os.path.join(self.folder_path,ARCH_FILENAME),cache=False)
        self.files.load()
        log.debug(f'loaded files ..{len(self.files)}')
        self.scan_or_rescan()
        self.files.load() #after scanning - load back entire folder scan into memory.

    def save(self):
        #print('saving',len(self.files))
        self.files.dump() #save from cache to filestore
        self.files.clear() #clear memory cache

    def delete_record(self,docpath):
        del(self.files[docpath]) #delete from the disk cache

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
    def __init__(self,folder,specs_dict=True,scan_contents=True,ignore_pattern='X-'):
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.specs_dict=specs_dict
        self.files=file_archive(os.path.join(self.folder_path,ARCH_FILENAME),cache=False)
        self.files.load()
        #print('loaded files ..',len(self.files))
        if not self.check_pickle():
            raise DoesNotExist('No stored filespecs')
        self.hash_scan()
        self.files.load()


           
class HashIndex(PathIndex):
    def __init__(self,ignore_pattern='X-'):
        self.ignore_pattern=ignore_pattern
        pass

class Index_Maker():
#index_maker
    def __init__(self, path,index_collections,specs=None,masterindex=None, rootpath=DOCSTORE, hidden_files=False):
        log.info(f'Indexmaker PATH: {path}, ROOTPATH: {rootpath}')
        def _index(root,depth,index_collections,maxdepth=2):
            #log.debug(f'Root :{root} Depth: {depth}')
            try:
                
                files = self.dir_list(root)
                for mfile in files:
                    t = os.path.join(root, mfile)
                    relpath=os.path.relpath(t,rootpath)
                    #print(f'FILE/DIR: {t}')
                    if os.path.isdir(t):    
                        #log.debug(f"{t},{index_collections}")
                        is_collection_root,is_inside_collection=inside_collection(t,index_collections)
                        #log.debug(is_inside_collection)
                        if depth==maxdepth-1:
                            yield self.folder_html_nosub(mfile,relpath,path,is_collection_root,is_inside_collection)
                        else:
                            subfiles=_index(os.path.join(root, t),depth+1,index_collections)
                            #log.debug(f'ROOT:{root},SUBFILES:{subfiles}')
                            yield self.folder_html(mfile,relpath,subfiles,path,is_collection_root,is_inside_collection)
                        continue
                    else:
                        #files
                        if MODELS:
                            _stored,_indexed=model_index(t,index_collections)
                        else:
                            _stored,_indexed=None,None
                        dupcheck=DupCheck(t,specs,masterindex)
                        #log.debug(f'Local check: {t},indexed: {_indexed}, stored: {_stored}')
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
            self._index=_index(basepath,0,index_collections)
        else:
            raise Not_A_Directory('not a valid path to a folder')
    
    @staticmethod
    def dir_list(root):
        if root=='/' and os.name=='nt':
            return ['C','D'] #TODO replace with Windows volume list
        else:
            return os.listdir(root)
        
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


def changed_file(_file):
    newspecs=FileSpecs(_file.filepath,scan_contents=False)
    
    
    log.debug(f'Comparing.. LAST-MOD Old: {_file.last_modified} New: {time_utils.timestamp2aware(newspecs.last_modified)} LENGTH Old: {_file.filesize} New: {newspecs.length}')
    
    if _file.last_modified != time_utils.timestamp2aware(newspecs.last_modified) or _file.filesize != newspecs.length:
        log.debug('file changed')
        return True
    return False



def changed(oldspecs):
    if not oldspecs.get('folder'): #ignore folders
        if 'path' not in oldspecs:
            return True
        docpath=oldspecs['path']
        newspecs=FileSpecs(docpath,scan_contents=False)
        if oldspecs['last_modified'] != newspecs.last_modified or oldspecs['length'] != newspecs.length:
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
    a,b=os.path.split(path)
    if isfile:
        tags=[]
    else:
        a_hash=pathHash(path)
        tags=[(path,a,b,a_hash)]
    path=a
    while True:
        a,b=os.path.split(path)

        if b=='/' or b=='' or b=='\\':
            #print('break')
            
            break
        a_hash=pathHash(path)
        tags.append((path,a,b,a_hash))
        path=a
        
    tags=tags[::-1]
    #log.debug(f'Tags: {tags}')
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


#FILE MODEL METHODS
def model_index(path,index_collections,hashcheck=False):
    """check if True/False file in collection is in database, return File object"""
    
    stored=File.objects.filter(filepath=path, collection__in=index_collections)
    #log.debug(stored)
    if stored:
        indexed=stored.exclude(solrid='')
        #log.debug(indexed)
        return True,indexed
    else:
        return None,None
        
def find_collections(path):
    match_collections=[]
    for collection in Collection.objects.all():
        if is_inside(path, collection.path) and path !=collection.path:
            match_collections.append(collection)
    return match_collections

def inside_collection(path,_collections):
    """return is collection path or inside collection"""
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
        self.check()
        

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
                            
