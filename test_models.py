from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.core.urlresolvers import reverse
from documents.models import Index
from ownsearch import solrJson,pages
from documents import setup
from django.test.client import Client
import logging,re

# store the password to login later
password = 'mypassword' 

class DocumentsTest(TestCase):
    def setUp(self):
#        print('Tests: disable logging')
#        logging.disable(logging.CRITICAL)
        print('Tests: setting up a user, usergroup and permissions')
        my_admin = User.objects.create_superuser('myuser', 'myemail@test.com', password)
#        print(User.objects.all())
        admin_user=User.objects.get(username='myuser')
        #make an admin group and give it permissions
        admingroup,usergroup=setup.make_admingroup(admin_user)
#        print(Group.objects.all())
        setup.make_default_index(usergroup)
        
        # You'll need to log him in before you can send requests through the client
        self.client.login(username=my_admin.username, password=password)
        
        
    def test_indexes(self):
        """check access to solrindex """
        setup.check_solr()
        pass
        
    def test_authorise(self):
        """check user has access to example index"""
        import ownsearch.authorise as a
        admin_user=User.objects.get(username='myuser')        
        authcores=a.AuthorisedCores(admin_user)
        self.assertEqual(authcores.mycore.name,'coreexample')
        print('Authorise test complete')

#    def test_testpage(self):
        #"""use test page to experiment"""
#        response=self.client.get(reverse('test_index'))
##        print(response.status_code)
##        print("Response: {}".format(response.__dict__))
#        self.assertEqual(response.status_code,200)

    def test_search(self):
        
        """run searches of solr index"""
        self.client.login(username='myuser', password=password)        
        
        #documents view
        response = self.client.get(reverse('docs_index'))
        self.assertEqual(response.status_code,200)
#        print(response.status_code)
#        print(response.cookies)
#        print(response.cookies['csrftoken'])
#        try:
        ctoken=self.client.cookies['csrftoken'].value
        print(ctoken)

        
        """index forms"""
        from documents.forms import IndexForm
        from documents.forms import get_corechoices
        choices=get_corechoices()
        print(choices)
        firstchoice=choices[0][0] #get first choice of index available
#        f.fields['CoreChoice'].widget.choices[
        f=IndexForm()
#        f=IndexForm(data={'csrfmiddlewaretoken':ctoken,'CoreChoice':str(firstchoice)})   #'csrfmiddlewaretoken':ctoken,
        f.is_valid()
        print(f.__dict__, f.fields['CoreChoice'].choices)
        self.assertTrue(f.is_valid())


#        cookies['csrftoken'].value)
#        print(type(cookies))
#        print(str(cookies))
#        ctoken=re.match('.*csrftoken=(\w*);',cookies).group(1)
#        print(ctoken)
        #choose index view
        response = self.client.post(reverse('docs_index'),{'csrfmiddlewaretoken':ctoken,'CoreChoice':'1'})
        self.assertEqual(response.status_code,200)
        print(response.status_code)

#        print("Response: {}".format(response.content))


#        response=self.client.get(reverse('test_index'))

#        #index search
#        response = self.client.get(reverse('searchview'))
#        self.assertEqual(response.status_code,200)
##        print("Response: {}".format(response.__dict__))
#        response = self.client.get(reverse('searchpageview', kwargs={'searchterm':'Trump', 'page_number':0,'sorttype':'date'}))
#        self.assertEqual(response.status_code,200)
#        print('Tests: Index searches completed')
##        print("Response: {}".format(response.__dict__))
#
