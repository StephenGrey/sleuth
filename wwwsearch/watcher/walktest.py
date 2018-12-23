import os

def walking(path,ignore_pattern='X-'):
    for dirName, subdirs, fileList in os.walk(path): #go through every subfolder in a folder
        print(f'Scanning {dirName} Subdirs: {subdirs}  fileList: {fileList}...')
        #this works:
        #notify(f'Scanning {dirName}',f'Subdirs: {subdirs}  fileList: {fileList}...')
        
        for filename in fileList: #now through every file in the folder/subfolder
            pass
#                self.files[path]=FileSpecs(path)
#    
        for subfolder in subdirs:
            if subfolder.startswith(ignore_pattern):
               print('ignore this one: ',subfolder)
               subdirs.remove(subfolder)
            path= os.path.join(dirName,subfolder)
 

def notify(title, text):
    os.system("""
              osascript -e 'display notification "{}" with title "{}"'
              """.format(text, title))

#notify("Title", "Heres an alert")



walking(path)
