import os,time,logging,random, shutil,redis
from watcher import watch_dispatch,watch_filesystem
THREADS=[]
TASKS_UNDERWAY=set()
MODIFY_DELAY=120
from threading import Thread, current_thread, Event,get_ident
try:
    from queue import Full,Empty #pip3 install queuelib
    from queue import Queue as Q
except ImportError:
    from Queue import Full,Empty #pip install queuelib
    from Queue import Queue as Q

try:
    from configs import config
    DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore
except:
    DOCSTORE=''
HEARTBEAT=watch_dispatch.HeartBeat()

log = logging.getLogger('ownsearch.tasks')
#r=redis.Redis()

class PostFailure(Exception):
    pass

class Terminate(Exception):
    pass

class PoisonPill(Exception):
    pass

class StoppableThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.killswitch=Event()
        self.process_q=Q(maxsize=0) #no maxsize
        self.setDaemon(True)
        self.pid=f"{os.getpid()} - {random.randint(1,4096)}"
        THREADS.append(self.pid)
        print(f'Thread launched with process ID: \"{self.pid}\""')
        log.info(f'Thread launched with process ID: \"{self.pid}')


    def stop(self):
        self.killswitch.set()
        print(f'stopping watcher process ID: \"{self.pid}\"')
        
    def stopped(self):
        return self.killswitch.is_set()

    def stopper(self):
        while True:
            try:
                self.process_q.task_done()
            except ValueError:
                break

class SleuthBee(StoppableThread):
    "worker thread"
    def __init__(self,name,q,task):
        super(SleuthBee,self).__init__()
        self.setName(name)
        self.name=self.getName()
        self.task=task
        self.q=q
        print(f'Task worker created, name: {self.name} task: {task}')
        
    def run(self):
        try:
            log.debug(f'Starting task {self.task}')
            result=watch_dispatch.task_dispatch(self.task)
            log.debug(f'Task over: terminating {self.name}')
        except Exception as e:
            log.debug(f'Exception {e}')
            pass
        finally:
            try:
                TASKS_UNDERWAY.remove(self.task)
            except:
                pass
            try:
                self.q.task_done()
            except ValueError:
                pass
            except AttributeError:
                pass
            self.stop


class TaskQueue(StoppableThread):
    """wait for tasks then allocate"""
    def __init__(self,name):
        super(TaskQueue,self).__init__()
        self.setName(name)
        self.name=self.getName()
        self.workers=[]

    def run(self):
        log.debug('Launching {}'.format(self.name))
        try:
            while (not self.killswitch.is_set()):
                try:
                    self.task=self.process_q.get(timeout=2) #wait for new task
                    log.debug('TaskQ received a new task')
                    if self.task=='poison_pill':
                        raise PoisonPill
                except Empty:
                    continue                
                try:
                    log.debug(f'Do task {self.task}')
                    worker=SleuthBee(f'TaskWorker.{self.task}',self.process_q,self.task)
                    worker.start()
                    #print(f'pretending to do task')
                    #self.killswitch.wait(60)   # seconds.
                except Exception as e:
                    log.info(f'Exception {e} launching task {self.task}')
        except KeyboardInterrupt:
            self.stop()
            self.stopper()
        except PoisonPill:
            pass
        except Terminate:
            pass            
        finally:
            log.debug('{}: terminating'.format(self.name))
            for t in self.workers:
                try:
                    t.stop()
                except:
                    pass

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
    def __init__(self,name,watch_files=False,watch_folder=DOCSTORE,modify_delay=MODIFY_DELAY):
        log.debug(f'Docprocessor launched in {get_ident()}')
    	 #process_q,upload_q,results_q,name
        super(DocProcessor,self).__init__()
        self.setName(name)
        self.name=self.getName()
        self.watch_files=watch_files
        self.watch_folder=watch_folder
        self.modify_delay=modify_delay
#
    def run(self):
        log.debug('Launching process name \'{}\''.format(self.name))
        
        self.taskq=start_taskqueue()
        
        if self.watch_files:
            if os.path.exists(self.watch_folder):
                log.info(f'Launching Watchdog on filesystem: {self.watch_folder}')
                self.observer=watch_filesystem.launch(self.watch_folder)
            else:
                log.info(f'Watch folder \'{self.watch_folder}\' does not exist: cannot launch Watchdog')
        
        try:
            while (not self.killswitch.is_set()):
                #print('doing a background task then wait')
                time.sleep(1)

                #check for new un-assigned task 
                put_tasks(self.taskq)
                watch_dispatch.modify_check(self.modify_delay)
                
                if self.taskq.is_alive():
                    #log.debug('Heartbeat')
                    HEARTBEAT.tick()   #heartbeat signal
                else:
                    self.taskq=start_taskqueue()
        except PoisonPill:
            log.info('Poison pill received')
        except Terminate:
            pass            
        finally:
            print('{}: terminating'.format(self.name))
            
            if self.taskq:
                self.taskq.stop()
                self.taskq.stopper()
            
            if self.watch_files:
                self.observer.stop()
                self.observer.join()
    
def set_watcher():
    t=DocProcessor('docprocess1',watch_files=True)
    t.start()
    return t

def start_taskqueue():
    tq=TaskQueue('main_tasks')
    tq.setDaemon(True)
    tq.start()
    return tq

def put_tasks(tq):
    for task in watch_dispatch.r.smembers('SEARCHBOX_JOBS'):
        if task not in TASKS_UNDERWAY:
            TASKS_UNDERWAY.add(task)
            log.debug(f'New task from redis jobs -- {task} -- added to processing set')
            tq.process_q.put(task)
            if task=="poison_pill":
                TASKS_UNDERWAY.remove(task)
                watch_dispatch.r.srem('SEARCHBOX_JOBS',"poison_pill")
                raise PoisonPill

def test_taskq():
    tq=start_taskqueue()
    try:
        while True:
            if not tq.is_alive():
                raise Exception
            put_tasks(tq)
            time.sleep(1)
    except:
        pass
    finally:
        log.debug(f'Stopping {tq}')
        tq.stop()
        tq.stopper()
    
    
    
    
