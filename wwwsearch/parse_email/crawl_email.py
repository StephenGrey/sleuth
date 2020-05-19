# -*- coding: utf-8 -*-
import os,logging,shutil
from msg_parser import MsOxMessage
from documents.file_utils import SqlFileIndex
from pathlib import Path
log = logging.getLogger('ownsearch.emailcrawler')

_relpath='msg'
_relpath2='msg2'
DOCBASE=os.path.abspath(os.path.join(os.path.dirname(__file__),'../tests/testdocs'))
TESTPATH=os.path.join(DOCBASE,_relpath)
TESTPATH2=os.path.join(DOCBASE,_relpath2)


def db(path=TESTPATH):
    return MessageIndex(path,label='messages')

class MessageIndex(SqlFileIndex):
    """sql database of a file directory containing .msg files"""

    def message_scan(self):
        """add missing message_id to database"""
        for f in self.files:
            print(f'Message name: {f.name}')
            print(f'Message ID: {f.document_id}')
            if not f.document_id:
                xt = os.path.splitext(f.name)[1]
                if xt=='.msg':
                    f.document_id=message_id(f.path)
        self.save()            
    def message_dups(self):
        return self.dup_doc_id()
    
    def list_message_dups(self):
        dups=[]
        
         
        for d in self.message_dups().all():
            if d[0]=='':
                continue
            yield d,self.lookup_doc_id(d.document_id)
#            dups.append(self.lookup_doc_id(dup.document_id))
#        return dups

    def _inspect(self):
        for d,files in self.list_message_dups():
            print(d)
            for f in files:
                print(f.contents_hash)
                print(f.last_modified)
                print(f.length)
                
                
                
    def purge(self,target):
        for d,files in self.list_message_dups():
            remove_files=files[1:]
            for f in remove_files:
                if target:
                    folder,filename=os.path.split(f.path)
                    relfolder=os.path.relpath(folder,self.folder_path)
                    newfolder=os.path.join(target,relfolder)
                    make_folder(newfolder)
                    os.rename(f.path,os.path.join(newfolder,filename))
                else:
                    log.info('No destination specified')
            
        
def message_id(path):
    try:
        msg_obj = MsOxMessage(path)
    #            #json_string = msg_obj.get_message_as_json()
        msg_dict = msg_obj.get_properties()
    ##            print(msg_dict.keys())
    ###            msg_dict.pop('Body')
#        for _i in msg_dict.keys():
#            print()
#            print('KEY: '+_i)
#            print(msg_dict.get(_i))
#    #            
    #            c_id=msg_dict.get('ConversationIndex')
        _id=msg_dict.get('InternetMessageId')
        
        print(_id)
    except Exception as e:
        log.error(e)
        _id=None
    return _id
    
        
        
def search_dups(specs,search_folder=TESTPATH2):
    #look through a folder
    print(search_folder)
    for path,subdir,files in os.walk(search_folder):
        #for each filename - check if already in the master specs
        for f in files:
            filepath=os.path.join(path,f)
            xt = os.path.splitext(f)[1]
            if xt=='.msg':
                _id=message_id(filepath)
                #print(_id)
                q=specs.lookup_doc_id(_id) #returns a list
                
                if q:
                    #message in search folder is a dup of item in master specs
                    log.debug(f'Filepath: {filepath} matches dup(s) in master {q}')
                    yield filepath
                else:
                    #item in search folde is an orphan - i.e. not in master specs
                    pass
                    

def make_folder(newfolder):
    if not os.path.isdir(newfolder):
        log.debug(f'Making new folder {newfolder}')
        pp=Path(newfolder)
        pp.mkdir(parents=True) 




def copy_dups(specs,search_folder=TESTPATH2,target_folder=None):
    for f in search_dups(specs=specs,search_folder=search_folder):
        if target_folder:
            folder,filename=os.path.split(f)
            relfolder=os.path.relpath(folder,DOCBASE)
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
            relfolder=os.path.relpath(folder,DOCBASE)
            newfolder=os.path.join(target_folder,relfolder)
            make_folder(newfolder)
            os.rename(f,os.path.join(newfolder,filename))
        else:
            log.info('No destination specified')

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




