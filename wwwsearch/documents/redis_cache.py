# -*- coding: utf-8 -*-
#in windows  = downloaded redis https://github.com/MicrosoftArchive/redis/releases
#launch service with C:\Program Files\Redis  - execute redis-server.exe

import redis,logging
log = logging.getLogger('ownsearch.docs.redis')
try:
    #from usersettings import userconfig as config
    from configs import config
    HOST=config['Redis']['host']
    PORT=int(config['Redis']['port'])
    DB=int(config['Redis']['db'])
     #get base path of the docstore
except Exception as e:
    #make usable outside the project
    log.info('Default redis settings loaded')
    HOST='localhost'
    PORT=6379
    DB=0

    
redis_connection=redis.Redis(host=HOST,port=PORT,db=DB, charset="utf-8", decode_responses=True)

def delete_job(job):
    return redis_connection.delete(job)
    

