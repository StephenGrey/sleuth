import os, threading
from django.conf import settings

TASKS=[]
from watcher import tasks

def run():
#    autoload(["receivers"])
    if os.environ.get('RUN_MAIN') != 'true':
        if not tasks.THREADS: #prevent the background processes being set twice
            print('Initialising Search Box background processes in startup.py.. ')
            tid=threading.get_ident()
            print(f'Main thread has id: {os.getpid()} and thread:{tid}')
            t=tasks.set_watcher()
            TASKS.append(t)
       
    else:
        tid=threading.get_ident()
        print(f'Secondary thread launching, other thread running has id: {os.getpid()} thread:{tid}')
  # myVar exists.

#from django.utils.importlib import import_module
#from django.utils.module_loading import module_has_submodule


#def autoload(submodules):
#    for app in settings.INSTALLED_APPS:
#        mod = import_module(app)
#        for submodule in submodules:
#            try:
#                import_module("{}.{}".format(app, submodule))
#            except:
#                if module_has_submodule(mod, submodule):
#                    raise