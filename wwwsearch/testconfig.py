# -*- coding: utf-8 -*-

from usersettings import userconfig
from configs import config
newconfig=config.data

for section in userconfig:
    newsection=newconfig.pop(section,None)

    if newsection:
        for option in userconfig[section]:
            newval=newsection.pop(option,None)
            if newval:
                assert newval==userconfig[section].get(option)
                print('.')
            else:
                print(f'Missing option {option} in section {section}')
    else:
        print(f'Missing section: {section}')
        
        