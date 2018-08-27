from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db.models.query import QuerySet
from django.urls import reverse
from documents import documentpage,solrcursor,updateSolr,api,indexSolr,file_utils,changes

from documents.management.commands import setup
from documents.management.commands.setup import make_admin_or_login
from documents.models import  Index, Collection, Source, UserEdit,File
from ownsearch.solrJson import SolrResult,SolrCore
from ownsearch import pages,solrJson
from ownsearch import views as views_search
from django.test.client import Client
import logging,re,requests,getpass,os,shutil
from django.core import serializers
from django.conf import settings

## store any password to login later
PASSWORD = 'mypassword' 
MANUAL=False

class IndexTester(TestCase):
    def makebase(self):
        #CONTROL LOGGING IN TESTS
        #logging.disable(logging.CRITICAL)
        self.password=PASSWORD
        self.username='myuser'
        self.my_email='myemail@test.com'
        #check admin user exists and login
        make_admin_or_login(self)
        
        #login as admin
        self.client.login(username=self.username, password=self.password)

                #make an admin group and give it permissions
        admingroup,usergroup=setup.make_admingroup(self.admin_user,verbose=False)
        setup.make_default_index(usergroup,verbose=False,corename='tests_only')
        self.sampleindex=Index.objects.get(corename='tests_only')
        
        #make a sample source
        self.testsource=Source(sourceDisplayName='Test source',sourcename='testsource')
        self.testsource.save()
        

        #make a test collection
        samplecollection=Collection.objects.get_or_create(path='some/path/somewhere',core=self.sampleindex,indexedFlag=False,source=self.testsource)
#        samplecollection.save()
        anothercollection=Collection.objects.get_or_create(path='another/different/path/somewhere',core=self.sampleindex,indexedFlag=False,source=self.testsource)
#        anothercollection.save()
        
        #DUPS
        self.testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))

        collectiondups=Collection(path=self.testdups_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collectiondups.save()
        self.collectiondups=collectiondups
        
        # Establish an indexing page
        self.page=documentpage.CollectionPage()

        self.docstore=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs'))
        self.mycore=solrcursor.solrJson.SolrCore('tests_only')

#        self.testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))

class ExtractTest(IndexTester):

    """test extract documents to Solr"""
    def setUp(self):
        
        self.makebase()
                
        self.icij_extract=self.use_icij_extract()

    def use_icij_extract(self):
        return False
        
    def test_Extractor(self):
        mycore=self.mycore
        
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(mycore)
        self.assertTrue(status)
        
        #make non-existent collection
        collection=Collection(path='some/path/somewhere',core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collection.save()
        ext=indexSolr.Extractor(collection,mycore,useICIJ=self.icij_extract)
        #NOTHING HAPPENS ON EMPTY FILELIST
        
        #NOW SCAN THE COLLECTION
        scanner=updateSolr.scandocs(collection)
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],[0, 0, 0, 0, 0])
        collection.save()
        
        collectiondups=Collection.objects.get(path=self.testdups_path)

        #NOW SCAN THE COLLECTION
        scanner=updateSolr.scandocs(collectiondups)        
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],[5, 0, 0, 0, 0])

        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        self.assertEquals((5,0,0),(ext.counter,ext.skipped,ext.failed))

        self.assertEquals(indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore).data['docpath'],['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        
        
        
        #['dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        
        
        #,['dups/HilaryEmailC05793347.pdf', 'dups/HilaryEmailC05793347 copy.pdf', 'dups/dup_in_folder/HilaryEmailC05793347 copy.pdf'])
        
    
    def test_indexfile(self):
        #dummy run
        mycore=self.mycore
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
        
        collectiondups=Collection.objects.get(path=self.testdups_path)
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
        
        scanner=updateSolr.scandocs(collectiondups,docstore=self.docstore)
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],[0, 1, 0, 4, 0])      
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
        
        #start with first version
        shutil.copy2(os.path.join(testchanges_path,'1changingfile.txt'),os.path.join(testchanges_path,'changingfile.txt'))
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)


        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        

        updated_doc=indexSolr.check_hash_in_solrdata("4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0",mycore) #first hash
        #print(updated_doc.__dict__)
        self.assertEquals(updated_doc.data['docpath'],['changes/changingfile.txt','changes/1changingfile.txt'])

        self.assertEquals(indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore),None) #second hash
        
        
        change_file()
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)

        change_file()
        self.assertEquals(indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore).data['docpath'],['changes/changingfile.txt'])

    def test_change_meta(self):
    	
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes'))
        mycore=solrJson.SolrCore('tests_only')
        #start with first version
        shutil.copy2(os.path.join(testchanges_path,'1changingfile.txt'),os.path.join(testchanges_path,'changingfile.txt'))
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)


        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        solrid="4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0"

        docs=solrJson.getmeta(solrid,mycore)
        self.assertEquals(docs[0].docname,'changingfile.txt')
        self.assertEquals(docs[0].date,'')
        
        updateSolr.updatetags(solrid,mycore,value='newfilename',field_to_update='docnamesourcefield',newfield=False,test=False)
        
        newdate=solrJson.timestringGMT(solrJson.datetime.now())
        
        updateSolr.updatetags(solrid,mycore,value=newdate,field_to_update='datesourcefield',newfield=False,test=False)
        
        doc=solrJson.getmeta(solrid,mycore)[0]
        self.assertEquals(doc.date,newdate)
        self.assertEquals(doc.docname,'newfilename')

        #ANOTHER UDPATE METHOD
        
        newdate=solrJson.timestringGMT(solrJson.datetime.now()+solrJson.timedelta(days=1))
        changes=[]
        
        changes.append(('datesourcefield','date',newdate))
        json2post=updateSolr.makejson(solrid,changes,mycore)
        
        response,updatestatus=updateSolr.post_jsonupdate(json2post,mycore)

        doc=solrJson.getmeta(solrid,mycore)[0]
        self.assertEquals(doc.date,newdate)


   
    def test_change_dupfiles(self):
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes_and_dups'))
        mycore=self.mycore
        
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

    def test_updatefiledata(self):
        #make non-existent collection
        collection=Collection(path='some/path/somewhere',core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collection.save()
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes_and_dups'))
        
        newfile=File(collection=collection)
        changes.updatefiledata(newfile,testchanges_path,makehash=True)
        self.assertTrue(newfile.is_folder)
        self.assertEquals(newfile.hash_filename, file_utils.pathHash(testchanges_path))
        
    def test_extract_folder(self):
        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/emptyfolders'))
        collection=Collection(path=testfolders_path,core=self.sampleindex,indexedFlag=False,source=self.testsource)
        collection.save()
        mycore=solrJson.SolrCore('tests_only')
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        folder_solr_id=file_utils.pathHash(os.path.join(testfolders_path,'folder1'))
        updated_doc=indexSolr.check_hash_in_solrdata(folder_solr_id,mycore)
        
        self.assertEquals(updated_doc.docname,'Folder: folder1')
        self.assertEquals(updated_doc.data['docpath'],['emptyfolders/folder1'])
        self.assertEquals(updated_doc.data['sb_parentpath_hash'], '50b1c5e4bb7678653bf119e2da8a7a30')
#class ICIJExtractTest(ExtractTest):
#    def use_icij_extract(self):
#        return True


class DocumentsTest(IndexTester):
    """ Tests for documents module """
    def setUp(self):
        self.makebase()
        

    def test_getcores(self):
        """test get cores"""
        self.page.getcores(self.admin_user)
        self.assertEqual(self.page.coreID,1)
        self.assertEqual(self.page.cores[1].name,'tests_only')
       
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
        self.assertEqual(len(ac),3)
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

class UpdatingTests(IndexTester):
    """tests for updateSolr module"""
    def setUp(self):
       self.makebase()
    
    def test_updators(self):
       mycore=self.mycore
       o=updateSolr.Updater(mycore)
       self.assertIsInstance(o,updateSolr.Updater)

       o=updateSolr.UpdateField(mycore)
       
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
       
class FileUtilsTest(IndexTester):
    """test various fileutils"""
    def setUp(self):
        self.makebase()
        
	      
    def test_model_index(self):
        self.assertEquals(file_utils.model_index('somepath',[self.collectiondups]),(None,None))
        
    
    def test_filespecs(self):
        specs=file_utils.filespecs(self.testdups_path)
        filepath=os.path.join(self.testdups_path,'dup_in_folder/HilaryEmailC05793347 copy.pdf')
        spec=specs[filepath]
        self.assertEquals(spec.length,118916)
        self.assertTrue(spec.exists)
        self.assertEquals(spec.name,'HilaryEmailC05793347 copy.pdf')
        self.assertEquals(spec.ext,'.pdf')
 

class ChangeApiTests(TestCase):
    """test Api for returning user changes"""
    #
    
    def setUp(self):

        #CONTROL LOGGING IN TESTS
        logging.disable(logging.CRITICAL)

        self.password=PASSWORD
        self.username='myuser'
        self.my_email='myemail@test.com'
        self.admin_user=make_admin_or_login(self)
        #login as admin
        self.client.login(username=self.username, password=self.password)

         
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


