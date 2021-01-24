# -*- coding: utf-8 -*-
import os,logging,shutil
#from msg_parser import MsOxMessage
from documents.file_utils import SqlFileIndex
from documents.file_utils import normalise
import extract_msg,olefile,sys

from pathlib import Path
log = logging.getLogger('ownsearch.emailcrawler')

_relpath='msg'
_relpath2='msg2'
DOCBASE=os.path.abspath(os.path.join(os.path.dirname(__file__),'../tests/testdocs'))
TESTPATH=os.path.join(DOCBASE,_relpath)
TESTPATH2=os.path.join(DOCBASE,_relpath2)

"""
HUNT DUPLICATE .MSG FILES BASED ON MESSAGE ID

(using two methods to find message ID)

"""



def db(path=TESTPATH):
    """return a message index"""
    return MessageIndex(path,label='messages')

class MessageIndex(SqlFileIndex):
    """sql database of a file directory containing .msg files"""
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def message_scan(self):
        """add missing message_id to database"""
        mcount=0
        nullcount=0
        for f in self.files:
            mcount+=1
            if not f.document_id:
                xt = os.path.splitext(f.name)[1]
                if xt=='.msg':
                    _id=message_id(f.path)
                    if not _id:
                        nullcount+=1
                    f.document_id=_id
                    
                    try:
                    #print(f'Message name: {f.name}')
                        print(f'Message ID: {_id}')if _id else None
                    except Exception as e:
                        log.debug(e)
        print(f'Scanned: {mcount}files; no id retrieved {nullcount}')
        self.save()            

    def message_dups(self):
        """return all messages that are duplicates"""
        return self.dup_doc_id()
    
    def list_message_dups(self):

        for d in self.message_dups().all():
            if d[0]=='': #ignore files with NO message_id
                continue
            yield d,self.lookup_doc_id(d.document_id)
#            dups.append(self.lookup_doc_id(dup.document_id))
#        return dups

    def _inspect(self):
        """list meta for duplicate messages"""
        for d,files in self.list_message_dups():
            print(d)
            for f in files:
                print(f.contents_hash)
                print(f.last_modified)
                print(f.length)
                print(f.path)
                if not os.path.exists(f.path):
                    print(f'File {f.path} does not exist')
    def purge(self,target):
        """ move all duplicates (apart from first) to a target folder"""
        _count=0
        for d,files in self.list_message_dups():
            _count+=1
            files2remove=files[1:] #no preference on which copy to keep
            self.remove_files(files2remove,target)
        print(f'Removed {_count}files')
#    def add_orphans(self,search_folder=TESTPATH2):
#    	       for filepath in search_orphans(self,target):
#    	           
   
    def move_all(self,target):
        for d,files in self.list_message_dups():
            files2remove=files
            self.remove_files(files2remove,target)

    def remove_files(self,files2remove,target):
        """ move a list of files to folder - recreating file tree
              except if already exists"""
        for f in files2remove:
            if target:
                folder,filename=os.path.split(f.path)
                print(f' oldfolder{folder}, path {self.folder_path}')
                relfolder=relpath(folder,self.folder_path)
                newfolder=os.path.join(target,relfolder)
                make_folder(newfolder) #make target folder if doesnt exist
                try:
                    newpath=normalise(os.path.join(newfolder,filename))
                    print(f'moving {f.path} to {newpath}')
                    os.rename(f.path,newpath)
                except FileExistsError:
                    log.debug(f'file {f.path}exists at destination')
                    os.remove(f.path)
                except FileNotFoundError:
                    log.debug(f'file {f.path}not found ')
                    log.debug(f'new filename {filename} newfolder:{newfolder}')

            else:
                log.info('No destination specified')
    def list_blanks(self):
        return self.lookup_doc_id("")
    
    def copy_blanks(self,target):
    	    assert os.path.exists(target)
    	    
    	    for f in self.list_blanks():
    	    	if not os.path.isdir(f.path):
    	    	    shutil.copy2(f.path,os.path.join(target,os.path.basename(f.path)))


class Compare():
        """
        Look for duplicate .msg in master_folder, comparing it to new (search_folder),
        with functionality to move duplicates to output_folder
        (uses sql database for each folder)
        (duplicates keyed on message ID)
        """
        def __init__(self,master_folder,search_folder,output_folder=None):
            self.master_folder=master_folder
            self.search_folder=search_folder
            self.output_folder=output_folder
            self.setup()
            
        def setup(self):
        	    self.master=db(self.master_folder)
        	    log.debug('load local')
        	    self.local=db(self.search_folder)
        	    
        def rescan_all(self):
        	    print('master rescan')
        	    self.master.rescan()
        	    self.master.message_scan()
        	    print('local rescan')
        	    self.local.rescan()
        	    self.local.message_scan()
        	    print('scans complete')
             
        def search_local_dups(self):
            """check what .msg files in local folder already exist in master
               return a generator of dups """
            #print(search_folder)
            blanks=0
            orphans=0
            dups=0
            for f in self.local.files:
                _id=f.document_id
                if _id:
                    q=self.master.lookup_doc_id(_id) #returns a list
                    if q:
                        #message in search folder FOUND in  master specs
                        dups+=1
                        try:
                            print(f'Duplicate message id found in local filepath: {f.path} match in master: {q} ')
                        except Exception as e:
                            print(e)
                        yield f
                    else:
                        orphans+=1 #the local file not found in master
                else:
                    blanks+=1
            print(f'Ignore {blanks} messages with no message id in local folder')
            print(f'Orphans found in local folder  {orphans}and dups: {dups}')
                        
        def inspect_local(self):
            """ print meta for duplicates in local folder"""
            self.local._inspect()
    
        def purge_local(self):
            """purge all the duplicates within the local folder"""
            self.local.purge(self.output_folder)
            self.local.rescan()
        
        def purge_dups_with_master(self):
            """move all the local files that already exist in master"""
            print(f'removing dups to {self.output_folder}')
            self.local.remove_files(self.search_local_dups(),self.output_folder)
            self.local.rescan()
        

        
def message_id(path):
    """try two methods to extract message_ID"""
    try:
        msg = extract_msg.Message(path)
        _id=msg.header.get('Message-Id')
    except Exception as e:
        log.error(f'ERROR {e} with parsing path {path}')
        _id=message_id_v2(path)
    return _id

#        msg_obj = MsOxMessage(path)
#    #            #json_string = msg_obj.get_message_as_json()
#        msg_dict = msg_obj.get_properties()
#    ##            print(msg_dict.keys())
#    ###            msg_dict.pop('Body')
##        for _i in msg_dict.keys():
##            print()
##            print('KEY: '+_i)
##            print(msg_dict.get(_i))
##    #            
#    #            c_id=msg_dict.get('ConversationIndex')
#        _id=msg_dict.get('InternetMessageId')
 
 
def relpath(path,rootpath):
    #deals with a relpath even if longpath for windows
    if os.name=='nt' and path.startswith("\\\\?\\") and not rootpath.startswith("\\\\?\\"):
        return os.path.relpath(path,"\\\\?\\"+rootpath)
    else:
        return os.path.relpath(path,rootpath)
        
        
def messages(search_folder):
    for path,subdir,files in os.walk(search_folder):
        #for each filename - check if already in the master specs
        for f in files:
            filepath=os.path.join(path,f)
            xt = os.path.splitext(f)[1]
            if xt=='.msg':
                yield filepath
        
def search_dups(specs,search_folder=TESTPATH2):
    #look through a folder
    for path,subdir,files in os.walk(search_folder):
        #for each filename - check if already in the master specs
        for filepath in messages(search_folder):
                _id=message_id(filepath)
                if not _id:
                    log.debug(f'Filepath: {filepath} returned no  message id')
                    continue
                else:
                    q=specs.lookup_doc_id(_id) #returns a list
                    if q:
                        #message in search folder is a dup of item in master specs
                        log.debug(f'Filepath: {filepath}with message id {_id} matches dup(s) in master {q}')
                        yield filepath

def search_orphans(specs,search_folder=TESTPATH2):
    #look through a folder
    #print(search_folder)
    for path,subdir,files in os.walk(search_folder):
        #for each filename - check if already in the master specs
        for filepath in messages(search_folder):
                _id=message_id(filepath)
                #print(_id)
                q=specs.lookup_doc_id(_id) #returns a list
                if not q:
                    #message in search folder NOT FOUND in  master specs
                    log.debug(f'Filepath: {filepath} no match in master ')
                    yield filepath

def make_folder(newfolder):
    if not os.path.isdir(newfolder):
        log.debug(f'Making new folder {newfolder}')
        pp=Path(newfolder)
        pp.mkdir(parents=True) 


def copy_orphans(specs,search_folder=TESTPATH2,target_folder=None):
    for f in search_orphans(specs,search_folder=search_folder):
        if target_folder:
            folder,filename=os.path.split(f)
            #log.debug(f'{folder},{search_folder}')
            relfolder=relpath(folder,search_folder)
            newfolder=os.path.join(target_folder,relfolder)
            make_folder(newfolder)
            #print(f'new folder:{newfolder}')
            shutil.copy2(f,os.path.join(newfolder,filename))
            #os.rename(f,dst_dir_fd=newfolder)
        else:
            log.info('No destination specified')

def copy_dups(specs,search_folder=TESTPATH2,target_folder=None):
    for f in search_dups(specs=specs,search_folder=search_folder):
        if target_folder:
            folder,filename=os.path.split(f)
            relfolder=relpath(folder,search_folder)
            newfolder=os.path.join(target_folder,relfolder)
            make_folder(newfolder)
            #print(f'new folder:{newfolder}')
            shutil.copy2(f,os.path.join(newfolder,filename))
            #os.rename(f,dst_dir_fd=newfolder)
        else:
            log.info('No destination specified')

def move_dups(specs,search_folder=TESTPATH2,target_folder=None):
    for f in search_dups(specs=specs,search_folder=search_folder):
        if target_folder:
            folder,filename=os.path.split(f)
            relfolder=relpath(folder,search_folder)
            newfolder=os.path.join(target_folder,relfolder)
            make_folder(newfolder)
            os.rename(f,os.path.join(newfolder,filename))
        else:
            log.info('No destination specified')


def message_id_v2(f):
    try:
        assert olefile.isOleFile(f)
        ole = olefile.OleFileIO(f)
        sub=    ole.openstream("__substg1.0_1035001F")
        data = sub.read()
    except Exception as e:
    	    print(e)
    	    return None
    return windowsUnicode(data)


def windowsUnicode(string):
    if string is None:
        return None
    if sys.version_info[0] >= 3:  # Python 3
        return str(string, 'utf_16_le')
    else:  # Python 2
        return unicode(string, 'utf_16_le')


#specs=db()
#specs.rescan()
#specs.message_scan()








    
    
 
            # SenderEntryId
# access file directory
#AdDKKAaX9q9luDyvTUuYi703s24kTw==
#OriginalAuthorEntryId
#ReceivedRepresentingEntryId
#SentRepresentingEntryId
#ReceivedByEntryId
##attachments', 'recipients', 'MessageClass', 'Subject', 'SentRepresentingSearchKey', 'ReceivedByEntryId', 'ReceivedByName', 'SentRepresentingEntryId', 'SentRepresentingName', 'ReceivedRepresentingEntryId', 'ReceivedRepresentingName', 'ReceivedBySearchKey', 'ReceivedRepresentingSearchKey', 'SentRepresentingAddressType', 'SentRepresentingEmailAddress', 'ConversationTopic', 'ConversationIndex', 'ReceivedByAddressType', 'ReceivedByEmailAddress', 'ReceivedRepresentingAddressType', 'ReceivedRepresentingEmailAddress', 'TransportMessageHeaders', 'TnefCorrelationKey', 'SenderEntryId', 'SenderName', 'SenderSearchKey', 'SenderAddressType', 'SenderEmailAddress', 'DisplayCc', 'DisplayTo', 'NormalizedSubject', 'Body', 'RtfCompressed', 'InternetMessageId', 'SearchKey', 'PolicyTag', 'StartDateEtc', 'LastModifierName', 'LastModifierEntryId', 'SenderSmtpAddress', 'SentRepresentingSmtpAddress', 'ChangeKey', 'PredecessorChangeList', 'AddressBookManagerDistinguishedName', 'AddressBookOwner', 'AddressBookReports', 'AddressBookProxyAddresses'])

# for each .msg filetype , extract the message ID and thread ID.




