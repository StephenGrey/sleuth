# -*- coding: utf-8 -*-
import string,os,itertools,platform

if os.name=='nt':
    from ctypes import windll,cdll

class NotWindows(Exception):
    pass

def get_drives():
    try:
        assert os.name=='nt'
    except AssertionError as e:
    	    print(e)
    	    raise NotWindows
    	
    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(letter+':/')
        bitmask >>= 1

    return drives

def get_available_drives():
    if 'Windows' not in platform.system():
        return []
    drive_bitmask = cdll.kernel32.GetLogicalDrives()
    return list(itertools.compress(string.ascii_uppercase,
               map(lambda x:ord(x) - ord('0'), bin(drive_bitmask)[:1:-1])))
   
   
def is_drivelist(path):
    if path=='/' and os.name=='nt':
        return True
    else:
        return False
        
        