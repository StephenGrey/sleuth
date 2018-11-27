
from threading import Thread, current_thread, Event
try:
    from queue import Full,Empty #pip3 install queuelib
    from queue import Queue as Q
except ImportError:
    from Queue import Full,Empty #pip install queuelib
    from Queue import Queue as Q

from threading import Thread, current_thread, Event
import os,time,logging,random, shutil,redis
from SearchBox.watcher import watch_dispatch

#r=redis.Redis()

class PostFailure(Exception):
    pass

class Terminate(Exception):
    pass

class StoppableThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.killswitch=Event()
        self.process_q=Q(maxsize=0) #no maxsize
        self.setDaemon(True)
        self.pid=os.getpid()
        print(f'Thread launched with process ID: \"{self.pid}\"')


    def stop(self):
        self.killswitch.set()
        print(f'stopping process ID: \"{self.pid}\"')
        
    def stopped(self):
        return self.killswitch.is_set()

    def stopper(self):
        while True:
            try:
                self.process_q.task_done()
            except ValueError:
                break

class TestWatch(StoppableThread):
    
    def run(self):
        print('running something')
        while True:
            time.sleep(10)
            print ('keeping going')
            

class Watcher(StoppableThread):
    def __init__(self):
        super(Watcher,self).__init__()
        
    def run(self):
        t=Tasker("tasker_thread_")
        t.setDaemon(True)
        t.start()
        t.run()
                        
def main():
    w=Tasker('tasker')
    w.start()
    counter=0
    try:
        while True:
            #feed some test tasks
            counter+=1
            task_id=f'task_id:{counter}'
            print(f'Sending task#{task_id} Action: \'extract\'')
            r.hmset(task_id,{'action':'extract'})
            r.lpush('tasks-queue',counter)
            time.sleep(7)
    except KeyboardInterrupt:
        print('\nKeyboard interrupt')
    finally:
        w.stop()
        r.lpush('tasks-queue',None)    
        

class Tasker(StoppableThread):
#    """Threaded OCR processor"""
#    #----------------------------------------------------------------------
    def __init__(self,name):
    	
    	 #process_q,upload_q,results_q,name
        super(Tasker,self).__init__()

        self.setName(name)
        self.name=self.getName()
#
    def run(self):
        print('Launching {}'.format(self.name))
        try:
            while (not self.killswitch.is_set()):
                try:
                    key,task_id=r.brpop('tasks-queue')
                except Empty:
                    continue                
                if task_id==b'None':
                    break
                elif task_id:
                    task_key=f'task_id:{int(task_id)}'
                    action=r.hget(task_key,'action')
                    print(f'Processing task {task_id}; action: {action}')
                    
        except Terminate:
            pass            
        finally:
            print('{}: terminating'.format(self.name))

class DocProcessor(StoppableThread):
#    """Threaded OCR processor"""
#    #----------------------------------------------------------------------
    def __init__(self,name):
    	
    	 #process_q,upload_q,results_q,name
        super(DocProcessor,self).__init__()
        self.setName(name)
        self.name=self.getName()
#
    def run(self):
        print('Launching {}'.format(self.name))
        try:
            while (not self.killswitch.is_set()):
                #print('doing a background task then wait')
                time.sleep(1)
                watch_dispatch.task_check()   
        except Terminate:
            pass            
        finally:
            print('{}: terminating'.format(self.name))
    
def set_watcher():
    t=DocProcessor('docprocess1')
    t.start()
    return t



    
