# -*- coding: utf-8 -*-
import string,os
from ctypes import windll

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
            drives.append(letter)
        bitmask >>= 1

    return drives
    
    
    