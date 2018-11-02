import json
from klepto.archives import *

DEFAULT_ROOT_FILENAME='R:/temp/dumper'
DEFAULT_ARCHIVE='R:/temp/klepto'


def dumpthis(_dict):
    counter=0
    chunk=0

    chunk_data={}
    for key in _dict:
        counter+=1
        chunk_data[key]=_dict[key]
        
        if counter%40000==0:
            chunk+=1
            result=save_chunk(chunk_data,chunk)
            chunk_data={}
            
def save_chunk(chunk_data,chunk):
    _thisfile=f'{filename}{str(chunk)}'
    print(f'saving chunk {chunk} to filename {_thisfile}')
    try:
        with open(_thisfile,'w') as f:
        	    json.dump(chunk_data,f)
        return True
    except Exception as e:
        print(e)
        return False

def load_chunk(chunk,root_filename):
    _thisfile=f'{root_filename}{str(chunk)}'
    print(f'trying to load {_thisfile}')
    try:
        with open(_thisfile,'r') as f:
            chunk_data=json.load(f)
    except Exception as e:
        print(e.__dict__)
        chunk_data=None
    return chunk_data

def load_this(start=0,root_filename=DEFAULT_ROOT_FILENAME):
    counter=start
    _dict={}
    
    while True:
        counter+=1
        chunk_data=load_chunk(counter,root_filename)
        if not chunk_data:
            break
        _dict.update(chunk_data)
    return _dict

def archive_dict(_dict,archive=DEFAULT_ARCHIVE):
    arch=file_archive(archive)
    counter=0
    for key,value in _dict.items():
        counter+=1
        arch[key]=value
        if counter%20000==0:
            arch.sync()
            print('saving to disk')
    
def archive_direct(_dict,archive=DEFAULT_ARCHIVE):
    arch=file_archive(archive,cache=False)
    counter=0
    for key,value in _dict.items():
        counter+=1
        arch.archive[key]=value
#        if counter%20000==0:
#            arch.sync()
#            print('saving to disk')
def json_to_klepto(root_filename=DEFAULT_ROOT_FILENAME,archive=DEFAULT_ARCHIVE):
    _dict=load_this(start=0,root_filename=root_filename)
    archive_dict(_dict,archive=archive)
    
    
    
    
    
    
    
    
    
    
	
    
    
    
    
    
    
            