import os
from django.conf import settings

TASKS=[]
from watcher import tasks


def run():
#    autoload(["receivers"])
    if os.environ.get('RUN_MAIN') != 'true':
        if not tasks.THREADS: #prevent the background processes being set twice
            print('Initialising Search Box background processes.. ')
            print(f'Main thread has id: {os.getpid()}')
            t=tasks.set_watcher()
            TASKS.append(t)
       
    else:
        print(f'Other thread running has id: {os.getpid()}')
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