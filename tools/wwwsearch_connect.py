"""connect to Django"""
import sys,os
#get path to Django application - go up to project root, then down to the application 
projpath=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'wwwsearch')
sys.path.append(projpath)

# This is so Django knows where to find stuff.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
# This is so my local_settings.py gets loaded.
os.chdir(projpath)

# This is so models get loaded.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
