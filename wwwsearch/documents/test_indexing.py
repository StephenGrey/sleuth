# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db.models.query import QuerySet
from django.urls import reverse
from documents import documentpage,solrcursor,updateSolr,api,indexSolr,file_utils,changes,check_pdf,time_utils, views as views_docs, index_check, correct_paths
from documents.indexSolr import BadParameters, ExtractFileMeta
from documents.management.commands import setup
from documents.management.commands.setup import make_admin_or_login
from documents.models import  Index, Collection, Source, UserEdit,File
from ownsearch.solrJson import SolrResult,SolrCore
from ownsearch import pages,solrJson
from ownsearch import views as views_search
from django.test.client import Client
import logging,re,requests,getpass,os,shutil,json,datetime
from django.core import serializers
from django.conf import settings
from pathlib import Path

## store any password to login later
PASSWORD = 'mypassword' 
MANUAL=False




class IndexTester(TestCase):
    def makebase(self):
        """make framework for tests"""
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
        samplecollection,created=Collection.objects.get_or_create(path=os.path.join('some','path','somewhere'),core=self.sampleindex,live_update=False,source=self.testsource)
        self.sample_collection=samplecollection


        anothercollection=Collection.objects.get_or_create(path=os.path.join('some','different','path','somewhere'),core=self.sampleindex,source=self.testsource,live_update=False)
#        anothercollection.save()
        
        #DUPS
        self.testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','dups'))

        collectiondups=Collection(path=self.testdups_path,core=self.sampleindex,source=self.testsource,live_update=False)
        collectiondups.save()
        self.collectiondups=collectiondups
        self.docstore=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs'))
        
        # Establish an indexing page
        self.page=documentpage.CollectionPage(docstore=self.docstore)

        self.mycore=solrcursor.solrJson.SolrCore('tests_only')
        index_check.BASEDIR=self.docstore
        #OVERRIDE MAXISZE FROM USER CONFIGS
        indexSolr.MAXSIZE=10*(1024**2)
        

#        self.testdups_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/dups'))

class ExtractTest(IndexTester):
    """test extract documents to Solr"""
    def setUp(self):
        self.makebase()
        self.icij_extract=self.use_icij_extract()

    def use_icij_extract(self):
        return False
        
    def extract_document(self,_id,_relpath):
        updateSolr.delete(_id,self.mycore)
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))

        #first a test run, then a full extract into index        
        self.assertTrue(os.path.exists(path))
        print(path)
#        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=True)
        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        self.assertTrue(extractor.result)
        extractor.post_process()
        return extractor


class ExtractorTest(ExtractTest):
    "test extractor object"""
    def test_Extractor(self):
        """simple extract of a collection"""
        mycore=self.mycore
        
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(mycore)
        self.assertTrue(status)
        
        #make non-existent collection
        collection=Collection(path=os.path.join('some','path','somewhere'),core=self.sampleindex,source=self.testsource,live_update=False)
        collection.save()
        ext=indexSolr.Extractor(collection,mycore,useICIJ=self.icij_extract)
        #NOTHING HAPPENS ON EMPTY FILELIST
        
                
        #NOW SCAN THE COLLECTION
        scanner=updateSolr.scandocs(collection)
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],['', '', '', '', ''])
        collection.save()
        
        
        #SCAN THE DUPS COLLECTION
        collectiondups=Collection.objects.get(path=self.testdups_path)
        
        #print(self.testdups_path)
        #NOW SCAN THE COLLECTION
        scanner=updateSolr.scandocs(collectiondups)        
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],[4, 0, 0, 0, 0])
        
        #print(File.objects.filter(collection=collectiondups))
        
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        self.assertEquals((4,0,0),(ext.counter,ext.skipped,ext.failed))
       
        storedpaths=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore).data['docpath']
        calcpaths=[os.path.join('dups','HilaryEmailC05793347.pdf'), os.path.join('dups','HilaryEmailC05793347 copy.pdf'),os.path.join( 'dups','dup_in_folder','HilaryEmailC05793347 copy.pdf')]
        
        #print(storedpaths)
        #print(calcpaths)
        
        for path in calcpaths:
            storedpaths.remove(path)
        self.assertEquals(storedpaths,[])
        
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
        self.mycore.commit()
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        updatedlist=updated_doc.data['docpath']
        expectedlist=[os.path.join('dups','HilaryEmailC05793347.pdf'), os.path.join('dups','HilaryEmailC05793347 copy.pdf'), os.path.join('dups','dup_in_folder','HilaryEmailC05793347 copy.pdf')]
        
#        print(expectedlist)
#        print(updatedlist)
        for path in expectedlist:
            updatedlist.remove(path)
        self.assertEquals(updatedlist,[])
        
         
        updatedparentpath=updated_doc.data[mycore.parenthashfield]
        #print (updatedparentpath)
        for path in ['b7d16465ed3947cc5849328cf182130e', 'b7d16465ed3947cc5849328cf182130e', 'efc6d83504d6183aab785ac3d3576cd1']:
            updatedparentpath.remove(path)
        self.assertEquals(updatedparentpath,[])
        

        #MOVE OUT OF COLLECTION
        os.rename(os.path.join(origindir,filename),os.path.join(tempdir,filename))
        
        scanner=updateSolr.scandocs(collectiondups,docstore=self.docstore)
        self.assertEquals([scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count],[0, 1, 0, 3, 0])      
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        self.assertEquals(updated_doc.data['docpath'],[os.path.join('dups','HilaryEmailC05793347 copy.pdf'), os.path.join('dups','dup_in_folder','HilaryEmailC05793347 copy.pdf')])
        self.assertEquals(updated_doc.data[mycore.parenthashfield],['b7d16465ed3947cc5849328cf182130e', 'efc6d83504d6183aab785ac3d3576cd1'])
        
        #MOVE BACK AGAIN
        os.rename(os.path.join(tempdir,filename),os.path.join(origindir,filename))        
        scanfiles=updateSolr.scandocs(collectiondups,docstore=self.docstore)        
        ext=indexSolr.Extractor(collectiondups,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        
        updated_doc=indexSolr.check_hash_in_solrdata("6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809",mycore)
        self.assertEquals(updated_doc.data['docpath'],
        [os.path.join('dups','HilaryEmailC05793347 copy.pdf'), os.path.join('dups','dup_in_folder','HilaryEmailC05793347 copy.pdf'), os.path.join('dups','HilaryEmailC05793347.pdf')])

        self.assertEquals(updated_doc.data[mycore.parenthashfield],["b7d16465ed3947cc5849328cf182130e", "efc6d83504d6183aab785ac3d3576cd1", "b7d16465ed3947cc5849328cf182130e"])


    def test_change_dupfiles(self):
        """change duplicate files """
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','changes_and_dups'))
        mycore=self.mycore
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)

        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,source=self.testsource,live_update=False)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)

        
        change_file(relpath=os.path.join('changes_and_dups','changingfile.txt'))
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        change_file(relpath=os.path.join('changes_and_dups','changingfile.txt'))

    def test_changefiles(self):
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/changes'))
        mycore=solrJson.SolrCore('tests_only')
        
        
        #start with first version
        shutil.copy2(os.path.join(testchanges_path,'1changingfile.txt'),os.path.join(testchanges_path,'changingfile.txt'))
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)


        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,source=self.testsource,live_update=False)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        

        updated_doc=indexSolr.check_hash_in_solrdata("4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0",mycore) #hash of first version
        #print(updated_doc.__dict__)
        updated_list=updated_doc.data['docpath']
        for path in [os.path.join('changes','changingfile.txt'),os.path.join('changes','1changingfile.txt')]:
            updated_list.remove(path)
        self.assertEquals(updated_list,[])

        self.assertEquals(indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore),None) #second hash
        
        change_file()
        
        #NOW SCAN THE COLLECTION
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract,forceretry=True)
#
#        #change_file()
        self.assertEquals(indexSolr.check_hash_in_solrdata("d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67",mycore).data['docpath'],[os.path.join('changes','changingfile.txt')])



    def test_change_meta(self):
        """change file meta and update"""	
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','changes'))
        mycore=solrJson.SolrCore('tests_only')
        #start with first version
        shutil.copy2(os.path.join(testchanges_path,'1changingfile.txt'),os.path.join(testchanges_path,'changingfile.txt'))
        
        #delete relevant files
        updateSolr.delete('d5cf9b334b0e479d2a070f9c239b154bf1a894d14f2547b3c894f95e6b0dad67',mycore)
        updateSolr.delete('4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0',mycore)


        collection,res=Collection.objects.get_or_create(path=testchanges_path,core=self.sampleindex,source=self.testsource,live_update=False)
        self.assertTrue(res)

        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        solrid="4be826ace55d600ee70d7a4335ca26abc1b3e22dee62935c210f2c80ea5ba0d0"

        docs=solrJson.getmeta(solrid,mycore)
        self.assertTrue(docs[0].docname == 'changingfile.txt' or '1changingfile.txt')
        #self.assertEquals(docs[0].date,'')
        
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

    def test_extract_folder(self):
        """extract a folder reference"""
        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','emptyfolders'))
        collection=Collection(path=testfolders_path,core=self.sampleindex,source=self.testsource,live_update=False)
        collection.save()
        mycore=solrJson.SolrCore('tests_only')
        scanfiles=updateSolr.scandocs(collection,docstore=self.docstore) 
        ext=indexSolr.Extractor(collection,mycore,docstore=self.docstore,useICIJ=self.icij_extract)
        
        folder_solr_id=file_utils.pathHash(os.path.join(testfolders_path,'folder1'))
        updated_doc=indexSolr.check_hash_in_solrdata(folder_solr_id,mycore)
        
        self.assertEquals(updated_doc.docname,'Folder: folder1')
        self.assertEquals(updated_doc.data['docpath'],[os.path.join('emptyfolders','folder1')])
        self.assertEquals(updated_doc.data['sb_parentpath_hash'], '50b1c5e4bb7678653bf119e2da8a7a30')

    def test_index_metaonly(self):
        """index meta only"""
        _id='e46df5747edd25174f7d61aa2d333f81e8435029faf1ebcebc5a51e1d535ab8b'
        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','pdfs','4meta'))
        mycore=self.mycore
        updateSolr.delete(_id,self.mycore)
        for filename in os.listdir(testfolders_path):
            path=os.path.join(testfolders_path,filename)
            #print(path)
            _newfile=changes.newfile(path,self.sample_collection)
            existing_doc=indexSolr.check_file_in_solrdata(_newfile,self.mycore) #searches by hashcontents, not solrid
            if existing_doc:
                indexSolr.UpdateMeta(mycore,_newfile,existing_doc,docstore=self.docstore)
            else:
                ext=indexSolr.ExtractFileMeta(path,mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=True,check=True)
                ext.post_process(indexed=False)
        #check results
        doc=solrJson.getmeta(_id,self.mycore)[0]
        #print(doc.data)
        self.assertTrue(doc.data.get('docpath')==['pdfs/4meta/CIA_doc.pdf.mov', 'pdfs/4meta/CIA_doc copy.pdf.mov']or   doc.data.get('docpath')==['pdfs\\4meta\\CIA_doc copy.pdf.mov', 'pdfs\\4meta\\CIA_doc.pdf.mov'])

    def test_index_not_extract(self):
        """index meta only"""
        _id='e46df5747edd25174f7d61aa2d333f81e8435029faf1ebcebc5a51e1d535ab8b'
        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','pdfs','4meta'))
        mycore=self.mycore
        updateSolr.delete(_id,self.mycore)
        
        for filename in os.listdir(testfolders_path):
            path=os.path.join(testfolders_path,filename)
            _newfile=changes.newfile(path,self.sample_collection)
            self.assertFalse(_newfile.indexMetaOnly)
            updater=indexSolr.UpdateMeta(mycore,_newfile,None,docstore=self.docstore,existing=False) #an instance of Extractor
            updater.job=None
            updater.useICIJ=False
            updater.ocr=False
            updater.counter=1
            updater.skipped=0
            updater.skippedlist=[]
            updater.collection=self.sample_collection
            
            skip=updater.skip_extract(_newfile)
            self.assertEquals(updater.skipped,1)
            self.assertTrue(skip)
            
            entity=indexSolr.Entity(_file=_newfile)
            updater.extract_entity(entity)
            
            #print(_newfile.__dict__)
            self.assertTrue(_newfile.indexMetaOnly)
            
            
    def test_meta_only_date(self):
        """index meta only date"""
        _id='e46df5747edd25174f7d61aa2d333f81e8435029faf1ebcebc5a51e1d535ab8b'
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','pdfs','4meta_date','2019-12-01 doc.mov'))
        self.assertTrue(os.path.exists(path))
        mycore=self.mycore
        updateSolr.delete(_id,self.mycore)
        
        
        ext=ExtractFileMeta(path,self.mycore,hash_contents=_id,sourcetext='',docstore=self.docstore,meta_only=True,check=True)
        result=ext.post_process(indexed=False)
        
        doc=solrJson.getmeta(_id,self.mycore)
        
        self.assertTrue(doc[0].data.get('sb_meta_only'))
    
    def test_fail_file(self):
        pass
#        #THIS FILE IS NO LONGER FAILING! 
#        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','fails2'))
#        mycore=self.mycore
#        _id='d76380878f1eed6cc07f18f547e9fe7848861fe0e204e3d7b7b4519cd9abec09'
#        updateSolr.delete(_id,self.mycore)
#        
#        for filename in os.listdir(testfolders_path):
#            path=os.path.join(testfolders_path,filename)
#            _newfile=changes.newfile(path,self.sample_collection)
#            ext=indexSolr.ExtractSingleFile(_newfile,forceretry=False,useICIJ=False,ocr=True,docstore=self.docstore,job=None)
#            #print(ext.counter,ext.skipped,ext.failed)
#            if ext.failed==1:
#                self.assertEquals(_newfile.indexFails,1)
#            
#        #if the extract fails, confirm it extracts metaonly
#        doc=solrJson.getmeta(_id,self.mycore)
#        #print(doc[0].data)
#        #print(self.mycore.meta_only)
#        meta_result=doc[0].data.get(self.mycore.meta_only)
#        self.assertTrue(meta_result)
        
    def test_postcontent(self):
        _id='d76380878f1eed6cc07f18f547e9fe7848861fe0e204e3d7b7b4519cd9abec09'
        testfolders_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','fails2'))
        mycore=self.mycore
        updateSolr.delete(_id,self.mycore)
        filename="65865.TIF"
        filepath=os.path.join(testfolders_path,filename)
        
        ext=indexSolr.ExtractFileMeta(filepath,self.mycore,hash_contents=_id,sourcetext='',docstore=self.docstore,meta_only=True,check=True)
        meta_result=ext.post_process(indexed=False)
        doc=solrJson.getcontents(_id,self.mycore)
        self.assertEquals('Metadata only: No content extracted from file',doc[0].data['rawtext'])
        #print(doc[0].data)
        
class ICIJFolderTest(IndexTester):
    def setUp(self):
        self.makebase()
        _relpath="mixed_folder"
        self._path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
        self.collection,created=Collection.objects.get_or_create(path=self._path,core=self.sampleindex,source=self.testsource,live_update=False)
        self.assertTrue(created)
        
    def test_folder(self):
        """extract an entire folder with ICIJ extract tool"""
        
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(self.mycore)
        self.assertTrue(status)
        
        #make a collection
        scanner=updateSolr.scandocs(self.collection,job="jobid")
        
        #check if files already indexed
        counter,skipped,failed=index_check.index_check(self.collection,self.mycore)
        #print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
        self.assertEquals(skipped,7)  #nothing found in initial scan
        
        #EXTRACT A FOLDER

        self.assertTrue(os.path.exists(self._path))
        
        result=indexSolr.solrICIJ.ICIJExtractor(self._path,self.mycore,ocr=False).result
        self.assertTrue(result)

        #now fix meta
        pp=indexSolr.Collection_Post_Processor(self.collection,self.mycore,docstore=self.docstore,_test=False,job=None)
        
        doc=solrJson.getmeta('6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809',self.mycore)[0]
        stored_paths=[Path(doc.data.get('docpath')[0]),Path(doc.data.get('docpath')[1])]
        
        self.assertTrue(stored_paths==[ Path("mixed_folder/HilaryEmailC05793347.pdf"),Path("mixed_folder/HilaryEmailC05793347 copy.pdf")]or stored_paths==[Path("mixed_folder/HilaryEmailC05793347 copy.pdf"),Path("mixed_folder/HilaryEmailC05793347.pdf")])
        self.assertTrue(doc.docname=='HilaryEmailC05793347.pdf' or doc.docname=="HilaryEmailC05793347 copy.pdf")
        
#        #NOW RECOGNISE FOLDER IN THE DATA - NOT NECESSARY
#        counter,skipped,failed=.index_check(self.collection,self.mycore)
#        print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
#        self.assertEquals(counter,10)
#        
#        #change absolute paths to relative paths - WORKING NOT NECESSARY
#        self.assertTrue(correct_paths.check_solrpaths(self.mycore,self.collection,docstore=self.docstore))
        
        childdoc=solrJson.getmeta('c032fe1fbef76624f1ad09e46feb4c04ec4e37a27a6a3487abc3ef73c702d3f9',self.mycore)[0]
        self.assertEquals(childdoc.docname,"image1.jpg")
        
        
    def test_command_extract(self):
        """test extract collection from the command line"""

        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(self.mycore)
        self.assertTrue(status)
        
        #make a collection
        scanner=updateSolr.scandocs(self.collection,job="jobid")
        
        #check if files already indexed
        counter,skipped,failed=index_check.index_check(self.collection,self.mycore)
        #print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
        self.assertEquals(skipped,7)  #nothing found in initial scan

        
        #run through the extractor
        tester=indexSolr.solrICIJ.ICIJ_Tester()
        tester.mycore=self.mycore
        tester.path=self._path
        tester.ocr=False
        
        tester.get_args()
        tester.run_command(tester.args)
        
        self.assertTrue(tester.log_parser.success)
        
        #now commit it
        tester.commit_args()
        tester.run_command(tester.args)
        
#        indexSolr.Collection_Post_Processor(self.collection,self.mycore,docstore=self.docstore,_test=False,job="")
        index_check.BASEDIR=self.docstore
        counter,skipped,failed=index_check.index_check(self.collection,self.mycore)
        #print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
        childdoc=solrJson.getmeta('c032fe1fbef76624f1ad09e46feb4c04ec4e37a27a6a3487abc3ef73c702d3f9',self.mycore)[0]
        self.assertEquals(childdoc.docname,"image1.jpg")

    def test_fixmeta_command(self):
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(self.mycore)
        self.assertTrue(status)
        
        #make a collection
        scanner=updateSolr.scandocs(self.collection,job="jobid")
        
        #check if files already indexed
        counter,skipped,failed=index_check.index_check(self.collection,self.mycore)
        #print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
        self.assertEquals(skipped,7)  #nothing found in initial scan

        
        #run through the extractor
        tester=indexSolr.solrICIJ.ICIJ_Tester()
        tester.mycore=self.mycore
        tester.path=self._path
        tester.ocr=False
        
        tester.get_args()
        tester.run_command(tester.args)
        
        self.assertTrue(tester.log_parser.success)
        
        #now commit it
        tester.commit_args()
        tester.run_command(tester.args)
        
        args = ['tests_only']
        opts = {'docstore':self.docstore,'collectionID':self.collection.id}
        call_command('fix_meta', *args, **opts)

        childdoc=solrJson.getmeta('c032fe1fbef76624f1ad09e46feb4c04ec4e37a27a6a3487abc3ef73c702d3f9',self.mycore)[0]
        self.assertEquals(childdoc.docname,"image1.jpg")
        
        
    def test_indexcheck(self):
        scanner=updateSolr.scandocs(self.collection,job="jobid")
        counter,skipped,failed=index_check.index_check(self.collection,self.mycore)
        #print(f'counter:{counter},skipped: {skipped}, failed: {failed}')
        self.assertEquals(counter,7)
        self.assertEquals(skipped,0)
        
    def test_folder_command(self):
        
        #ERASE EVERYTHING FROM TESTS_ONLY 
        res,status=updateSolr.delete_all(self.mycore)
        self.assertTrue(status)
        
        self.assertRaises(BadParameters, indexSolr.ExtractFolder,'wrongname',self._path)
        self.assertRaises(BadParameters,indexSolr.ExtractFolder,'tests_only','randompath')
        
               
        args = ['tests_only']
        opts = {'docstore':self.docstore,'collectionID':self.collection.id}
        call_command('extract_folder', *args, **opts)
        
        
        doc=solrJson.getmeta('6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809',self.mycore)[0]
        #self.assertEquals([Path(doc.data.get('docpath')[0]),Path(doc.data.get('docpath')[0])],[Path("mixed_folder/HilaryEmailC05793347.pdf"),Path("mixed_folder/HilaryEmailC05793347 copy.pdf")])
        #print(doc.__dict__)
        self.assertTrue(doc.docname=='HilaryEmailC05793347.pdf' or doc.docname=='HilaryEmailC05793347 copy.pdf')
        childdoc=solrJson.getmeta('c032fe1fbef76624f1ad09e46feb4c04ec4e37a27a6a3487abc3ef73c702d3f9',self.mycore)[0]
        self.assertEquals(childdoc.docname,"image1.jpg")
        


        
        
class ICIJExtractTest(ExtractorTest):
    """ run same extractor object tests through ICIJ extract tool"""
    def use_icij_extract(self):
        return True
        
    
    def test_ICIJdoc(self):
        """check direct extract via ICIJ extract tool"""
        _id="fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74"
        _relpath="pdfs/ocr_d/C05769606.pdf"
        
        updateSolr.delete(_id,self.mycore)
        
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
        result=indexSolr.solrICIJ.ICIJExtractor(path,self.mycore,ocr=False).result
        self.assertTrue(result)
        
        ext=indexSolr.ICIJ_Post_Processor(path,self.mycore,hash_contents=_id, sourcetext='some text',docstore=os.path.join(os.path.dirname(__file__), '../tests/testdocs'),test=False)
        
        doc=indexSolr.check_hash_in_solrdata(_id,self.mycore)

        self.assertEquals(doc.data.get(self.mycore.sourcefield),'some text')

        self.assertEquals(Path(doc.data.get('docpath')[0]), Path(_relpath))
        self.assertEquals(doc.data.get(self.mycore.parenthashfield),'ca966a7642c7791b99ab661feae3ebb7')
        self.assertEquals(doc.docname,'C05769606.pdf')

    
    def test_no_commit(self):
        _id2='28b00a45819a9307fa1f1a34fc729efb6d7e3378591e9d6b99f210b0b989f29c'
        
        #with commit
        updateSolr.delete(_id2,self.mycore)        
        updateSolr.updatetags(_id2,self.mycore)
        doc=indexSolr.check_hash_in_solrdata(_id2,self.mycore)
        
        #print(doc.__dict__)
        self.assertTrue(doc.data.get('sb_usertags1')==['test', 'anothertest'])
        
        #no commit
        updateSolr.delete(_id2,self.mycore)        
        updateSolr.updatetags(_id2,self.mycore,check=False)
        doc=indexSolr.check_hash_in_solrdata(_id2,self.mycore)
        
        self.assertFalse(doc)
        
        #now commit
        self.mycore.commit()
        doc=indexSolr.check_hash_in_solrdata(_id2,self.mycore)        
        self.assertTrue(doc.data.get('sb_usertags1')==['test', 'anothertest'])

        
#        if doc:
#            print(doc.__dict__)        
#        self.assertFalse(doc.data.get('sb_usertags1')==['test', 'anothertest'])

        
    
    def test_childprocess(self):
#        #ERASE EVERYTHING FROM TESTS_ONLY 
#        res,status=updateSolr.delete_all(self.mycore)
#        self.assertTrue(status)
        
        
        _id2='28b00a45819a9307fa1f1a34fc729efb6d7e3378591e9d6b99f210b0b989f29c'
        updateSolr.delete(_id2,self.mycore)
        _id='c032fe1fbef76624f1ad09e46feb4c04ec4e37a27a6a3487abc3ef73c702d3f9'
        updateSolr.delete(_id,self.mycore)
        
        _relpath="mixed_folder/2013-03-10 Labour claims largest majority ever in post.docx"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))

        _newfile=changes.newfile(path,self.sample_collection)
        #print(_newfile)
        ext=indexSolr.ExtractSingleFile(_newfile,forceretry=False,useICIJ=True,ocr=True,docstore=self.docstore,job=None,check=False)
            #print(ext.counter,ext.skipped,ext.failed)
        self.mycore.commit()
        doc=indexSolr.check_hash_in_solrdata(_id2,self.mycore)        
        #print(doc.__dict__)

        self.assertEquals(doc.data.get('sb_source'),'Test source')
        #running it a second time 
        ch=indexSolr.ChildProcessor(path,self.mycore,docstore=self.docstore)
        ch.process_children()
    

    def test_ICIJfail(self):
        _id="fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74"
        _relpath="fails/__init__.py"
        
        updateSolr.delete(_id,self.mycore)
        
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
        ext=indexSolr.solrICIJ.ICIJExtractor(path,self.mycore,ocr=False)
        self.assertFalse(ext.result)
        self.assertEquals(ext.error_message,'ICIJ ext: parse failure')

class ExtractFileTest(ExtractTest):
    """extract tests without extractor object"""
    
    def test_indexfile(self):
        #dummy run
        mycore=self.mycore
        indexSolr.extract_test(mycore=mycore,test=True,docstore=self.docstore)
        
        #livetest on test index
        indexSolr.extract_test(mycore=mycore,test=False,docstore=self.docstore)
    
    
    def test_catch_nofile(self):
        _id="fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74"
        #_path="pdfs/ocr_d/C05769606.pdf"
        _path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/pdfs/ocr_d/C05769606.pdf'))
        
        self.assertTrue(os.path.exists(_path))
        
        updateSolr.delete(_id,self.mycore)
        url="http://solr:8983/solr/tests_only/update/extract?commit=true&wt=json&literal.extract_id=fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74&literal.sb_pathhash=284be69651f8dfc66e2b86d2355c4b85&extractOnly=true"
        #res=solrJson.resPostfile(url,_path,timeout=1)
        
        #e=indexSolr.ExtractFileMeta(_path,self.mycore)
        #print(e)
        
        result=indexSolr.extract(_path,_id,self.mycore,timeout=1,docstore=self.docstore,test=False,sourcetext="random source",ocr=True)
        
        result=solrJson.getfield(_id,"sb_pathhash",self.mycore,resultfield='')
        print(result)
        
        result=solrJson.getfield(_id,self.mycore.datesourcefield2,self.mycore,resultfield='')
        #print(result)
        
        
    
    def test_extractfile(self):
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/docx/2018-01-23 Sale of Maltese passports nets Malta over €277m in one year.docx'))
        
        _id="fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74"
        _path="pdfs/ocr_d/C05769606.pdf"
        extractor=self.extract_document(_id,_path)
        
        #TEMP
        #updateSolr.delete(_id,self.mycore)
    
    def test_extractfile_no_ocr(self):
        """index a single file with no OCR"""
        
        _id="fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74"
        _path="pdfs/ocr_d/C05769606.pdf"
        extractor=self.extract_document(_id,_path)
        
        updateSolr.delete(_id,self.mycore)
    
    
    def test_morefilenames(self):
        """ test with % character """

        folder="../tests/testdocs/longnames/"
        filename="percent%filename.pdf"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))
        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        extractor.post_process()
        self.assertTrue(extractor.result)
        self.assertTrue(extractor.post_result)
    
    def test_opendoc(self):
        """extract odt format """

        folder="../tests/testdocs/odt/"
        filename="opendoc.odt"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))
        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        self.assertTrue(extractor.result)
        if extractor.result:
            extractor.post_process()
            self.assertTrue(extractor.post_result)        
    
    def test_filenames(self):
        """index non-ascii filenames"""
        folder="../tests/testdocs/longnames/"
        filename="emdashfilename–.pdf"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))
        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        extractor.post_process()
        self.assertTrue(extractor.result)
        self.assertTrue(extractor.post_result)

        filename="chinese漢字filename.pdf"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))
        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        extractor.post_process()
        self.assertTrue(extractor.result)
        self.assertTrue(extractor.post_result)
        
        #ASCII FILENAME BUT CHINESE CHARACTERS IN SOLR FIELDS
        filename="normalfilename.pdf"
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))

        args="commit=true&wt=json&literal.extract_id=SOMEID8bc9&literal.tika_metadata_resourcename=chinese漢字.pdf&literal.extract_paths=somepathwithchinese漢字&literal.sb_pathhash=2be738d4a6acef35febfa0d9ef5e6f65&literal.sb_parentpath_hash=710ea88f1e278e3795b76368927c1d5c&extractOnly=true"
        
        result,elapsed=indexSolr.postSolr(args,path,self.mycore,timeout=1)
        self.assertTrue(result)

        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        extractor.post_process()
        filename="normalfilename.pdf"
#        
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), folder,filename))
#        
        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
        extractor.post_process()

        self.assertTrue(extractor.result)
        self.assertTrue(extractor.post_result)
        

    def test_slugify(self):
        """check slugifying non-ascii filenames"""
        filename="chinese漢字filename.pdf"
        clean=file_utils.slugify(filename)
        self.assertEquals(clean,'chinesefilename.pdf')
        
        filename="漢字漢字漢字漢字.pdf"
        clean=file_utils.slugify(filename)
        self.assertEquals(clean,'filename.pdf')
        
    def test_update_parent_hashes(self):
        #index sample PDF
        _id="b0e08515ec0c602dbc1a0997c7f37d715cfda1b08080c1a96e42cde0b041e8c1"
        mycore=solrJson.SolrCore('tests_only')

        updateSolr.delete(_id,self.mycore)
        
        indexSolr.extract_test(mycore=mycore,test=False,docstore=self.docstore)
        
        
        existing_parenthash=solrJson.getfield(_id,mycore.parenthashfield,mycore)
        self.assertEquals(existing_parenthash,None)

        result=updateSolr.updatetags(_id,mycore,field_to_update=mycore.parenthashfield,value=['8bc944dbd052ef51652e70a5104492e3','somerandomhash'])

        new_parenthash=solrJson.getfield(_id,mycore.parenthashfield,mycore)
        self.assertEquals(new_parenthash,['8bc944dbd052ef51652e70a5104492e3', 'somerandomhash'])
        
        
        value=['8bc944dbd052ef51652e70a5104492e3']
        result=updateSolr.updatetags(_id,mycore,field_to_update=mycore.parenthashfield,value=value)

        new_parenthash=solrJson.getfield(_id,mycore.parenthashfield,mycore)
        self.assertEquals(new_parenthash,'8bc944dbd052ef51652e70a5104492e3')
        
        #make changes to the solr index
        changes=[(mycore.parenthashfield,mycore.parenthashfield,value)]
        #print(changes)
        json2post=updateSolr.makejson(_id,changes,mycore)
        response,updatestatus=updateSolr.post_jsonupdate(json2post,mycore)
        #print(response,updatestatus)
        self.assertTrue(updatestatus)
        result= updateSolr.checkupdate(_id,changes,mycore)
        self.assertTrue(result)
        
        
    
    def test_specs(self):
        pp=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs/docx/2018-01-23 Sale of Maltese passports nets Malta over €277m in one year.docx'))
        specs=file_utils.FileSpecs(pp)
        self.assertEquals(specs.length,154209)
#        print(time_utils.timestamp2aware(specs.last_modified))
        self.assertEquals(specs.date_from_path.day,23)
        self.assertEquals(specs.date_from_path.month,1)
        
        newfile=File(collection=self.sample_collection)
        changes.updatefiledata(newfile,pp,makehash=True)
        
        self.assertEquals(changes.time_utils.timeaware(specs.date_from_path),newfile.content_date)
        
        #print(Collection.objects.all())
        
    def test_extract_withdate(self):
#        #start fresh
        _id='9ea57f8bd36c23f2b8316b621fedef1182b8f47c23fc4220ed0a44f67c52998b'
        _relpath='docx/2018-01-23 Sale of Maltese passports nets Malta over €277m in one year.docx'
        ##
        extractor=self.extract_document(_id,_relpath)
        self.assertEquals(solrJson.getmeta(_id,self.mycore)[0].datetext,'Jan 23, 2018')
        updateSolr.delete(_id,self.mycore)
#        updateSolr.delete("fed766bc65fd9415917f0ded164a435011aab5247b2ee393929ec92bd96ffe74",self.mycore)
    def test_extract_withdate2(self):
#        #start fresh
        _id='ffbb5c2510c33e980ad7a523f1e9c90ca6d968066f61fd04a253182d09da76d3'
        _relpath='docx/2013-03-10 Labour claims largest majority ever in post.docx'
        
        extractor=self.extract_document(_id,_relpath)    

        self.assertEquals(solrJson.getmeta(_id,self.mycore)[0].datetext,'Mar 10, 2013')
        updateSolr.delete(_id,self.mycore)
#            
     
    def test_change_date(self):
        _id='ffbb5c2510c33e980ad7a523f1e9c90ca6d968066f61fd04a253182d09da76d3'
        _relpath='docx/2013-03-10 Labour claims largest majority ever in post.docx'
        extractor=self.extract_document(_id,_relpath)
        
        upd={"extract_id": _id, self.mycore.datesourcefield: {"set": "2009-04-10T00:00:00Z"}}
        data=json.dumps([upd])
        response,updatestatus=updateSolr.post_jsonupdate(data,self.mycore)
        #print(f'Response: {response}; Status: {updatestatus}')   
        self.assertEquals(solrJson.getmeta(_id,self.mycore)[0].datetext,'Apr 10, 2009')
        self.assertTrue(updatestatus)
        
        #change another way
        
        updateSolr.updatetags(_id,self.mycore,value="2039-10-10T00:00:00Z",field_to_update='datesourcefield',newfield=False,test=False)
        
        self.assertEquals(solrJson.getmeta(_id,self.mycore)[0].datetext,'Oct 10, 2039')        
        
        updateSolr.delete(_id,self.mycore)        

    def test_path_date_changed(self):
        _id='ffbb5c2510c33e980ad7a523f1e9c90ca6d968066f61fd04a253182d09da76d3'
        _relpath='docx/2013-03-10 Labour claims largest majority ever in post.docx'
        extractor=self.extract_document(_id,_relpath)
        
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        
        newfile=File(collection=self.collectiondups)
        changes.updatefiledata(newfile,extractor.path,makehash=False)
        
        newdate=time_utils.timeaware(datetime.datetime.now())
        newdatetext=time_utils.easydate(newdate)
        
        newfile.content_date=newdate
        
        updater=indexSolr.UpdateMeta(self.mycore,newfile,doc,docstore=self.docstore)
        
        self.assertEquals(solrJson.getmeta(_id,self.mycore)[0].datetext,newdatetext)    

        newfile.delete()
    
    
    def test_changesize(self):
        _id='ffbb5c2510c33e980ad7a523f1e9c90ca6d968066f61fd04a253182d09da76d3'
        _relpath='docx/2013-03-10 Labour claims largest majority ever in post.docx'
        extractor=self.extract_document(_id,_relpath)
        
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)

        
        newfile=File(collection=self.collectiondups)
        
        changes.updatefiledata(newfile,extractor.path,makehash=False)
        
        #print('now parse')
        _changes=updateSolr.parsechanges(doc,newfile,self.mycore,docstore=self.docstore)
        response,updatestatus=updateSolr.update(_id,_changes,self.mycore)

        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        #print('do again')
        newfile.filesize=999
                
        _changes=updateSolr.parsechanges(doc,newfile,self.mycore,docstore=self.docstore)
        
        #print(_changes)
        if _changes:
            response,updatestatus=updateSolr.update(_id,_changes,self.mycore)
        
    def test_tif(self):
        _relpath='tiff/sample.tiff'
        _id='9bada33daa4e4ec0d8915d5123ac0b5964c3fc7dfee11456bb48287e8d22450a'
        extractor=self.extract_document(_id,_relpath)
#        print(extractor.__dict__)
        self.assertTrue(extractor.result)
                
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        self.assertEquals(doc.date,'1998-07-29T10:30:30Z')    
    
        updateSolr.delete(_id,self.mycore)
        
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
        ext=indexSolr.solrICIJ.ICIJExtractor(path,self.mycore,ocr=False)
        
        #returns True in ICIJ extract despite bad date metadata
        self.assertTrue(ext.result)
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        self.assertEquals(doc.date,'1998-07-29T10:30:30Z')


    
    def test_email(self):
        """test email both with direct extract and ICIJ extract tool"""
        _relpath='msg/test_email.msg'
        _id='5b6fcfc9fe87b050255bb695a4616e3c7abddf282e6397fd868e03c1b0018fb0'
        updateSolr.delete(_id,self.mycore)
        
        extractor=self.extract_document(_id,_relpath)
        #print(extractor.__dict__)
        
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        #print(doc.__dict__)
        self.assertEquals(doc.data['message_to'],"'Adele Fulton'; Paul J. Brown")
        self.assertEquals(doc.data['message_from'],'Wood, Tracy')
        self.assertEquals(doc.date,'2015-07-29T17:58:40Z')
        self.assertEquals(doc.data['title'], 'Newport Adimistrative Order by Consent (AOC) Status')
        
        updateSolr.delete(_id,self.mycore)
        
        path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
        ext=indexSolr.solrICIJ.ICIJExtractor(path,self.mycore,ocr=False)
        #print(ext.__dict__)
        self.assertTrue(ext.result)

        
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
        #print(doc.__dict__)
        self.assertEquals(doc.data['message_to'],"'Adele Fulton'; Paul J. Brown")
        self.assertEquals(doc.data['message_from'],'Wood, Tracy')
        self.assertEquals(doc.data['message_raw_header_message_id'],'<B7EE98A869777C49ACF006A8AA90665C63B8A2@HZNGRANMAIL1.granite.nhroot.int>')
        self.assertEquals(doc.date,'2015-07-29T17:58:40Z')
        self.assertEquals(doc.data['title'], 'Newport Adimistrative Order by Consent (AOC) Status')
        
        


#        extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=self.docstore,test=False)
#        self.assertTrue(extractor.result)
#        extractor.post_process()
    
    
    
    def test_jpg(self):
        _id='909e8c759f760ee45c9735274e71d66d8f112e8e14387ff2e7d4af064091afe0'
        _relpath='jpg/Squirrel.jpg'
        extractor=self.extract_document(_id,_relpath)
        
        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)

        newfile=File(collection=self.collectiondups)
        newfile.solrid=_id
        changes.updatefiledata(newfile,extractor.path,makehash=True)
        
        #print(newfile.__dict__)
        
        #print('PARSE CHANGES')
        _changes=updateSolr.parsechanges(doc,newfile,self.mycore,docstore=self.docstore)
        response,updatestatus=updateSolr.update(_id,_changes,self.mycore)

        newfile.filesize=999

        doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)                
        _changes=updateSolr.parsechanges(doc,newfile,self.mycore,docstore=self.docstore)
        
        #print(_changes)
        if _changes:
            response,updatestatus=updateSolr.update(_id,_changes,self.mycore)
    


    def test_updatefiledata(self):
        #make non-existent collection
        collection=Collection(path='some/path/somewhere',core=self.sampleindex,source=self.testsource,live_update=False)
        collection.save()
        testchanges_path=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','tests','testdocs','changes_and_dups'))
        
        newfile=File(collection=collection)
        changes.updatefiledata(newfile,testchanges_path,makehash=True)
        self.assertTrue(newfile.is_folder)
        self.assertEquals(newfile.hash_filename, file_utils.pathHash(testchanges_path))
        

        

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
        #print(ac)
        
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
       o.maxcount=1
       o.process()
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
        #print(self.testdups_path)
        #print(specs)
        filepath=os.path.join(self.testdups_path,'dup_in_folder','HilaryEmailC05793347 copy.pdf')
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
        views_search.update_user_edits(self.page.doc_id,self.page.mycore,keyclean,'admin')
        
        self.page=pages.ContentPage(doc_id='someid2',searchterm='another searchterm')
        self.page.mycore=SolrCore('some_solr_index',test=True)
        keyclean=[re.sub(r'[^\w, ]','',item) for item in ['Hilary Clinton','politics','USA']]
        views_search.update_user_edits(self.page.doc_id,self.page.mycore,keyclean,'user1')
        
        
        
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


class TestPdfChecks(TestCase):

    def setUp(self):
        self.docstore=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs'))
        
    def test_pdf(self):
        filepath=os.path.join(self.docstore,'pdfs','ocr_d','C05769606.pdf')
        self.assertTrue(check_pdf.main(filepath))
        
        filepath=os.path.join(self.docstore,'pdfs','not_ocr_d','DOC_0005517469.pdf')
        self.assertFalse(check_pdf.main(filepath))
        
    def test_pdfdirectory(self):
        filepath=os.path.join(self.docstore,'pdfs','ocr_d')
        check_pdf.crawl(filepath)
        
        filepath=os.path.join(self.docstore,'pdfs','not_ocr_d')
        check_pdf.crawl(filepath)
 

        

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
            #print('setting second version of changed files')
            f.write(text2)
            f.truncate()
        else:
            #print('setting first version of changed filed')
            f.write(text1)
            
            f.truncate()


