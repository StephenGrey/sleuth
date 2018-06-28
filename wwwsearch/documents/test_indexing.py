from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db.models.query import QuerySet
from documents import setup, documentpage,solrcursor,updateSolr
from documents.models import  Index, Collection, Source
from ownsearch.solrJson import SolrResult
from django.test.client import Client
import logging,re

## store any password to login later
password = 'mypassword' 


class DocumentsTest(TestCase):
    """ Tests for documents module """
    def setUp(self):
        #print('This is the set up')
        #print (self._testMethodName)
        #print('Tests: disable logging')
        
        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)
        
        #print('Tests: setting up a user, usergroup and permissions')
        my_admin = User.objects.create_superuser('myuser', 'myemail@test.com', password)
        self.admin_user=User.objects.get(username='myuser')
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
        self.client.login(username=my_admin.username, password=password)
        
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
       
    
