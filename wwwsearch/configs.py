# -*- coding: utf-8 -*-
#MAKE A DICTIONARY OF USER OPTIONS TAKEN FROM INI FILE DEFINED BY CONFIGPATH
#BACKUP FILE TAKES DEFAULT OPTIONS FROM USERSETTINGS.CONFIG.EXAMPLE 
import logging,os
log = logging.getLogger('servertest.configs')

try:
    from configparser import SafeConfigParser
except:
    from ConfigParser import SafeConfigParser


CWD = os.path.dirname(os.path.abspath(__file__))
CONFIGPATH=CWD+'/usersettings.config'
DEFAULTPATH=CWD+'/usersettings.config.example'
SOLRDEFAULTS=CWD+'/solrdefaults.config'


class Config():
    def __init__(self,path=CONFIGPATH):
        self.this_parser=SafeConfigParser()
        self.path=path
        self.read()
        self.data={}
        self.get_values()
        
    def update(self,section,option,newvalue,update_file=True):
        section_value=self.data.get(section)
        if not section_value:
            self.this_parser.add_section(section)
            section_value={}
        section_value.update({option:newvalue})
        self.data.update({section:section_value})
        self.this_parser.set(section,option,newvalue)
        if update_file:
            self.dump()

    def read(self):
        try:
            self.this_parser.read(self.path)
        except:
            print('Error on reading user configuration')
            
    def get_values(self):
        if self.this_parser.sections()==[]:
            print(f'Failed to load {self.path}')
        else:
            for section in self.this_parser.sections():
                self.data[section]=self.settingsMap(section)
                
    def dump(self):
        # Writing our configuration file to 'example.cfg'
        with open(self.path, 'w') as configfile:
            self.this_parser.write(configfile)


    def settingsMap(self,section):
        dict1 = {}
        options = self.this_parser.options(section)
        for option in options:
            try:
                dict1[option] = self.this_parser.get(section, option)
                if dict1[option] == -1:
                    DebugPrint("skip: %s" % option)
            except:
                print("exception on %s!" % option)
                dict1[option] = None
        return dict1
#
#GET USER CONFIGS (which will override default)
userconfig=Config()


try:
    defaultconfig=Config(path=DEFAULTPATH) #the example configs - 
    solrconfig=Config(path=SOLRDEFAULTS) #the basic solr configuration
    
    changes=False
    for section in defaultconfig.data:
        if section not in userconfig.data:
            changes=True
            for option in defaultconfig.this_parser.options(section):
                option_value=defaultconfig.this_parser.get(section, option)
                userconfig.update(section,option,option_value,update_file=False)
                
    for section in solrconfig.data:
        if section not in userconfig.data:
            changes=True
            for option in solrconfig.this_parser.options(section):
                option_value=solrconfig.this_parser.get(section, option)
                userconfig.update(section,option,option_value,update_file=False)
    
    if changes:
        userconfig.dump()  #update userconfig file
        log.info('User configs updated from defaults')

except Exception as e:
    log.warning(e)
    
config=userconfig.data

