##import email, os
from msg_parser import MsOxMessage
from documents.file_utils import normalise
from parse_email.crawl_email import message_id
from parse_email.crawl_email import message_id_v2

###from email.parser import BytesParser, BytesHeaderParser,Parser
###from email.policy import default
##
import extract_msg
import olefile,sys
import os
import chardet

#f="R:\\DATA BACKUP\\Outlook CLEAN\\Messages_new\\Afghan_M\\2 Yorks\\Jake Little  Re_ BOOK ON OP HERRICK 7 [a42a2100].msg"
search_folder="R:\\DATA BACKUP\\Outlook CLEAN\\Messages_new"

#f="R:\\DATA BACKUP\\Outlook CLEAN\\Messages_new\\2009_sent\\Sent 2009 and 2010\\Stephen Grey - FOIA US SG.doc [24152000].msg"
#f="R:\DATA BACKUP\Outlook CLEAN\Messages_new\Reuters2017\Inbox\Williams, Michael J.  Enterprise Thursday_ our first meeting_ Soliciting tips an[44342200].msg"
#"R:\DATA BACKUP\Outlook CLEAN\orphans\Zen2010_2012\Top of Outlook data file\Contacts\Stephen Grey - Tayab Ali [84182a00].msg"
f="R:\DATA BACKUP\Outlook CLEAN\Messages_new\Reuters2018\Inbox\London Technology Unconference - London Technology Unconference – Clear your diary! [24002000].msg"


#print (os.path.exists(normalise(f)))
##
##assert olefile.isOleFile(f)
#ole = olefile.OleFileIO(f)
##with open(f, 'rb') as msg:
##    m=BytesParser(policy=default).parse(msg)
##    print(m)
    

def windowsUnicode(string):
    if string is None:
        return None
    if sys.version_info[0] >= 3:  # Python 3
        return str(string, 'utf_16_le')
    else:  # Python 2
        return unicode(string, 'utf_16_le')


#with open(messagefile, 'rb') as fp:
#     headers = BytesParser(policy=default).parse(fp)

def foldercheck(folder):
    for folder,subdir,files in os.walk(search_folder):
        total=0
        fails=0
        for file in files:
            total+=1
            f=os.path.join(folder,file)
            f=normalise(f)
            print (f'File: {f} exists: {os.path.exists(normalise(f))}')
            try:
                #method 1
                assert olefile.isOleFile(f)
                ole = olefile.OleFileIO(f)
                #print(ole.listdir())
                try:
                    sub=    ole.openstream("__substg1.0_1035001F")
                    data = sub.read()
                    _id_ole=windowsUnicode(data)
                except Exception as e:
                    _id_ole=None
                    #print(f'No OLE id for {f}')

                #method 2
                try:
                    alt_id=message_id(f)
                except Exception as e:
                    print(e)
                    alt_id=None

                #method 3
                try:
                    msg = extract_msg.Message(f)
                    _id3=msg.header.get('Message-Id')
                except Exception as e:
                    print(e)
                    _id3=None
                    
                if not alt_id or not _id_ole or not _id3:
                    if alt_id or _id_ole or _id3:
                        print(f'FAIL : OLE ide {_id_ole} alt_id: {alt_id} id3: {_id3} for path {f} ')
                    fails+=1
            except Exception as e:
                print(f' Exception {e} for filepath {f}')
        print(f'COUNT: {total}   FAILS: {fails}')


def sample_check(folder,sample=100):
    count=0
    for path,sub,files in os.walk(folder):
        for f in files:
            count+=1
            if count>sample:
               break
            else:
                filepath=os.path.join(path,f)
                filecheck(filepath)


def filecheck(f):
    print('method 1')
    print (os.path.exists(normalise(f)))
    try:
        msg = extract_msg.Message(f)
        #print(msg.header)
        _id=msg.header.get('Message-Id')
        if not _id:
            print(msg.header)
            print(msg.body)
        else:
            print(_id)
            print(msg.header.get('Thread-Index'))
 
    except NotImplementedError as e:
        print(e)
    except Exception as e:
        print(e)
    
    #msg.header.__dict__
    #msg.header.get('To')
    #Thread-Index
    
    print('method 2')
    try:
        msg_obj = MsOxMessage(normalise(f))
        msg_dict = msg_obj.get_properties()
        #fields=msg_dict.keys()
        
##        for field in ['Subject', 'SentRepresentingName', 'SentRepresentingEmailAddress',
##                      'ConversationTopic', 'SenderName', 'SenderSearchKey',
##                      'SenderAddressType', 'SenderEmailAddress','recipients', 'DisplayTo', 'NormalizedSubject', 'InternetMessageId']:
##            field_text=msg_dict.get(field)
##            print(f'{field} : {field_text}')

        x=msg_dict.get('InternetMessageId')
        print(x)
        print(chardet.detect(x))

        x=x.decode('iso-8859-1')
        print(x)

    except Exception as e:
            print(e)

    print('method 3')
    _id=message_id_v2(f)  
##    assert olefile.isOleFile(f)
##    ole = olefile.OleFileIO(f)
##    sub=    ole.openstream("__substg1.0_1035001F")
##    data = sub.read()
##    print(data)
##    print(windowsUnicode(data))
##
    print(_id)
##    streams=ole.listdir()
##    for sa in streams:
##        try:
##            s=sa[1]
##            print(s)
##            #p = ole.getproperties(s)
##            #print(p)
##            sub=    ole.openstream(s) #("__substg1.0_1035001F")
##            data = sub.read()
##            #print(data)
##            try:
##                _id=windowsUnicode(data)
##            except Exception as e:
##                print(e)
##                _id=None
##                id= str(data)
##            print(_id)
##        except Exception as e:
##            pass
##            #print(e)

sample_check("R:\DATA BACKUP\Outlook CLEAN\copyblanks")


#meta = ole.get_metadata()
#meta.dump()
# 247470.78644.qm@web25506.mail.ukl.yahoo.com>


#print(meta.__dict__)


#msg = extract_msg.Message(f)
#print(msg.header)


##for key in msg.__dict__.keys():
##    print()
##    print(key)
##    print(msg.__dict__.get(key))
##
##    

