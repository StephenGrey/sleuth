# -*- coding: utf-8 -*-
from django.contrib.auth.models import User, Group, Permission
from django.db.utils import OperationalError
from documents.models import Index
from ownsearch import solrJson,pages, solr_indexes
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations.executor import MigrationExecutor
from django.db import connections, DEFAULT_DB_ALIAS

import getpass,re


class Command(BaseCommand):
    help = 'Test manage.py command'
    
    def handle(self, *args, **options):
        print('SETTING UP SEARCHBOX')
        print('1. CHECKING DATABASE IS INSTALLED')
        if is_database_synchronized(DEFAULT_DB_ALIAS):
            # All migrations have been applied.
            print('... Database installed and synchronised')
        else:
            print('Database needs to be created or updated. Before running \'setup\', run \n\033[1mpython manage.py makemigrations\n\033[0mfollowed by\n\033[1mpython manage.py migrate\033[0m')
            return
        print('2. CHECK SOLR SERVER IS UP AND RUNNING')
        server=check_solr(verbose=True)             
        if not server.server_up:
            print('CONFIGURATION ERROR: Solr server can\'t be launched')
            return
        if not server.example_server_up:
            print('Example solr index missing or needs configuration')
            return
        print('...Solr server is up')
        server.check_or_make_test_index()
        if server.test_index_up:
                print('3. CREATE ADMIN USER')
                if answer_yes('Create admin user? (y/n)'):
                    print('Choose a username, password, email')
                    username=input('Username?')
                    try:
                        admin_user=get_admin(username)
                    except User.DoesNotExist:
                        admin_user=None
                    if admin_user:
                        print('Username \'{}\' exists already'.format(username))
                    else:
                        password=getpass.getpass()
                        my_email=input('Email?')
                        
                        try:
                            admin_user=get_or_create_admin(username,my_email,password)
                        except OperationalError:
                            print('No database created: you need to run \n\033[1mpython manage.py makemigrations\n\033[0mfollowed by\n\033[1mpython manage.py migrate\033[0m')
                print('4. MAKE USERGROUPS')
                admingroup=get_group('adminusers')
                if admingroup:
                    print('admin usergroup exists already')
                    new_usergroup=get_group('usergroup1')
                    if new_usergroup:
                        print('usergroup exists')
                else:
                    print('Creating admin usergroup')
#                if get_group('adminusers'):
#                    print('Adminuser already created in database')
                    admingroup,new_usergroup=make_admingroup(admin_user,verbose=True,admingroupname='adminusers',usergroupname='usergroup1')
                    
                print('5. CREATE BLANK SOLR INDEX')
                print('A blank index can be created, copying the standards settings from the \'coreexample\' index')
                if answer_yes('Make a new index (y/n)?'):
                    indexname=make_new_index_on_server(server)
                    print('Now adding to database')      
                    displayname=make_new_displayname()

                    if new_usergroup:
                        make_default_index(new_usergroup,verbose=True,corename=indexname, coreDisplayName=displayname)
                print("""
Default installation complete

Launch SearchBox in installation directory with shortcut:
./launch   (or python wwwserver/manage.py runserver )

In web browser visit: 
	http://localhost:8000/admin/documents/collection/
to login and add a document collection

To add other users, collections, indexes, usergroups:
	http://localhost:8000/admin

To index the collection, visit:
	http://localhost:8000/documents

To search the index, visit:
	http://localhost:8000                           	 	


                            """)

def make_new_displayname():
    displayname=''
    while not displayname:
        displayname=get_displayname()
    return displayname

def make_new_index():
    server=check_solr(verbose=True) 
    indexname=make_new_index_on_server(server)
    return indexname

def make_new_index_on_server(server):
    indexname=''
    while not indexname:
        indexname=get_corename()                        
    displayname=''
    print(f'Making new index {indexname}')
    
    if server.core_status(indexname):
        print('Index exists already')
        
    else:
        server.make_new_index(indexname)
        server.status_check()
    if not server.index_up(indexname):
        print('ERROR: index \'{}\' not running'.format(indexname))
    else:
        print('.... index \'{}\' up and running on solr'.format(indexname))
    return indexname

def make_admin_or_login(tester):
    """make admin or login for test object"""
    username='myuser'
    my_email='myemail@test.com'
    password=tester.password
    
    tester.admin_user=get_or_create_admin(username,my_email,password)


def get_or_create_admin(username,my_email,password):
    try:
        return get_admin(username)
    except User.DoesNotExist:
        return create_admin(username,my_email,password) 
    
def get_admin(username):
    return User.objects.get(username=username)

def create_admin(username,my_email,password):
    my_admin = User.objects.create_superuser(username,my_email,password)
    return User.objects.get(username=username)
    

def get_group(groupname):
    try:
        return Group.objects.get(name=groupname)
    except Group.DoesNotExist as e:
         return None

def make_admingroup(admin_user,verbose=True,admingroupname='adminusers',usergroupname='usergroup1'): 
    """make an adminusers group containing a user with all permissions"""  
    new_group, created = Group.objects.get_or_create(name=admingroupname)
    if verbose and created:
        print('New group "adminusers" created')
    elif not created:
        print('Adminusers group already exists, or failed to create')
        
    #give all permissions to adminusers
    perms = Permission.objects.all()
    for p in perms:
        new_group.permissions.add(p)
    if verbose:
        print('Added full-permissions to "adminusers"')
    
    #add the admin user to adminusers group
    admin_user.groups.add(new_group)
    if verbose:
        print('Added admin user to "adminusers"')
#        
    """make a sample read-only usergroup group"""  
    new_usergroup, created = Group.objects.get_or_create(name=usergroupname)
    if verbose and created:
        print('New group \"{}\" created'.format(usergroupname))
    elif not created:
        print('\"{}\" group already exists, or failed to create'.format(usergroupname))

    #add the admin user to user group
    admin_user.groups.add(new_usergroup)
    if verbose:
        print('Added admin user to \"{}\"'.format(usergroupname))
    
    return new_group,new_usergroup

def make_default_index(new_usergroup,verbose=True,corename='coreexample', coreDisplayName='Example index'):
    """install a default solr index"""
    
    #check if default exists
    try:
        s=Index.objects.get(corename=corename)
        #make it part of usergroup1
        if s.usergroup==new_usergroup:
            print('.... index already attached to usergroup')
        else:
            s.usergroup=new_usergroup
            s.save()
        
    except Index.DoesNotExist:
        if verbose:
            print('Installing \"{}\"'.format(corename))
        #add the default index, adding to usergroup1
        s,screated=Index.objects.get_or_create(corename=corename,usergroup=new_usergroup, coreDisplayName=coreDisplayName)
        
        if verbose and screated:
            print('Solr index installed: {}'.format(s))
            s.save()
        elif not screated:
            print('\'{}\' solr index already installed, or failed to create'.format(corename))
            

def check_solr(verbose=True):
    """ check if solr server is operating, and example index is present """
    try:
        server=solr_indexes.SolrServer()
        server.example_server_up=False
        server.status_check()
        

        if server.server_up and server.status:
            defaultstatus=server.status.get('coreexample')
            if defaultstatus:
                if defaultstatus.get('name')=='coreexample' and defaultstatus['index'].get('current')==True:
                    mycore=solrJson.SolrCore('coreexample')
                    if mycore.ping():
                        #print('Solr server and "coreexample" index operating and installed')
                        server.example_server_up=True
        return server
    except solrJson.SolrCoreNotFound as e:
        print('Solr core "coreexample" not found on solr server: check installation')
        print('\nNo response from url {}'.format(mycore.url))
        return server
    except solrJson.SolrConnectionError as e:
        print('\nError: cannot connect to Solr server')
        print('Solr server needs to be started.\n(You can use shortcut from SearchBox installation folder:\n\b ./lsolr start \b\nor check configs.)')
        return server
    except solrJson.SolrAuthenticationError as e:
        print('\nError: cannot connect to Solr server')
        print('Check username and password in config files')
        return server

        
    

    """ make a test search, to test further configs """
    page=trysearch(mycore,verbose=verbose)
#    print('DUMMY SEARCH RESULT PAGE: {}'.format(page.__dict__))
    
    print('DEFAULTS INSTALLATION COMPLETE')
    return
        
def trysearch(mycore,verbose=True):
    if verbose:
        print('Running dummy search ...')
    page_number=1
    searchterm='Trump'
    page=pages.SearchPage(page_number=page_number,searchterm=searchterm,direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3='')
    #GET PARAMETERS
    page.safe_searchterm() #makes searchterm_urlsafe; all unicode 
    page.add_filters()       
    page.startnumber=0
    page.faceting=True
    page.mycore=mycore
    solrJson.pagesearch(page)
    if verbose:
        print('Search complete.')
    return page



    

def is_database_synchronized(database):
    connection = connections[database]
    connection.prepare_database()
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return False if executor.migration_plan(targets) else True

# Usage example.
if is_database_synchronized(DEFAULT_DB_ALIAS):
    # All migrations have been applied.
    pass
else:
    # Unapplied migrations found.
    pass

def answer_yes(question):
    answer=input(question)
    yes_answers=['Yes','YES','yes','Y','y']
    if answer in yes_answers:
        return True

def get_corename():
    indexname=input('Name of index? (max 10 letters or numbers or spaces)')
    if len(indexname)>10:
        return ''
    clean_name=re.match('[\w\s]*',indexname)[0]
    if  clean_name!= indexname:
        return ''
    return indexname

def get_displayname():
    displayname=input('Display name of index? (max 20 alpha-numeric characters)')
    if len(displayname)>20:
        return ''
    matches=re.match('[\w\s\\-\"\'\(\)\[\]|!]*',displayname)
    if matches:
        clean_name=matches[0]
        if  clean_name!= displayname:
            return ''
    else:
        return ''
    return displayname
     
     
     
