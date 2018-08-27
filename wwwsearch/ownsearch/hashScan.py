# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
# extract from dupFinder.py
import os, sys, logging
import hashlib
import time
log = logging.getLogger('ownsearch.hashscan')

#new structure: key:[[filespecsx],[filespecsx+1]] etc where filespecs  = [path,filelen,shortName,fileExt,modTime]

def FileSpecTable(parentFolder): #  MAIN ROUTINE FOR BUILDING SIMPLE FILE SPECS TABLE KEYED TO pATH
    deetdict = {}  #dictionary of filespecs
    #print ('Scanning directory tree to create filespecs index.')
    #print ('Folders scanned ...')
    count=0
    for dirName, subdirs, fileList in os.walk(parentFolder): #go through every subfolder in a folder
        count+=1
        if count%100==0:
            #print ('...',count)
            pass
        for filename in fileList: #now through every file in the folder/subfolder
#######GET FILE SPECS
            # Get the path to the file
            path = os.path.join(dirName, filename)
            if os.path.exists(path)==True: #check file exists
                # Get file specs
                shortName, fileExt = os.path.splitext(filename)
                filelen=os.path.getsize(path) #get file length
                modTime = os.path.getmtime(path) #last modified time
#            print (time.strftime("%d%b%Y %H:%M:%S",time.gmtime(modTime)))

    #######ADD TO DICTIONARY
                if path in deetdict:  #if there is already a copy
                    specs = deetdict[path]
                    specs.append([path,filelen,shortName,fileExt,modTime])#add new specs to old specs for same hash
                    deetdict[path] = specs
                else:  #first or only version of the file
                    deetdict[path]=[path,filelen,shortName,fileExt,modTime]  #first item in list of specs for potential duplicate
                    
            else:
                print(('ERROR: File not Found: ',path))
    return deetdict



def findDup(parentFolder):  #check duplicates in a file folder  MAIN ROUTINE FOR FINDING DUPLICATE
    # Dups in format {hash:[names]}
    dups = {}  #dictionary of dups
    lendups = {} #the length of the files
    for dirName, subdirs, fileList in os.walk(parentFolder): #go through every subfolder in a folder
        print('Scanning %s...' % dirName)
        for filename in fileList: #now through every file in the folder/subfolder
            # Get the path to the file
            path = os.path.join(dirName, filename)
            # Calculate hash
            file_hash = hashfile256(path)
#            # Calculate filesize (for info)
#            file_size = os.path.getsize(path)
#            print ('file_size:',file_size) #for debugging
            # Add or append the file path
            if file_hash in dups:  #if there is already a copy
                dups[file_hash].append(path) #add the path
#                print (file_hash,os.path.getsize(path)) #debug
                lendups[file_hash].append(os.path.getsize(path))  #adding filesize dict
            else:
                dups[file_hash] = [path]
                lendups[file_hash]=[os.path.getsize(path)]
    return dups,lendups
 
def HexFolderTable(parentFolder):
    """ Build a simple file specs dictionary, keyed to hash of contents """
    deetdict = {}  #dictionary of dups
    for dirName, subdirs, fileList in os.walk(parentFolder): #go through every subfolder in a folder
        try:
            print('Scanning %s...' % dirName)
        except: # catch errors printing
            e=sys.exc_info()[0]
            print(('Error in printing foldername:',e))
        for filename in fileList: #now through every file in the folder/subfolder
#######GET FILE SPECS
            # Get the path to the file
            path = os.path.join(dirName, filename)
            if os.path.exists(path)==True: #check file exists
                # Calculate hash
                shortName, fileExt = os.path.splitext(filename)
                try: #modified to switch from MD5 to sha256 hash function
                    file_hash = hashfile256(path)
                except IOError as e:
                    file_hash = None
                    print (str(e))
                    log.error(str(e))
                if file_hash is not None:
                    filelen=os.path.getsize(path) #get file length
                    modTime = os.path.getmtime(path) #last modified time
    #            print (time.strftime("%d%b%Y %H:%M:%S",time.gmtime(modTime)))
                # Add or append the file path
        #######ADD TO DICTIONARY
                    if file_hash in deetdict:  #if there is already a copy
                        specs = deetdict[file_hash]
                        specs.append([path,filelen,shortName,fileExt,modTime])#add new specs to old specs for same hash
                        deetdict[file_hash] = specs
                    else:  #first or only version of the file
                        deetdict[file_hash]=[[path,filelen,shortName,fileExt,modTime]]  #first item in list of specs for potential duplicate
                else: #if file hash is None:
                    #pass
                    #debug:
                    print(('file hash is None for ' , path))
            else:
                print(('ERROR: File not Found: ',path))
    return deetdict

def HexDetails(path):
    if os.path.exists(path)==True: #check file exists
                # Calculate hash
                head,filename=os.path.split(path)
                shortName, fileExt = os.path.splitext(filename)
                file_hash = hashfile256(path)
                filelen=os.path.getsize(path) #get file length
                modTime = os.path.getmtime(path) #last modified time
                return file_hash,[path,filelen,shortName,fileExt,modTime]
    else:
        return None,None

def hashfile(path, blocksize = 65536):
    afile = open(path, 'rb')
    hasher = hashlib.md5()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return hasher.hexdigest()

def hash256(text):
    hash_object = hashlib.sha256(text)
    # Assumes the default UTF-8
    return hash_object.hexdigest()

def hashfile256(path,blocksize = 65536):
    afile = open(path, 'rb')
    hasher = hashlib.sha256()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return hasher.hexdigest()

# Joins two dictionaries - which key a list
def joinDicts(dict1, dict2):
    for key in dict2.keys():
        if key in dict1:
            dict1[key] = dict1[key] + dict2[key] #the lists are joined 
        else:
            dict1[key] = dict2[key]
    return dict1
 
def DupsScan(folders):
        dups = {}
        lens= {}
        resultmess = []
        for i in folders:
                # Iterate the folders given
            if os.path.exists(i):
                    # Find the duplicated files and append them to the dups
                    newdup,newlen=findDup(i)
                    dups=joinDicts(dups, newdup)
                    lens=joinDicts(lens,newlen)
                    
            else:
                    print('%s is not a valid path, please verify' % i)
                    sys.exit()
        return dups,lens


def printResults(duplist):
    resulttext = []
    count = 0
    if len(duplist)> 200:
        print ('Displaying first 200 results ...')
    if len(duplist) > 0:
        print('Duplicates Found:')
        resulttext.append('The content of the following files is identical:\n\n')
        print('The content of the following files is identical:')
        print('___________________')
        for filelen,hasher,result in duplist:
            count += 1
            for subresult in result:
                print('\t\t%s\t%s\t%s' % (subresult[2],displaynumb(filelen),subresult[0]))
                resulttext.append('%s\t%s\t%s\n' % (subresult[2],filelen,subresult[0]))
            print('___________________')
            resulttext.append('\n\n')
            if count > 200:
                break
        return resulttext
    else:
        print('No duplicate files found.')
	
	

# OLD WORKING CODE
#    resulttext = []
#    results = list(filter(lambda x: len(x) > 1, dict1.values()))
#    #print (dict1)
#    #print (lendix)
#    if len(results) > 0:
#        print('Duplicates Found:')
#        resulttext.append('The content of the following files is identical:\n\n')
#        print('The content of the following files is identical:')
#        print('___________________')
#        for result in results:
#            for subresult in result:
#                print('\t\t%s' % subresult)
#                resulttext.append('%s\n' % subresult)
#            print('___________________')
#            resulttext.append('\n\n')
#        return resulttext
# 
#    else:
#        print('No duplicate files found.')


def choosedir():
        file_path = eg.diropenbox('Choose a Directory to Scan','DUPLICATE-FINDER')
        folders = [file_path]
        print(('Folder to scan:',folders))

        reply = "Choose ANOTHER Directory"
        while reply == "Choose ANOTHER Directory":
            choices = ["Choose ANOTHER Directory","Quit","Execute"]
            reply = eg.buttonbox("DUPLICATE CHECK: What do you want to do?", choices=choices)
            if reply == 'Quit':
                sys.exit()
            elif reply == 'Choose ANOTHER Directory':
                file_path = eg.diropenbox('Choose a second Directory to Scan','DUPLICATE-FINDER')
                folders.append(file_path)
                print(('Folder to scan:',file_path))
        return folders
    
def dupfind(folders):
	if folders ==[]:
		choices=['Choose folder to scan for Duplicates','Quit']
		reply = eg.buttonbox("FOLDER CHOICE?", choices=choices)
		if reply=='Quit':
			return
		folders=choosedir()
	dups=DupsScan16(folders)
	#print(dups)
#	duplicates,lengths=DupsScan(folders) #go look for duplicates, return hex dictionary ;file length dict
	
	return dups
	
def displaynumb(num):
	if num >= 1000000000: #gigabytes:
		gigs=int(num/1000000)/100
		numstring = str(gigs)+' Gb'
	elif num >= 1000000: #megabytes
		megs=int(num/10000)/100
		numstring = str(megs)+' Mb'
	elif num >= 1000: #kilobytes
		kb=int(num/10)/100
		numstring = str(kb)+' Kb'
	else:
		numstring = str(num)+ ' bytes'
	return numstring

	
def testdup():
	dups=dupfind(['/Users/Stephen/Documents/Dropbox/REUTERS/Russia'])
	printResults(dups)
	return dups

def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
    return m.hexdigest()
	
if __name__ == '__main__':   #ASK USER TO CHOOSE A DIRECTORY FOLDER, OR SEVERAL, AND LOOK FOR DUPS
    if len(sys.argv) > 1: 
        folders = sys.argv[1:]
        print(('from arguments, folders s:',folders))
    else:
        folders = []
    dups = dupfind(folders)
    printResults(dups)

