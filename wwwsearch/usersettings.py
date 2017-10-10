# -*- coding: UTF-8 -*-

#MAKE A DICTIONARY OF USER OPTIONS TAKEN FROM INI FILE DEFINED BY CONFIGPATH
#BACKUP FILE TAKES DEFAULT OPTIONS FROM USERSETTINGS.CONFIG.EXAMPLE 
import logging,os
log = logging.getLogger('ownsearch')
from ConfigParser import SafeConfigParser
parser=SafeConfigParser()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
configpath=BASE_DIR+'/wwwsearch/usersettings.config'
defaultpath=BASE_DIR+'/wwwsearch/usersettings.config.example'
solrdefaults=BASE_DIR+'/wwwsearch/solrdefaults.config'


#log.info(configpath)

def settingsMap(section):
    dict1 = {}
    options = parser.options(section)
    for option in options:
        try:
            dict1[option] = parser.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

#GET DEFAULT CONFIGS
defaultconfig={}
try:
    parser.read(solrdefaults)
except:
    log.error ('Error on reading default configuration')    

if parser.sections()==[]:
    log.info('Failed to load default usersettings.config ')

for section in parser.sections():
    defaultconfig[section]=settingsMap(section)

#GET USER CONFIGS (which will override default)
userconfig={}
try:
    parser.read(configpath)
except:
    log.error ('Error on reading user configuration')

#debugging
#log.info(parser.read(configpath))
#log.info ('Parser sections:')
#log.info (parser.sections())

if parser.sections()==[]:
    log.info('Failed to load usersettings.config so trying default configs')
    try:
        parser.read(defaultpath)
    except:
        print ('Error on reading default=example configuration')

for section in parser.sections():
    userconfig[section]=settingsMap(section)

for section in defaultconfig:
    if section not in userconfig:
        userconfig[section]=defaultconfig[section]
#print ('userconfig',userconfig)






"""

Configuration files containing Unicode data should be opened using the codecs module to set the proper encoding value.

Changing the password value of the original input to contain Unicode characters and saving the results in UTF-8 encoding gives:

[bug_tracker]
url = http://localhost:8080/bugs/
username = dhellmann
password = ßéç®é

from ConfigParser import SafeConfigParser
import codecs

parser = SafeConfigParser()

# Open the file with the correct encoding
with codecs.open('unicode.ini', 'r', encoding='utf-8') as f:
    parser.readfp(f)

password = parser.get('bug_tracker', 'password')

print 'Password:', password.encode('utf-8')
print 'Type    :', type(password)
print 'repr()  :', repr(password)


"""
