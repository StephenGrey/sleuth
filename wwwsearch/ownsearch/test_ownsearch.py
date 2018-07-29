from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
try:
    from django.core.urlresolvers import reverse,resolve
except ImportError:
    from django.urls import reverse,resolve,NoReverseMatch
from documents.models import Index,Source
from ownsearch import solrJson,pages,solr_indexes
from documents import setup
from django.test.client import Client
import logging,re,os
log = logging.getLogger('ownsearch.tests')

# store the password to login later
password = 'mypassword' 

class DocumentsTest(TestCase):
    def setUp(self):
#        print('Tests: disable logging')
        logging.disable(logging.CRITICAL)
        #print('Tests: setting up a user, usergroup and permissions')
        my_admin = User.objects.create_superuser('myuser', 'myemail@test.com', password)
#        print(User.objects.all())
        self.admin_user=User.objects.get(username='myuser')
        #make an admin group and give it permissions
        admingroup,usergroup=setup.make_admingroup(self.admin_user,verbose=False)

        setup.make_default_index(usergroup,verbose=False,corename='tests_only',coreDisplayName='Tests')
        self.sampleindex=Index.objects.get(corename='tests_only')
        self.testsource, res=Source.objects.get_or_create(sourceDisplayName='Test source',sourcename='testsource')
        
        # You'll need to log him in before you can send requests through the client
        self.client.login(username=my_admin.username, password=password)
        

    def test_indexes(self):
        """check access to solrindex """
        server=setup.check_solr(verbose=False)
        self.assertTrue(server.server_up)
        
    def test_authorise(self):
        """check user has access to example index"""
        import ownsearch.authorise as a
        self.admin_user=User.objects.get(username='myuser')        
        authcores=a.AuthorisedCores(self.admin_user)
        self.assertEqual(authcores.mycore.name,'tests_only')
        #print('Authorise test complete')

    def test_testpage(self):
        """use test page to experiment"""
        response=self.client.get(reverse('test_index'))
        self.assertEqual(response.status_code,200)

    def test_docs_index(self):        
        """run searches of solr index"""
        self.client.login(username='myuser', password=password)        
        
        #documents view
        response = self.client.get(reverse('docs_index'))
        self.assertEqual(response.status_code,200)
        ctoken=self.client.cookies['csrftoken'].value
        log.debug('CSRF token: {}'.format(ctoken))

        #choose index view
        response = self.client.post(reverse('docs_index'),{'csrfmiddlewaretoken':ctoken,'corechoice':'1'})
        self.assertEqual(response.status_code,200)

    def test_searchview(self):  
        """test searchview"""
        response = self.client.get(reverse('searchview'))
        self.assertEqual(response.status_code,200)
        #print("Response: {}".format(response.__dict__))
    
    def test_searchpageview(self):
        """test search page view"""  
        response = self.client.get(reverse('searchpageview', kwargs={'searchterm':'*', 'page_number':1,'sorttype':'relevance'}))
        #print("Response: {}".format(response.content))
        self.assertFalse("No results for search" in response.content.decode("utf-8"))
        response = self.client.get(reverse('searchpageview', kwargs={'searchterm':'Trump', 'page_number':0,'sorttype':'date'}))
        self.assertEqual(response.status_code,200)
        #print('Tests: Index searches completed')
        #print("Response: {}".format(response.__dict__))
        
class SolrTest(TestCase):
    def setUp(self):
        self.mycorename="SOME_NONEXISTENT_INDEX87a9dfkahsdfkh"
        pass
    def test_SolrCore(self):
        """create SolrCore and SolrResult object"""

        mycore=solrJson.SolrCore(self.mycorename)
        self.assertRaises(solrJson.SolrCoreNotFound, mycore.ping)
        
        result=solrJson.SolrResult({},mycore)
        self.assertEqual(result.json,{})
        self.assertEqual(result.mycore,mycore)

class SolrIndexesTest(TestCase):
    def setUp(self):
        """check status of solr server"""
        self.server=solr_indexes.SolrServer()
        self.server.status_check()
        self.server.check_or_make_test_index()
            
    def test_status(self):
        #check default
        defaultstatus=self.server.status['coreexample']
        self.assertEqual(defaultstatus['name'],'coreexample')
        self.assertEqual(defaultstatus['index']['current'],True)
        self.assertTrue(self.server.default_index_up)

    def test_default_location(self):
        #print(server.status)
        instanceDir=self.server.status['coreexample']['instanceDir']
        dataDir=self.server.status['coreexample']['dataDir']

        #check core example configured
        self.assertTrue(solr_indexes.check_corename(instanceDir))
        self.assertTrue(os.path.exists(self.server.solrdir))
        self.assertTrue(os.path.isdir(self.server.solrdir))
    
    def test_multivalued(self):
        """ test one solr index location"""
        self.assertFalse(self.server.solrdir_multivalued) #check only one solr dir
        
        
    def test_testindex(self):
        """check \"tests_only\" index up"""
        self.assertTrue(self.server.test_index_up)
        #solr_indexes.copy_index_schema(self.server.solrdir) #default: copy coreexample to tests_only

    def test_corenames(self):
        """check correct core name in solr configs"""
        for corename in self.server.cores:
            instanceDir=self.server.status[corename]['instanceDir']
            self.assertTrue(solr_indexes.check_corename(instanceDir))

    def test_create_index(self):
        """check register new solr index"""
        #test bad index name
        self.assertEquals(solr_indexes.create_index(os.path.join(self.server.solrdir,'test wrongname')),400)        
        #test index already exists
        self.assertEquals(solr_indexes.create_index(os.path.join(self.server.solrdir,'tests_only')),500)
        mycore=solrJson.SolrCore('tests_only')
        self.assertTrue(mycore.ping())
    
    def test_defaultsup(self):
        """checking 'coreexample' and 'tests_only' indexes are up and running"""
        self.assertTrue(self.server.status.get('tests_only'))
        self.assertTrue(self.server.status['tests_only']['index']['current'])
        self.assertTrue(self.server.status.get('coreexample'))
        self.assertTrue(self.server.status['coreexample']['index']['current'])
        


class UrlsTest(TestCase):
    def setUp(self):
#        print('Tests: disable logging')
        logging.disable(logging.CRITICAL)
        
    def test_simplesearch(self):        
         res=resolve("/ownsearch/searchterm=%252A&page=1&sorttype=relevance&filters=tag1=Donald Trump")
         #print(res.__dict__)
         self.assertEquals(res.kwargs,{'searchterm': '%252A', 'page_number': '1', 'sorttype': 'relevance', 'tag1field': 'tag1', 'tag1': 'Donald Trump', 'tag2field': None, 'tag2': None, 'tag3field': None, 'tag3': None,'start_date': None, 'end_date': None})
    def tests_tagsearch(self):
         params={'page_number':1,'sorttype':'relevance','searchterm':'test'}
         params.update({'tag1field':'tag1','tag1':'sometag'})
         rev=reverse('searchpagefilters',kwargs=params)
         print(rev)
         self.assertEquals(rev,"/ownsearch/searchterm=test&page=1&sorttype=relevance&filters=tag1=sometag")
         params.update({'start_date':'01012000'})
         rev=reverse('searchpagefilters',kwargs=params)
         self.assertEquals(rev,"/ownsearch/searchterm=test&page=1&sorttype=relevance&filters=tag1=sometag&start_date=01012000")
         params.update({'tag2field': 'secondfield', 'tag2': 'secondvalue'})
         rev=reverse('searchpagefilters',kwargs=params)
         self.assertEquals(rev,"/ownsearch/searchterm=test&page=1&sorttype=relevance&filters=tag1=sometag&tag=secondfield=secondvalue&start_date=01012000")
         
         res=resolve("/ownsearch/searchterm=test&page=1&sorttype=relevance&filters=tag1=sometag&tag=secondfield=secondvalue&start_date=01012000")
         print(res.kwargs)
         self.assertEquals(res.kwargs,{'searchterm': 'test', 'page_number': '1', 'sorttype': 'relevance', 'tag1field': 'tag1', 'tag1': 'sometag', 'tag2field': 'secondfield', 'tag2': 'secondvalue', 'start_date': '01012000', 'end_date': None,'tag3field': None, 'tag3': None})
         
##        firstchoice=choices[0][0] #get first choice of index available
###        f.fields['CoreChoice'].widget.choices[
##        #f=IndexForm()
##        f=IndexForm(data={'csrfmiddlewaretoken':ctoken,'CoreChoice':"1"})   #'csrfmiddlewaretoken':ctoken,
###         print('Choicefield: {}'.format(f.fields['CoreChoice'].__dict__))
##        f.is_valid()
##        print(f.__dict__, f.fields['CoreChoice'].choices)
###        self.assertTrue(f.is_valid())
##        
##
#
##        cookies['csrftoken'].value)
##        print(type(cookies))
##        print(str(cookies))
##        ctoken=re.match('.*csrftoken=(\w*);',cookies).group(1)
##        print(ctoken)
#
##        print("Response: {}".format(response.content))
#
#
##        response=self.client.get(reverse('test_index'))
#
##
