import sqlite3, os,logging,threading
log = logging.getLogger('ownsearch.sql_connect')
from documents import file_utils
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import aliased
Base = declarative_base()
from sqlalchemy.orm import sessionmaker
CACHE={}
ARCH_FILENAME='.sqlfilespecs.db'

class SqlFileIndex(file_utils.PathIndex):
   def __init__(self,folder_path,job=None,ignore_pattern='X-',rescan=False,label=None):
      """index of file objects using sqlite and sqlalchemy"""
      log.debug(f'Thread: {threading.get_ident()}')
      
      self.folder_path=folder_path
      self.job=job
      self.ignore_pattern=ignore_pattern
      self.specs_dict=True
      if not self.folder_path:
          self.engine = create_engine('sqlite:///:memory:', echo=False)
      else:
          self.engine = create_engine(f'sqlite:///{os.path.join(self.folder_path,ARCH_FILENAME)}', echo=False)
      Base.metadata.create_all(self.engine)
      Session = sessionmaker(bind=self.engine)
      self.session=Session()
        
      log.debug(f'loaded files ..{self.count_files}')
      if rescan:
          self.scan_or_rescan()
     
   def _add(self,filepath):
      name=os.path.basename(filepath)
      entry=File(name='filename',path=path)
      self.session.add(entry)
   
   def get_saved_specs(self):
      pass
       
   def check_pickle(self):
      return True
   
   def save(self):
      self.session.commit()         
      
   def sync(self):
      self.session.commit()
   
   def update_record(self,path, scan_contents=True,existing=None):
      spec=file_utils.FileSpecs(path)
      docspec=spec.__dict__
      docspec.update({'last_modified':spec.last_modified})
      docspec.update({'length':spec.length})
      if scan_contents:
         if spec.length > 1000000:
            log.debug(f'checking contents of large file {path} ')
         docspec.update({'contents_hash':spec.contents_hash})
      
      self.map_record(docspec,existing=existing)  

   def update_folder(self,path):
      docspec=file_utils.FileSpecs(path,folder=True).__dict__
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
   
   def update_changed(self):
      """#update changed files"""
      self.deletedfiles=[]
      #log.debug(self.filelist)
      for _file in self.files:
          stored_file=_file
          #log.debug(stored_file.path)
          try:
              self.filelist.remove(stored_file.path)  #self.filelist - disk files - leaving list of new files
          except ValueError:
              if not stored_file.folder:
                    log.debug(f'Filepath \"{stored_file.path}\" no longer exists - delete from index')
                    self.deletedfiles.append(stored_file)
                    continue                    
          if file_utils.changed(stored_file.__dict__):
              log.info(f'File \'{stored_file.path}\' is modified; updating hash of contents')
              self.update_record(stored_file.path,existing=stored_file)
            	
   def map_record(self,docspec,existing=None):
      if existing:
         _file=existing
      else:
         _file=File(path=docspec.get('path'))
      _file.name=docspec.get('name')
      _file.last_modified=docspec.get('last_modified')
      _file.scan_contents=docspec.get('scan_contents')
      _file.shortname=docspec.get('shortname')
      _file.ext=docspec.get('ext')
      _file.folder=docspec.get('folder')
      _file.length=docspec.get('length')
      _file.contents_hash=docspec.get('contents_hash')     
      if not existing:
          log.debug(f'adding new file {_file}')
          self.session.add(_file)
   
   def delete_record(self,_file):
      _hash=''
      log.debug(f'deleting \"{_file.path}\"')
      try:
         _hash=_file.contents_hash
         log.debug(_hash)
      except KeyError:
         pass
      try:
         self.session.delete(_file)
      except KeyError:
         log.debug(f'{_file} delete failed from index')
         pass
      if _hash:    
         self.hash_remove(_hash,_file.path)
   
   def lookup_path(self,path):
       return self.session.query(File).filter(File.path==path).first()

   def lookup_hash(self,_hash):
       return [f for f in self.session.query(File).filter(File.contents_hash==_hash)]
       
   def count_hash(self,_hash):
       return self.session.query(File).filter(File.contents_hash==_hash).count()

   def dup_hashes(self,n=1):
       return self.session.query(File.contents_hash,func.count(File.contents_hash)).group_by(File.contents_hash).having(func.count(File.contents_hash)>n)
   
   @property
   def dups(self):
       _hashes=self.dup_hashes().subquery()
       return self.session.query(File,_hashes).join(_hashes,File.contents_hash==_hashes.c.contents_hash)

   def dups_inside(self,folder):
       return self.dups.filter(File.path.startswith(folder))


   @property
   def count_files(self):
       return self.session.query(File).count()

   @property
   def files(self):
       return (f for f in self.session.query(File).all()) 

   def hash_scan(self):
       self.hash_index={}
       for _file in self.files:
            is_folder=_file.folder
            if not is_folder:
                if _file.contents_hash:
                    self.hash_index.setdefault(_file.contents_hash,[]).append(_file.__dict__)
     
class File(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    path = Column(String,index=True)
    contents_hash = Column(String,index=True)
    name=Column(String)
    length = Column(Integer)
    last_modified=Column(Float)
    scan_contents=Column(Boolean)
    shortname=Column(String)
    ext=Column(String)
    folder=Column(Boolean)
        
    def __repr__(self):
        return "<File(name='%s', path='%s', hash='%s', id='%s')>" % (
                           self.name, self.path, self.contents_hash,self.id)
                           
class ArchiveLocked(Exception):
    pass

def files(archive_location,label='master',rescan=False):
    """return a sql archive object"""
    log.debug(f'fetching archive for {archive_location}')
    return retrieve_or_create(archive_location,label,rescan=rescan)
    
def retrieve_or_create(path,label, rescan=False):
    stored=CACHE.get(path)
    if stored:
        if stored.get('locked'):
            raise ArchiveLocked
        else:
            log.debug('using cached file archive')
            return stored.get('archive')
    else:
        existing=[k for k,v in CACHE.items() if v.get('label')==label]
        if existing:
            for item in existing:
                log.debug(f'removing from cache index with label {label } path {item}')
                del(CACHE[item])
        else:
            archive=SqlFileIndex(path,rescan=rescan)
            archive.hash_scan()
        CACHE[path]={
        	'archive':archive,
        	'label':label,
        	'locked':False,
        		}
        return archive


def is_locked(archive):
    path=archive.archive.state['id']
    stored=CACHE.get(path)
    return stored.get('locked')
    

def set_lock(archive):
    path=archive.archive.state['id']
    log.debug(path)
    stored=CACHE.get(path)
    log.debug(stored)
    if stored:
        stored['locked']=True
        CACHE[path].update(stored)






