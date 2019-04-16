import sqlite3, os,logging,threading,sys,traceback
log = logging.getLogger('ownsearch.sql_connect')
#from documents import file_utils
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import aliased
from sqlalchemy.orm import sessionmaker
Base = declarative_base()

CACHE={}
ARCH_FILENAME='.sqlfilespecs.db'


class SqlIndex():
    def connect_sql(self):
        if not self.folder_path:
            self.engine = create_engine('sqlite:///:memory:', echo=False)
        else:
            self.engine = create_engine(f'sqlite:///{os.path.join(self.folder_path,ARCH_FILENAME)}', echo=False,
            connect_args={'check_same_thread': False}
            )
        
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session=Session()

    def save(self):
        try:
            self.session.commit()
        except sqlite3.OperationalError as e:
            log.error(f'Op Error: {e}') 
        except sqlite3.InvalidRequestError as e:
            log.error(f'InvalidReqError: {e}') 
        except Exception as e:
            log.error(e)         
      
    def sync(self):
        try:
            self.session.commit()
        except Exception as e:
            log.error(e)
            
      
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
            #log.debug(f'adding new file {_file}')
            self.session.add(_file)
   
   
   
    def delete_record(self,docpath):
        try:
            _file=self.lookup_path(docpath)
            if _file:
                log.debug(f'deleting \"{docpath}\"')
                self.delete_file(_file)
                log.debug(f'delete done')
            else:
                log.debug('Delete failed - no database record found')
                pass 
        except Exception as e:
            log.error(f'{docpath} delete failed from index; exception {e}')


    def delete_file(self,_file):
        try:
            self.session.delete(_file)
            self.save()
        except KeyError:
            log.debug(f'{docpath} delete failed from index')
            pass
        except sqlite3.OperationalError as e:
            self.session.rollback()
            log.debug(f'{docpath} delete failed from index with exception {e}')
            raise
        except Exception as e:
            log.debug(f'{docpath} delete failed from index with exception {e}')
            self.session.rollback()
            raise
   
    def lookup_path(self,path):
        #log.debug(path)
        try:
            return self.session.query(File).filter(File.path==path).first()
        except Exception as e:
            log.error(e)
            self.session.rollback()
            raise
        

    def lookup_hash(self,_hash):
        try:
            return [f for f in self.session.query(File).filter(File.contents_hash==_hash)]
        except Exception as e:
            log.error(e)
            return []
            
    def count_hash(self,_hash):
        return self.session.query(File).filter(File.contents_hash==_hash).count()

    def dup_hashes(self,n=1):
        return self.session.query(File.contents_hash,func.count(File.contents_hash)).group_by(File.contents_hash).having(func.count(File.contents_hash)>n)
    
    def checked_false(self):
        return  [f for f in self.session.query(File).filter(File.checked==False)]
        
   
    @property
    def dups(self):
        _hashes=self.dup_hashes().subquery()
        return self.session.query(File,_hashes).join(_hashes,File.contents_hash==_hashes.c.contents_hash)

    def dups_inside(self,folder,limit=500):
        return self.dups.filter(File.path.startswith(folder)).order_by(File.length.desc()).limit(limit)

    @property
    def count_files(self):
        return self.session.query(File).count()

    @property
    def files(self):
        return (f for f in self.session.query(File).all())
        
    def files_inside(self,folder,limit=500):
        return self.session.query(File.contents_hash,File.id).filter(File.path.startswith(folder)).order_by(File.length.desc()).limit(limit) 

#   def hash_scan(self):
#       self.hash_index={}
#       for _file in self.files:
#            is_folder=_file.folder
#            if not is_folder:
#                if _file.contents_hash:
#                    self.hash_index.setdefault(_file.contents_hash,[]).append(_file.__dict__)

    def set_all(self,flag):
        self.session.query(File.checked).update({File.checked:flag})
        self.session.commit()
      
#ALTER TABLE db3.files ADD COLUMN checked Boolean


class ComboIndex():
    def __init__(self,master_index,local_index,folder=None):
        log.debug(f'looking for dups in {master_index} and {local_index} inside {folder}')
        self.i1=master_index
        self.i2=local_index
        if folder:
            self.query=self.i2.files_inside(folder)
        else:
            self.query=self.i2.session.query(File.contents_hash,File.id).all()
        self.folder=folder

        
    def find_master_dups(self):
       #check scan hashes in master
       self.dups_in_master={}
       for _hash,_id in self.query:
           dups=self.i1.count_hash(_hash)
           if dups>0:
               self.dups_in_master[_hash]=dups
       #log.debug(f"Dups in master: {self.dups_in_master}")
    
    @property
    def dups(self):
       self.find_master_dups()
       if self.folder:
           self.local_dups=self.i2.dups_inside(self.folder)
       else:
           self.local_dups=self.i2.dups
       self.combine_dups()
       return self.combodups
       
    def combine_dups(self):
       self.combodups=[]
       hashes_in_both=set()
       for dup,_hash,localcount in self.local_dups:
           if _hash:
               if _hash in self.dups_in_master:
                   #log.debug(f'dups in both: local{dup}')
                   totalcount=localcount+self.dups_in_master[_hash]
                   self.combodups.append((dup,_hash,totalcount))
                   hashes_in_both.add(_hash)
               else:
                   self.combodups.append((dup,_hash,localcount))
       for _hash in hashes_in_both:
                   try:
                       del self.dups_in_master[_hash]
                   except KeyError:
                       log.debug('deletion error')
       
       
       for _hash in self.dups_in_master:
           if _hash:
               mastercount=self.dups_in_master[_hash]
               local_files=self.i2.lookup_hash(_hash)
               #log.debug(local_files)
               for _file in local_files:
                   self.combodups.append((_file,_hash,mastercount+1))
    #               =self.dups_in_master[dup.contents_hash]
#           else:
 
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
    checked=Column(Boolean)
        
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






