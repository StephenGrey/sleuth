from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db.models.query import QuerySet
from django.urls import reverse
from documents import setup, documentpage,solrcursor,updateSolr,api,indexSolr,file_utils
from documents.models import  Index, Collection, Source, UserEdit,File
from ownsearch.solrJson import SolrResult,SolrCore
from ownsearch import pages,solrJson
from ownsearch import views as views_search
from django.test.client import Client
import logging,re,requests,getpass,os
from django.core import serializers
from django.conf import settings

## store any password to login later
PASSWORD = 'mypassword' 
MANUAL=False

class DocumentsTest(TestCase):
    """ Tests for documents module """
    def setUp(self):
        #print('This is the set up')
        #print (self._testMethodName)
        #print('Tests: disable logging')
        
        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)
        
        #check admin user exists and login
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

#        # You'll need to log him in before you can send requests through the client
#        self.client.login(username=my_admin.username, password=PASSWORD)
        
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
        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)
            
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
    def setUp(self):
        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)    
    
    def test_updators(self):
       mycore=solrcursor.solrJson.SolrCore('tests_only')
       o=updateSolr.Updater(mycore)
       self.assertIsInstance(o,updateSolr.Updater)

       o=updateSolr.UpdateField(mycore)
       #newvalue='test value',newfield=False,searchterm='*',field_datasource='docpath',field_to_update='sb_parentpath_hash',test_run=True,maxcount=100000
       #args='&fl={},{},database_originalID, sb_filename'.format(o.mycore.unique_id,o.field_datasource_decoded)
       
       o.process(maxcount=1)
       self.assertIsInstance(o,updateSolr.UpdateField)

    
    def test_addparenthash(self):
       
       hashes=file_utils.parent_hashes(['dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf', 'dups/HilaryEmailC05793347.pdf'])
       self.assertEquals(hashes,['b7d16465ed3947cc5849328cf182130e', 'efc6d83504d6183aab785ac3d3576cd1', 'b7d16465ed3947cc5849328cf182130e'])
       
       mycore=solrcursor.solrJson.SolrCore('tests_only')
       self.assertEquals(mycore.parenthashfield,'sb_parentpath_hash')
       
       o=updateSolr.AddParentHash(mycore,field_datasource='docpath',field_to_update=mycore.parenthashfield,test_run=True)
       self.assertIsInstance(o,updateSolr.AddParentHash)
#       print(o.__dict__)
       self.assertFalse(o.update_errors)

#LIVETEST
#       o=updateSolr.AddParentHash(solrcursor.solrJson.SolrCore('tests_only'),field_datasource='docpath',field_to_update='sb_parentpath_hash',test_run=False)
#       self.assertIsInstance(o,updateSolr.AddParentHash)
       
       

class ExtractTest(TestCase):

    """test extract documents to Solr"""
    def setUp(self):
        #CONTROL LOGGING IN TESTS
        #logging.disable(logging.CRITICAL)

        
        #check admin user exists
        make_admin_or_login(self)

        #make an admin group and give it permissions
        admingroup,usergroup=setup.make_admingroup(self.admin_user,verbose=False)
        setup.make_default_index(usergroup,verbose=False,corename='tests_only')
        self.sampleindex=Index.objects.get(corename='tests_only')
        self.testsource, res=Source.objects.get_or_create(sourceDisplayName='Test source',sourcename='testsource')

        self.docstore=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs'))
#        print(self.docstore)
        
        self.testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))
        collectiondups=Collection(path=self.testdups_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collectiondups.save()
        
        self.icij_extract=self.use_icij_extract()

    def use_icij_extract(self):
        return False
        
    def test_Extractor(self):
        mycore=solrJson.SolrCore('tests_only')
        
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(mycore)
        self.assertTrue(status)
        
        #make non-existent collection
        collection=Collection(path='some/path/somewhere',core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collection.save()
        ext=indexSolr.Extractor(collection,mycore,useICIJ=self.icij_extract)
        #NOTHING HAPPENS ON EMPTY FILELIST
        
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection)
        self.assertEquals(scanfiles,[0, 0, 0, 0, 0])
        collection.save()
        
        testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))
        collectiondups=Collection.objects.get(path=testdups_path)

        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collectiondups)        
        self.assertEquals(scanfiles,[6, 0, 0, 0, 0])

        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        self.assertEquals((4,2,0),(ext.counter,ext.skipped,ext.failed))

        self.assertEquals(indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore).data['docpath'],['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        
        #,['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        
    
    def test_indexfile(self):
        #dummy run
        mycore=solrJson.SolrCore('tests_only')
        indexSolr.extract_test(mycore=mycore,test=True,docstore=self.docstore)
        
        #livetest on test index
        indexSolr.extract_test(mycore=mycore,test=False,docstore=self.docstore)
    
    def test_update_parent_hashes(self):
        #index sample PDF
        
        mycore=solrJson.SolrCore('tests_only')

        
        indexSolr.extract_test(mycore=mycore,test=False,docstore=self.docstore)
        solrid="b0e08515ec0c602dbc1a0997c7f37d715cfda1b08080c1a96e42cde0b041e8c1"
        
        
        existing_parenthash=solrJson.getfield(solrid,mycore.parenthashfield,mycore)
        self.assertEquals(existing_parenthash,"8bc944dbd052ef51652e70a5104492e3")

        result=updateSolr.updatetags(solrid,mycore,field_to_update=mycore.parenthashfield,value=['8bc944dbd052ef51652e70a5104492e3','somerandomhash'])

        new_parenthash=solrJson.getfield(solrid,mycore.parenthashfield,mycore)
        self.assertEquals(new_parenthash,['8bc944dbd052ef51652e70a5104492e3', 'somerandomhash'])
    
    def test_deletefiles(self):
        """ remove one among several duplicates"""
        
        testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))
        collectiondups=Collection.objects.get(path=testdups_path)
        tempdir=os.path.join(self.docstore,'temp')
        origindir=os.path.join(self.docstore,'dups')
        filename='HilaryEmailC05793347.pdf'
        mycore=solrJson.SolrCore('tests_only')

        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(mycore)
        self.assertTrue(status)

        try: #put back file from failed test
            os.rename(os.path.join(tempdir,filename),os.path.join(origindir,filename))        
        except:
            pass

        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collectiondups,docstore=self.docstore) 
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        
        self.assertEquals(updated_doc.data['docpath'],['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        self.assertEquals(updated_doc.data[mycore.parenthashfield],['b7d16465ed3947cc5849328cf182130e', 'b7d16465ed3947cc5849328cf182130e', 'efc6d83504d6183aab785ac3d3576cd1'])#,['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        

        #MOVE OUT OF COLLECTION
        os.rename(os.path.join(origindir,filename),os.path.join(tempdir,filename))
        
        scanfiles=updateSolr.scandocs(collectiondups,docstore=self.docstore)
        self.assertEquals(scanfiles,[0, 1, 0, 5, 0])      
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        self.assertEquals(updated_doc.data['docpath'],
        ['dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        self.assertEquals(updated_doc.data[mycore.parenthashfield],['b7d16465ed3947cc5849328cf182130e', 'efc6d83504d6183aab785ac3d3576cd1'])
        
        #MOVE BACK AGAIN
        os.rename(os.path.join(tempdir,filename),os.path.join(origindir,filename))        
        scanfiles=updateSolr.scandocs(collectiondups,docstore=self.docstore)        
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        self.assertEquals(updated_doc.data['docpath'],
        ['dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf', 'dups/HilaryEmailC05793347.pdf'])

        self.assertEquals(updated_doc.data[mycore.parenthashfield],["b7d16465ed3947cc5849328cf182130e", "efc6d83504d6183aab785ac3d3576cd1", "b7d16465ed3947cc5849328cf182130e"])
        
    def test_changefiles(self):
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes'))
        mycore=solrJson.SolrCore('tests_only')
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)

#        collection=Collection(path=self.testdups_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
#        collectiondups.save()
        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        updated_doc=indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore)
        self.assertEquals(updated_doc.data['docpath'],['changes/changingfile.txt'])
        self.assertEquals(indexSolr.check_hash_in_solrdata("4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0",mycore),None)
        
        
        change_file()
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        change_file()
        self.assertEquals(indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore),None)
        self.assertEquals(indexSolr.check_hash_in_solrdata("4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0",mycore).data['docpath'],['changes/changingfile.txt'])

    def test_change_dupfiles(self):
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes_and_dups'))
        mycore=solrJson.SolrCore('tests_only')
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)

        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore)

        
        change_file(relpath='changes_and_dups/changingfile.txt')
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        change_file(relpath='changes_and_dups/changingfile.txt')

class ICIJExtractTest(ExtractTest):
    def use_icij_extract(self):
        return True
        
class ChangeApiTests(TestCase):
    """test Api for returning user changes"""
    #
    
    def setUp(self):

        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)

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
        
    def test_get_remotechanges(self,manual=MANUAL):
        #this test will only operate manually
        if manual:
            api.get_remotechanges(test=True)
    
    def test_update_unprocessed(self):
        api.update_unprocessed(admin=True,test=True)
    
    def test_process_remotechanges(self):
        # Establish an indexing page
        self.page=documentpage.CollectionPage()
#        self.page.getcores(self.admin_user)
        api.update_unprocessed(admin=True,test=True)

#    def test_getfield(self):
#        solrid=input("Solr ID?")
#        corename=input("corename?")
#        core=SolrCore(corename)
#        field_text=solrJson.getfield(solrid,core.usertags1field,core)
#        print(field_text)
        
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
        

def change_file(docstore=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs')),relpath='changes/changingfile.txt'):
    """a test file that alternates contents"""
    filepath=os.path.join(docstore,relpath)
    #print(filepath)
    text1="The first version of events"
    text2="The second version of events"
    with open(filepath, "r+") as f:
        data = f.read()
        f.seek(0)
        if data==text1:
            f.write(text2)
            f.truncate()
        else:
            f.write(text1)
            f.truncate()


