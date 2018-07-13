from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db.models.query import QuerySet
from django.urls import reverse
from documents import setup, documentpage,solrcursor,updateSolr,api
from documents.models import  Index, Collection, Source, UserEdit
from ownsearch.solrJson import SolrResult,SolrCore
from ownsearch import pages
from ownsearch import views as views_search
from django.test.client import Client
import logging,re,requests
from django.core import serializers

## store any password to login later
PASSWORD = 'mypassword' 


class DocumentsTest(TestCase):
    """ Tests for documents module """
    def setUp(self):
        #print('This is the set up')
        #print (self._testMethodName)
        #print('Tests: disable logging')
        
        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)
        
#        #print('Tests: setting up a user, usergroup and permissions')
#        my_admin = User.objects.create_superuser('myuser', 'myemail@test.com', PASSWORD)
#        self.admin_user=User.objects.get(username='myuser')
        
        #check admin user exists
        make_admin_or_login(self)
        
        #make an admin group and give it permissions
        admingroup,usergroup=setup.make_admingroup(self.admin_user,verbose=False)
#        print(Group.objects.all())
        setup.make_default_index(usergroup,verbose=False)
        self.sampleindex=Index.objects.get(corename='coreexample')
        
        #make a sample source
        source=Source(sourceDisplayName='Test source',sourcename='testsource')
        source.save()
        
        #make a test collection
        samplecollection=Collection(path='some/path/somewhere',core=self.sampleindex,indexedFlag=False,source=source)
        samplecollection.save()
        anothercollection=Collection(path='another/different/path/somewhere',core=self.sampleindex,indexedFlag=False,source=source)
        anothercollection.save()

        # You'll need to log him in before you can send requests through the client
        self.client.login(username=my_admin.username, password=PASSWORD)
        
        # Establish an indexing page
        self.page=documentpage.CollectionPage()

    def test_getcores(self):
        """test get cores"""
        self.page.getcores(self.admin_user)
        self.assertEqual(self.page.coreID,1)
        self.assertEqual(self.page.cores[1].name,'coreexample')
       
    def test_choooseindexes(self):
        self.page.getcores(self.admin_user)
        
        #post a choice
        request_method="POST"
        data={'corechoice': '1'}
        self.page.chooseindexes(request_method,request_postdata=data,test=True)
        self.assertEqual(self.page.coreID,1)
        #print(self.page.form)
        self.assertTrue(self.page.validform)

        #get choice
        request_method="GET"
        data={}
        self.page.chooseindexes(request_method,request_postdata=data)
        self.assertEqual(self.page.coreID,1)
        self.assertTrue(isinstance(self.page.form,documentpage.IndexForm))
     
    def test_indexform(self):
        """index forms"""
        from documents.forms import IndexForm,TestForm
        from documents.forms import get_corechoices
        choices=get_corechoices()
        self.assertEqual(choices,((1, 'Example index'),))

        #test the test form
        f=TestForm(data={'testfield':'something','corechoice':"1"})
        f.fields['corechoice'].choices=choices
        f.is_valid()
        self.assertTrue(f.is_valid())
        
        #test the index form
        f=IndexForm(data={'corechoice':"1"})
        #print(f.fields['corechoice'].choices)
        #NOT CLEAR WHY THIS SHOULD BE NECESSARY
        f.fields['corechoice'].choices=choices
        #print(f.fields['corechoice'].choices)        
        f.is_valid()
        self.assertTrue(f.is_valid())
        
        #post data into the index form
        self.page.post_indexform(f)
        self.assertEqual(self.page.coreID,1)
        self.assertTrue(self.page.validform)

    def test_authorised_collections(self):
        """get authorised collections"""
        self.page.getcores(self.admin_user)
        self.page.get_collections()
        ac=self.page.authorised_collections
        self.assertEqual(QuerySet,type(ac))
        self.assertEqual(len(ac),2)
        self.assertEqual(Collection,type(ac[0]))
    	
class CursorTest(TestCase):
    """ Tests for solrcursor module """
    def setUp(self):
        pass
            
    def test_cursor_by_name(self):
        """test cursor on named index"""
        self.assertEqual(solrcursor.cursor_by_name(),{})
        pass
        
    def test_cursor_sorted(self):
        """test cursor sorted by key"""
        res=solrcursor.cursor_sorted('*','docpath',solrcursor.solrJson.SolrCore('coreexample'))
        assert isinstance(res,solrcursor.collections.OrderedDict)
        
    def test_cursor_next(self):
        """test cursor_next - iterate in groups"""
        res=solrcursor.cursor_next(solrcursor.solrJson.SolrCore('tests_only'),searchterm='*',highlights=True,lastresult=False,rows=10)
        assert isinstance(res,SolrResult)
        self.assertEqual(res.json['responseHeader']['status'],0) #good solr response

class UpdatingTests(TestCase):
    """tests for updateSolr module"""
    
    
    def test_updators(self):
       mycore=solrcursor.solrJson.SolrCore('tests_only')
       o=updateSolr.Updater(mycore)
       self.assertIsInstance(o,updateSolr.Updater)
       o=updateSolr.UpdateField(mycore)
       args='&fl={},{},database_originalID, sb_filename'.format(o.mycore.unique_id,o.field_datasource_decoded)
       o.process(args)
       self.assertIsInstance(o,updateSolr.UpdateField)

    
    def test_addparenthash(self):
       o=updateSolr.AddParentHash(solrcursor.solrJson.SolrCore('tests_only'),field_datasource='docpath',field_to_update='sb_parentpath_hash',test_run=True)
       self.assertIsInstance(o,updateSolr.AddParentHash)
       #print(o.__dict__)
       o=updateSolr.AddParentHash(solrcursor.solrJson.SolrCore('tests_only'),field_datasource='docpath',field_to_update='sb_parentpath_hash',test_run=False)
       self.assertIsInstance(o,updateSolr.AddParentHash)
       
    

class ChangeApiTests(TestCase):
    """test Api for returning user changes"""
    #
    
    def setUp(self):
        #check admin user exists
        make_admin_or_login(self)
        
         
        #make some user edits
        self.page=pages.ContentPage(doc_id='someid',searchterm='test searchterm')
        self.page.mycore=SolrCore('some_solr_index',test=True)
        
        keyclean=[re.sub(r'[^\w, ]','',item) for item in ['Donald Trump','Cat','Tower']]
        views_search.update_user_edits(self.page,keyclean,'admin')
        
        self.page=pages.ContentPage(doc_id='someid2',searchterm='another searchterm')
        self.page.mycore=SolrCore('some_solr_index',test=True)
        keyclean=[re.sub(r'[^\w, ]','',item) for item in ['Hilary Clinton','politics','USA']]
        views_search.update_user_edits(self.page,keyclean,'user1')
        
    def test_api_changes(self):
        
        #check useredits already saved
        existing=UserEdit.objects.all()
        self.assertEquals(existing[0].usertags,"['Donald Trump', 'Cat', 'Tower']")

        #check useredits api
        data=api.get_api_result(self.client,'',selftest=True,updateid=1)
        decoded_data=api.deserial(data)
        
        self.assertIsInstance(decoded_data[0],serializers.base.DeserializedObject)
        self.assertEquals(decoded_data[0].object.usertags,"""['Donald Trump', 'Cat', 'Tower']""")
        
        #check it exists already
        self.assertFalse(api.savecheck(decoded_data[0]))
        for edit in decoded_data:
            if api.savecheck(edit):
                edit.save()
            else:
                api.changes_append(edit)
                
        new_changes=UserEdit.objects.all()
        self.assertEquals(new_changes[2].usertags,"['Donald Trump', 'Cat', 'Tower']")
        self.assertEquals(new_changes[2].pk,3)
               
        #add sample data 
        data="""[{"model": "documents.useredit", "pk": 1, "fields": {"solrid": "j98kjdf9u9384jkjdf", "usertags": "[u'Karl Smith', u'Mark Brown', u'BritishTelecom']", "username": "admin", "time_modified": "2018-01-24T15:29:35.496Z", "corename": "Morocco"}}]"""
         
        #check adding new docs to UserEdit database
        api.process_api_result(data)
        self.assertEquals(UserEdit.objects.all()[3].pk,4)
        self.assertEquals(UserEdit.objects.all()[3].usertags,"[u'Karl Smith', u'Mark Brown', u'BritishTelecom']")
        
    def test_get_remotechanges(self):
        u=api.Updater()
        u.process()
    
    def test_process_remotechanges(self):
        # Establish an indexing page
        self.page=documentpage.CollectionPage()
#        self.page.getcores(self.admin_user)
       
        api.update_unprocessed(admin=True,test=True)

        
    def test_set_flag(self):
        edit=UserEdit.objects.get(pk=1)
        flag=edit.index_updated
        api.set_flag(edit,value=True,attr='index_updated')
        self.assertEquals(edit.index_updated,True)
        api.set_flag(edit,value=False,attr='index_updated')
        self.assertEquals(edit.index_updated,False)
        
    
    def test_tagform(self):
        #post a choice
        from django.http import QueryDict
        request_method="POST"
        data=QueryDict('',mutable=True)
        data.update({'keywords':"Donald Trump, Richard Nixon"})
        form=views_search.TagForm('',data)
        form.is_valid()        
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['keywords']==['Donald Trump', 'Richard Nixon'] or form.cleaned_data['keywords']==['Richard Nixon','Donald Trump'])
        
    def test_deserial_taglist(self):
        stored="[u'Donald Trump', u'Richard Nixon']"
        #print(api.deserial_taglist(stored))
        self.assertEquals(api.deserial_taglist(stored),['Donald Trump', 'Richard Nixon'])

def make_admin_or_login(tester):
    try:
        tester.admin_user=User.objects.get(username='myuser')
    except User.DoesNotExist:
        my_admin = User.objects.create_superuser('myuser', 'myemail@test.com', PASSWORD)
        tester.admin_user=User.objects.get(username='myuser')

    #login as admin
    tester.client.login(username=my_admin.username, password=PASSWORD)
        