# -*- coding: utf-8 -*-
from klepto.archives import *
import logging
log=logging.getLogger('ownsearch.klepto_archive')

CACHE={}


class ArchiveLocked(Exception):
    pass

def files(archive_location,label='master',sql=False):
    """return a klepto file archive object"""
    log.debug(f'fetching archive for {archive_location}')
    return retrieve_or_create(archive_location,label,sql=sql)
    
def retrieve_or_create(path,label,sql=False):
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
        
        log.debug(f'loading file archive into cache')
        if sql:
            archive=sql_files(path)
        else:
            archive=file_archive(path,cache=False)
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
        

def sql_files(path):
    return sql_archive(f"sqlite:///{path}sql.db")


