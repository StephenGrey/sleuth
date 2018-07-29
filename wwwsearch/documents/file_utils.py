# -*- coding: utf-8 -*-
import os, logging
from ownsearch.hashScan import pathHash
try:
    from django.template import loader
    from documents.models import File
    from usersettings import userconfig as config
    BASEDIR=config['Models']['collectionbasepath'] #get base path of the docstore
    log = logging.getLogger('ownsearch.docs.file_utils')    
except:
    #make usable outside the project
    pass


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
    
    
    


#PATH METHODS
def is_down(relpath, root=BASEDIR):
    path=os.path.abspath(os.path.join(root,relpath))
    return path.startswith(root)

def is_absolute(path,root=BASEDIR):
    return path.startswith(root)
    
def relpath_exists(relpath,root=BASEDIR):
    if BASEDIR:
        return os.path.exists(os.path.join(BASEDIR,relpath))
    else:
        return False

def relpath_valid(relpath,root=BASEDIR):
    """check relative path exists, is a sub of the docstore, and is not an absolute path"""
    return relpath_exists(relpath,root=root) and not is_absolute(relpath,root=root) and is_down(relpath,root=root)
    
def index_maker(path,index_collections):
    def _index(root,depth,index_collections):
        #print ('Root',root)
        if depth<2:
            files = os.listdir(root)
            for mfile in files:
                t = os.path.join(root, mfile)
                relpath=os.path.relpath(t,BASEDIR)
                if os.path.isdir(t):
                    subfiles=_index(os.path.join(root, t),depth+1,index_collections)
                    #print(root,subfiles)
                    yield loader.render_to_string('filedisplay/p_folder.html',
                                                   {'file': mfile,
                                                   	'filepath':relpath,
                                                   	'rootpath':path,
                                                    'subfiles': subfiles,
                                                    	})
                    continue
                else:
                    stored,indexed=model_index(t,index_collections)
                    #log.debug('Local check: {},indexed: {}, stored: {}'.format(t,indexed,stored))
                    yield loader.render_to_string('filedisplay/p_file.html',{'file': mfile, 'local_index':stored,'indexed':indexed})
                    continue
    basepath=os.path.join(BASEDIR,path)
    log.debug('Basepath: {}'.format(basepath))
    if os.path.isdir(basepath):
        return _index(basepath,0,index_collections)
    else:
        return "Invalid directory"

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
    log.debug(tags)
    return tags


#FILE MODEL METHODS

def model_index(path,index_collections,hashcheck=False):
    """check if file scanned into model index"""
    stored=File.objects.filter(filepath=path, collection__in=index_collections)
    if stored:
        indexed=stored.exclude(solrid='')
        return True,indexed
    else:
        return None,None



