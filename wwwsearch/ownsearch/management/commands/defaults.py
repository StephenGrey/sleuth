from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from documents.models import Index
#from ownsearch import solrJson,pages
from documents import setup

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

        admingroup,usergroup=setup.make_admingroup(u)
        setup.make_default_index(usergroup)
        setup.check_solr()
            

#
#def make_admingroup(u):
#    """make an adminusers group with all permissions"""  
#    new_group, created = Group.objects.get_or_create(name='adminusers')
#    if created:
#        print('New group "adminusers" created')
#    else:
#        print('Adminusers group already exists, or failed to create')
#        
#    
#    #give all permissions to adminusers
#    perms = Permission.objects.all()
#    for p in perms:
#        new_group.permissions.add(p)
#    print('Added permissions to adminusers group')
#    
#    #add the admin user to adminusers group
#    u.groups.add(new_group)
#    print('Added admin user to adminusers group')
##        
#    """make a sample usergroup group to read indexes only"""  
#    new_usergroup, created = Group.objects.get_or_create(name='usergroup1')
#    if created:
#        print('New group "usergroup1" created')
#    else:
#        print('usergroup1 group already exists, or failed to create')
#
#    #add the admin user to user group
#    u.groups.add(new_usergroup)
#    print('Added admin user to usergroup1 group')
#    
#    return new_group,new_usergroup
#
#        """install the default solr index"""
#        
#        #check if default exists
#        try:
#            s=Index.objects.get(corename='coreexample')
#            #make it part of usergroup1
#            s.usergroup=new_usergroup
#            s.save()
#            
#        except Index.DoesNotExist:
#            print('Installing "coreexample"')
#            #add the default index, adding to usergroup1
#            s,screated=Index.objects.get_or_create(corename='coreexample',usergroup=new_usergroup, coreDisplayName='Example index')
#            
#            if screated:
#                print('Solr index installed: {}'.format(s))
#            else:
#                print('"coreexample" solr index already installed, or failed to create')
#
    
        

