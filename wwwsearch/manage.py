# -*- coding: utf-8 -*-
import os
import sys
#
#print(f'Current directory: {os.getcwd()}')
#abspath=os.path.abspath(__file__)
#dname=os.path.dirname(abspath)
#os.chdir(dname) #this switches current directory to file's directory
#print(f'Current directory: {os.getcwd()}')

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    print (sys.argv)
    try:
        if sys.argv[1]=="runserver":
            
            import myproject.startup as startup
            startup.run()
            TASKS=startup.TASKS
        else:
            TASKS=[]
    except: 
        TASKS=[]
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    
    try:
        sys.argv[0]='manage.py' #to permit this file to be executed from any location
        execute_from_command_line(sys.argv)
    
    finally:
        print('Closing down background tasks in manage.py')
    
        for t in TASKS:
            print(f'closing task {t}')
            t.stop()
            t.stopper()

