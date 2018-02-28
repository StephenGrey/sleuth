from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from documents.models import SolrCore
from ownsearch import solrJson,pages


class Command(BaseCommand):
    def handle(self,*args, **options):
        print ('Setup database')
        person = input('Enter your admin username: ')
        try:
            u=User.objects.get(username=person)
            print('Confirming "{}" is an installed user '.format(person))
        except User.DoesNotExist as e:
            print('User does not exist')
            print('Make an admin user by running: \n $ python manage.py createsuperuser')
            print('DEFAULTS INSTALLATION NOT COMPLETE')
            return
#       
        if not u.is_superuser or not u.is_staff:
            print('"{}" is not an admin or superuser '.format(person))
            print('Make an admin user by running admin interface or with command: \n $ python manage.py createsuperuser')
            print('DEFAULTS INSTALLATION NOT COMPLETE')
            return


        """make an adminusers group with all permissions"""  
        new_group, created = Group.objects.get_or_create(name='adminusers')
        if created:
            print('New group "adminusers" created')
        else:
            print('Adminusers group already exists, or failed to create')
            
        
        #give all permissions to adminusers
        perms = Permission.objects.all()
        for p in perms:
            new_group.permissions.add(p)
        print('Added permissions to adminusers group')
        
        #add the admin user to adminusers group
        u.groups.add(new_group)
        print('Added admin user to adminusers group')
#        
        """make a sample usergroup group to read indexes only"""  
        new_usergroup, created = Group.objects.get_or_create(name='usergroup1')
        if created:
            print('New group "usergroup1" created')
        else:
            print('usergroup1 group already exists, or failed to create')

        #add the admin user to user group
        u.groups.add(new_usergroup)
        print('Added admin user to usergroup1 group')
        
        
        """install the default solr index"""
        
        #check if default exists
        try:
            s=SolrCore.objects.get(corename='coreexample')
            #make it part of usergroup1
            s.usergroup=new_usergroup
            s.save()
            
        except SolrCore.DoesNotExist:
            print('Installing "coreexample"')
            #add the default index, adding to usergroup1
            s,screated=SolrCore.objects.get_or_create(corename='coreexample',usergroup=new_usergroup, coreDisplayName='Example index',coreID=1)
            
            if screated:
                print('Solr index installed: {}'.format(s))
            else:
                print('"coreexample" solr index already installed, or failed to create')
            
        """ check if solr server is operating, and example index is present """
        mycore=solrJson.SolrCore('coreexample')
        try:
            if mycore.ping():
                print('Solr server and example index operating and installed')
        except solrJson.SolrCoreNotFound as e:
            print('Solr core "coreexample" not found on solr server: check installation')
            print('\nNo response from url {}'.format(mycore.url))
            return
        except solrJson.SolrConnectionError as e:
            print('\nError: cannot connect to Solr server\nFailed to reach url: {}'.format(mycore.url))
            print('Solr server needs to be started.\n(You can use shortcut from SearchBox installation folder:\n\b ./lsolr start \b\nor check configs.)')
            return
        
        """ make a test search, to test further configs """
        page=trysearch(mycore)
        print('DUMMY SEARCH RESULT PAGE: {}'.format(page.__dict__))
        
        print('DEFAULTS INSTALLATION COMPLETE')
        return
        

def trysearch(mycore):
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
    print('Search complete.')
    return page
