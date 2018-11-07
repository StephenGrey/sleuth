import sys, logging, redis,time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from SearchBox.watcher import watch_dispatch2 as watch_dispatch

# handles sync event actions, only modified 
class MySyncHandler(FileSystemEventHandler):
	
    def on_any_event(self,event):
        print(event)
        print(f'{event.__dict__} at {time.time()}')
        
        if event.event_type=='created':
            watch_dispatch.Index_Dispatch('created',event._src_path,None)

        elif event.event_type=='moved':
            watch_dispatch.Index_Dispatch('moved',event._src_path,event._dest_path)
            
        elif event.event_type=='deleted':
            watch_dispatch.Index_Dispatch('delete',event._src_path,None)
            
        elif event.event_type=='modified':        
            watch_dispatch.Index_Dispatch('modified',event._src_path,None)
        

        
        
        
#    def on_created(self,event):
#        print(event)
#        print(f'Created: {event.__dict__}')
#        watch_dispatch.Index_Dispatch('created',event._src_path,None)
#
#    def on_moved(self,event):
#        print(event)
#        print(f'Moved: {event.__dict__}')        
#        watch_dispatch.Index_Dispatch('moved',event._src_path,event._dest_path)
#        
#    def on_deleted(self,event):
#        print(f'Delete event: {event.__dict__}')
#        watch_dispatch.Index_Dispatch('delete',event._src_path,None)
#        
#    def on_modified(self, event):        
#        print (event)
#        print(f'Modified event: {event.__dict__}')
#        watch_dispatch.Index_Dispatch('modified',event._src_path,None)
#        
#

def modify_check(timeout):
    #print(f'Modification queues: {watch_dispatch.MODIFIED_FILES}, TIMES: {watch_dispatch.MODIFIED_TIMES}')
    modified_done=[]
    for _filepath in watch_dispatch.MODIFIED_TIMES:
        _now=time.time()
        _modtime=watch_dispatch.MODIFIED_TIMES[_filepath]
        if _now-_modtime>timeout:
            if watch_dispatch.update_filepath(_filepath):
                modified_done.append(_filepath)
            else:
                modified_done.append(_filepath)
    for _filepath in modified_done:
        watch_dispatch.MODIFIED_TIMES.pop(_filepath)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
#    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(MySyncHandler(), path, recursive=True)
    
    observer.start()
    try:
        while True:
            time.sleep(1)
            modify_check(5)
            
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


