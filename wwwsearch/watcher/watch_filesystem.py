# -*- coding: utf-8 -*-
import sys, logging, redis,time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from . import watch_dispatch
from django.conf import settings
logging.config.dictConfig(settings.LOGGING)
log = logging.getLogger('ownsearch.watch_filesystem')

# handles sync event actions, only modified 
class MySyncHandler(FileSystemEventHandler):
	
    def on_any_event(self,event):
        #log.debug(event.event_type)
        #log.debug(f'{event.__dict__} at {time.time()}')
        
        if event.event_type=='created':
            DISPATCHER.process('created',event._src_path,None)

        elif event.event_type=='moved':
            DISPATCHER.process('moved',event._src_path,event._dest_path)
            
        elif event.event_type=='deleted':
            DISPATCHER.process('delete',event._src_path,None)
            
        elif event.event_type=='modified':        
            DISPATCHER.process('modified',event._src_path,None)
        



def launch(path):
    observer = Observer()
    observer.schedule(MySyncHandler(), path, recursive=True)
    observer.start()
    global DISPATCHER
    DISPATCHER=watch_dispatch.Index_Dispatch()
    return observer

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
#    event_handler = LoggingEventHandler()
    observer=launch(path)
    
    
    try:
        while True:
            time.sleep(1)
            watch_dispatch.modify_check(5)
            watch_dispatch.task_check()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


