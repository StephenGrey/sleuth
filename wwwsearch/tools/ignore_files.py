import os,fnmatch
try:
    from configs import config
    PATTERNS=[r'{}'.format(x) for x in config['Dups']['ignore_patterns'].split(',') ]#get base path of the docstore
except Exception as e:
    #make usable outside the project
    print(e)
    PATTERNS=None
    pass

print(PATTERNS)

def match_any(text,patterns=PATTERNS):
	"check if text matches any regex patterns"
	if PATTERNS:
		return any(fnmatch.fnmatch(text,pattern) for pattern in PATTERNS)
	else:
		return None

def list_matches(folder,patterns=PATTERNS):
    """list files in folder that match patterns"""
    _list=[]
    assert os.path.exists(folder)
    for dirName, subdirs, fileList in os.walk(folder): #go through every subfolder in a folder
        for filename in fileList: #now through every file in the folder/subfolder
            filepath=os.path.join(dirName,filename)
            if match_any(filepath,patterns=patterns):
                _list.append(filepath)
    return _list


