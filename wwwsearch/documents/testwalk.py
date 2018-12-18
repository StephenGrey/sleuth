from . import file_utils
from .file_utils import PathIndex
import os, logging
try:
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    log = logging.getLogger('ownsearch.docs.file_utils')
    log.debug('Logging in operation')  
except:

    print('No logging')
    pass



def hashspecs(parent_folder): #  
    """return filespecs dict keyed to hash; ignore folders"""
    hashspecs={}
    for dirName, subdirs, fileList in os.walk(parent_folder): #go through every subfolder in a folder
        for filename in fileList: #now through every file in the folder/subfolder
            path = os.path.join(dirName, filename)
            specs=file_utils.FileSpecs(path)
            hashspecs[specs.contents_hash]=specs
    return hashspecs
    

class TestIndex(PathIndex):
    """index of FileSpec objects"""
    def __init__(self,folder,specs_dict=False,scan_contents=False,ignore_pattern='X-'):
        self.folder_path=folder
        self.ignore_pattern=ignore_pattern
        self.scan(specs_dict=specs_dict,scan_contents=scan_contents)

def testwalk(folder):
        for dirName, subdirs, fileList in os.walk(folder): #go through every subfolder in a folder
            log.info(f'Scanning {dirName} ...')
            print(f'Scanning {dirName} ...')
            
            

