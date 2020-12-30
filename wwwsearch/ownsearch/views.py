# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from builtins import str
from .forms import SearchForm,TagForm
from documents.models import File,Collection,Index,UserEdit
from documents.file_utils import slugify,make_download,make_file,DoesNotExist
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect,Http404,JsonResponse
from django.urls import reverse
from django.db.models.base import ObjectDoesNotExist
from django.contrib.staticfiles.templatetags.staticfiles import static #returns static url
from django.contrib.staticfiles import finders #locates static file
from django.conf import settings #to access settings constants
from documents.management.commands import setup
import re, os, logging, unicodedata, json
from . import markup
from watcher import watch_dispatch

try:
    from urllib.parse import quote_plus #python3
except ImportError:
    from urllib import quote_plus #python2
from documents import solrcursor,updateSolr
from datetime import datetime
from configs import config
from . import pages,solrJson,authorise


log = logging.getLogger('ownsearch.views')
DOCBASEPATH=config['Models']['collectionbasepath']
RESULTS_PER_PAGE=10
MIMETYPES_THAT_EMBED=['application/pdf','image/jpeg','image/svg+xml','image/x-icon','image/bmp','image/png','image/tiff','image/gif',]
#,'application/vnd.openxmlformats-officedocument.wordprocessingml.document','image/vnd.adobe.photoshop']
#max size of preview text to return (to avoid loading up full text of huge document in browser)
try:
   CONTENTSMAX=int(config['Display']['maxcontents'])
except:
   CONTENTSMAX=10000


@login_required
def do_search(request,page_number=0,**kwargs):
#    log.debug(request.__dict__)
    path_info=request.META.get('PATH_INFO')
    request.session['lastsearch']=path_info
    log.debug(request.session.get('lastsearch'))
    page=pages.SearchPage(page_number=page_number,searchurl=path_info, **kwargs)
    
    #log.debug('SESSION CACHE: '+str(vars(request.session)))
    log.debug('Request: {}    User: {}'.format(path_info,request.user))
    log.debug('Search parameters: {}'.format(page.__dict__))
    log.debug('Filters: {}, Tagfilters:{}'.format(page.filters,page.tagfilters))

    try:
    #GET AUTHORISED CORES AND DEFAULT
        thisuser=request.user
        storedcoreID=request.session.get('mycore','')
        log.debug('Stored core: {}'.format(storedcoreID))
        
        try:
            authcores=authorise.AuthorisedCores(thisuser,storedcore=storedcoreID)
            #log.debug('Authcores: {}'.format(authcores.__dict__))
            page.mycore=authcores.mycore
            choice_list=authcores.choice_list
            page.coreID=authcores.mycoreID
            #store the authorised core
            request.session['mycore']=page.coreID
            
        except authorise.NoValidCore as e:
            log.warning('Cannot find any valid coreID in authorised corelist')
            return HttpResponse('Missing any config data for any authorised index: contact administrator')
            
        log.debug('AUTHORISED CORE CHOICE: '+str(choice_list))
        log.debug('DEFAULT CORE ID:'+str(authcores.defaultcore))

#    
    #SET THE RESULT PAGE    
        page.page_number=int(page.page_number) #urls always returns strings only
        log.info('Page: {}'.format(page.page_number))

    
    #DO SEARCH IF PAGE ESTABLISHED 
        
        if page.page_number > 0: #if page value not default (0) then proceed directly with search
            log.info('User {} searching with searchterm: {} and tag \"{}\" and tag2 \"{}\" on page {} with core {}'.format(request.user.username,page.searchterm,page.tag1,page.tag2,page.page_number,page.coreID))
            try:
                log.debug(page.__dict__)
#                log.debug(type(page.start_date))
                form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm,page.start_date,page.end_date)

                page.startnumber=(page.page_number-1)*RESULTS_PER_PAGE
                page.faceting=True
                """go search>>>>>>>>>>>>>>>>>>>>>>>>>>>>"""
                solrJson.pagesearch(page)
                page.nextpages(RESULTS_PER_PAGE)
                
            except Exception as e:
                log.error('Error {}'.format(e))
                page.clear_()

    #PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN REDIDRECT WITH A GET TO DO FIRST SEARCH
        # if this is a POST request we need to process the form data
        elif request.method == 'POST': #if data posted from form
            # create a form instance and populate it with data from the request:
            form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm,None,None,request.POST)
            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required

                page.searchterm=form.cleaned_data['search_term'] #type Unicode
                page.sorttype=form.cleaned_data['SortType']
                page.start_date=form.cleaned_data['start_date']
                page.end_date=form.cleaned_data['end_date']


                coreselect=int(form.cleaned_data['CoreChoice'])
                if coreselect != page.coreID:  #NEW INDEX SELECTED
                    log.debug('change core')
                    page.coreID=coreselect  #new solr core ID
                    request.session['mycore']=page.coreID  #store the chosen index
                    log.debug('selected core'+str(coreselect))
                
                page.process_page_meta()
                return HttpResponseRedirect(page.searchurl)
            else:
                log.debug(form.__dict__)        
        # START BLANK FORM if a GET (or any other method) we'll create a blank form; and clear last search
        else:
            form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm,None,None)
            page.clear_()
            page.resultcount=-1
            request.session['lastsearch']=''
        page.process_page_meta()
        #log.debug('All page data: {}'.format(page.__dict__))
        return render(request, 'searchform.html', {'form': form, 'page':page})

    except solrJson.SolrCoreNotFound as e:
        log.error('Index not found on solr server')
        return HttpResponse('Index not found on solr server : check configuration')
    except solrJson.SolrConnectionError as e:
        log.error(e)
        return HttpResponse('No response from solr server : try again or check network connection, solr status')


@login_required
def embed(request,doc_id,hashfilename,mimetype):
    """return document to embed"""
    log.debug(f'Embed of doc_id: {doc_id} hashfilename: {hashfilename} with mimetype: {mimetype}')
        #check file exists in database and hash matches
    if mimetype not in MIMETYPES_THAT_EMBED:
        log.warning('Embedding document that cannot embed')
        return None
    try:
        thisfile=File.objects.get(id=doc_id)
        log.info('User: '+request.user.username+' embedding file: '+thisfile.filename)
        assert thisfile.hash_filename==hashfilename
    except AssertionError:
        log.warning('Embed failed because of hash mismatch')
        return None
    except ObjectDoesNotExist:
        log.warning('Embed failed as file ID not found in database')
        return None
        #check user authorised to download
    if authorise.authid(request,thisfile) is False:
        log.warning(thisfile.filename+' not authorised or not present')
        return None

    file_path = thisfile.filepath
    try:
        return make_file(file_path,mimetype)
    except DoesNotExist:
        log.error('DoesNotExist error in download embed: {}'.format(e))
    except Exception as e:
        log.error('Error in download embed: {}'.format(e))
    return None

    
@login_required
def download(request,doc_id,hashfilename):
    """download a document from the docstore"""
    log.debug('Download of doc_id:'+doc_id+' hashfilename:'+hashfilename)

    #MAKE CHECKS BEFORE DOWNLOAD
    #check file exists in database and hash matches
    try:
        thisfile=File.objects.get(id=doc_id)
        log.info('User: '+request.user.username+' attempting to download file: '+thisfile.filename)
        assert thisfile.hash_filename==hashfilename
    except AssertionError:
        log.warning('Download failed because of hash mismatch')
        return HttpResponse('File not stored on server')
    except ObjectDoesNotExist:
        log.warning('Download failed as file ID not found in database')
        return HttpResponse('File not stored on server')

    #check user authorised to download
    if authorise.authid(request,thisfile) is False:
        log.warning(thisfile.filename+' not authorised or not present')
        return HttpResponse('File NOT authorised for download')    

    file_path = thisfile.filepath
    try:
        log.info(f'DOWNLOAD by user: {request.user} of File: {file_path}')
        return make_download(file_path)
    except DoesNotExist:
        return HttpResponse('File not stored on server')
    except Exception as e:
        log.error('Error in download: {}'.format(e))
        raise Http404
    

@login_required
def get_content(request,doc_id,searchterm,tagedit='False'): 
    """make a page showing the extracted text, highlighting searchterm """
    
    log.info('User \'{}\' fetch content for doc id: \'{}\' from search term \'{}\''.format(request.user,doc_id,searchterm))
    log.debug('Request session : {}'.format(request.session.__dict__))
    
    page=pages.ContentPage(doc_id=doc_id,searchterm=searchterm,tagedit='False')
    page.safe_searchterm()
    page.searchurl=request.session.get('lastsearch','/ownsearch') #store the return page
    log.debug(type(page.searchurl))
    log.debug(request.META.get('PATH_INFO'))
    #GET INDEX
    #only show content if index defined in session:
    if request.session.get('mycore') is None:
        log.info('Get content request refused; no index defined in session')
        return HttpResponseRedirect('/') 
    page.coreID=int(request.session.get('mycore'))

    page.this_user=request.user
    corelist,DEFAULTCOREID,choice_list=authorise.authcores(page.this_user)
    page.mycore=corelist[page.coreID]

#    #HANDLE EDITS OF USER TAGS
#    useredit_str=request.session.get('useredit','')
#    log.debug('useredit: {}'.format(useredit_str))
#    if useredit_str=='True':
#        page.useredit=True	
#    else:
#        page.useredit= False
#    if request.method == 'POST': #if data posted from form
#        # create a form instance and populate it with data from the request:
#        form = TagForm('',request.POST)
#        log.debug('Tags data posted: {} Form all: {}'.format(request.POST,form.__dict__))
#            # check whether it's valid:
#        if request.POST.get('edit','')=='Edit':
#            log.debug('Editing user tags')
#            request.session['useredit']='True'
#            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(page.doc_id,page.searchterm))
#        elif request.POST.get('cancel','')=='Cancel':
#            log.debug('Cancel edit user tags')
#            request.session['useredit']='False'
#            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(page.doc_id,page.searchterm))            
#        elif request.POST.get('save','')=='Save':
#            log.debug('Save user tags')
#            request.session['useredit']=''
#            if form.is_valid():
#                # process the data in form.cleaned_data as required
#                keywords=form.cleaned_data['keywords']
#                log.debug('Keywords from form: {}, type{}'.format([(word,type(word)) for word in keywords],type(keywords)))
#                """Permit only alphanumeric and numbers as user tags - support Cyrillic in Py3""" 
#                keyclean=[re.sub(r'[^\w, ]','',item) for item in keywords]
#                updateresult=updateSolr.updatetags(page.doc_id,page.mycore,keyclean)
#                if updateresult:
#                    log.info('Update success of user tags: {} in solrdoc: {} by user {}'.format(keyclean,page.doc_id,request.user.username))
#                    update_user_edits(page,keyclean,request.user.username)
#                else:
#                    log.debug('Update failed of user tags: {} in solrdoc: {}'.format(keyclean,page.doc_id))
#            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(page.doc_id,page.searchterm))
    if True:

        #get a document content - up to max size characters
        try:
            page.results=solrJson.gettrimcontents(page.doc_id,page.mycore,CONTENTSMAX).results  #returns SolrResult object
            result=page.results[0]
            #log.debug(vars(result))
        except IndexError as e:
            log.error('Error: {}'.format(e))
            return HttpResponse('Can\'t find document with ID {} COREID: {}'.format(page.doc_id,page.coreID))
        except solrJson.SolrConnectionError:
            return HttpResponse('No connection to solr index')
        except Exception as e:
            log.error('Error: {}'.format(e))
            return HttpResponse('Error fetching document with ID {} COREID: {}'.format(page.doc_id,page.coreID))

        
        page.process_result(result)
        log.debug('Data ID: {}'.format(page.data_ID)) 
        
        #        #check if file is registered and authorised to download
        page.authflag,page.matchfile_id,page.hashfilename=authorise.authfile(request,page.hashcontents,page.docname)

        
        #REDIRECT IF PREVIEW URL DEFINED
        log.debug('Stored preview html: {}'.format(page.preview_url))
        if page.preview_url:
            return HttpResponseRedirect(page.preview_url) 
        
        if page.mimetype=='application/pdf':
            #page.pdf_url=static(os.path.join('files/',page.docpath))
            
            page.pdf_url=f"/ownsearch/download={page.matchfile_id}&{page.hashfilename}"
            log.debug('PDF URL: {}'.format(page.pdf_url))
            #statdoc = finders.find(page.docpath)
            log.debug(settings.STATIC_ROOT)
            statpath=os.path.join(settings.STATIC_ROOT,'files/',page.docpath)
            log.debug('statpath: {}'.format(statpath))
            if os.path.exists(statpath):
                log.debug('File exists in static: {}'.format(statpath))
        if page.mimetype in MIMETYPES_THAT_EMBED:
            if page.matchfile_id:
                log.debug('Embed authorised')
                page.embed=True
            else:
                page.embed=False
#            log.debug('PDF URL: {}'.format(page.pdf_url))
        else:
            page.embed=False

        #Make a user tag form    
        form = page.tagform()
#            log.debug('tag1: {}'.format(tags1))

        #Use preview template if preview HTML stored
        if page.html:
            page.searchterm_urlsafe=quote_plus(page.searchterm)
            return render(request, 'blogpost.html', {'form':form, 'page':page})
            	
        #DIVERT ON BIG FILE

        log.debug('Highlight length: '+str(len(page.highlight)))
        #detect if large file (contents greater or equal to max size)
        if len(page.highlight)==CONTENTSMAX:
           #go get large highlights instead
           return get_bigcontent(request,page)

        #clean up and prepare the preview text for display
        page.splittext,page.last_snippet,page.cleanterm=cleanup(page.searchterm,page.highlight)
        
        #log.debug('Page contents : {}'.format(page.result.__dict__))
        return render(request, 'content_small.html', {'form':form,'page':page})


def update_user_edits(doc_id,mycore,keyclean,username):
     #log.debug('{}{}'.format(keyclean,type(keyclean)))
     edit=UserEdit(solrid=doc_id,usertags=keyclean,corename=mycore.name)
     edit.username=username
     edit.time_modified=solrJson.timeaware(datetime.now())
     edit.save()
    

@login_required
def get_bigcontent(request,page): #make a page of highlights, for MEGA files
#        
    log.debug('GET BIGCONTENT')
    res=solrJson.bighighlights(page.doc_id,page.mycore,page.searchterm,CONTENTSMAX)
    if len(res.results)>0:
        #Get meta
        page.process_result(res.results[0]) #if duplicate, take the first
#        log.debug(result.data)
        #check if file is registered and authorised to download
        page.authflag,page.matchfile_id,page.hashfilename=authorise.authfile(request,page.hashcontents,page.docname)
        
        form = page.tagform()
        return render(request, 'content_big.html', {'form':form,'page':page})
#docsize':docsize, 'doc_id': doc_id, 'highlights': highlights, 'hashfile':hashfilename, 'fileid':matchfile_id,'searchterm': searchterm,'docname':docname, 'docpath':docpath, 'docexists':authflag})
    else:
        return HttpResponse('No document with ID '+doc_id+' COREID: '+coreID)


def cleansterm(searchterm):
    #    log.debug(searchterm)
    # take term in double quotes as search term
    try:
        cleanterm=re.search('\"(.+)\"',searchterm).group(0)[1:][:-1]
    except AttributeError as e:
        cleanterm=searchterm
    except Exception as e:
        log.debug(str(e))
        cleanterm=searchterm
    return cleanterm

def cleanup(searchterm,highlight):
    # CLEANUP TEXT
#    log.debug(repr(highlight[:400]))
    highlight=re.sub('\n \xc2\xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
    highlight=re.sub('\n \xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
#    print('SPACECLEANE'+repr(highlight[:400]))
    cleaned=re.sub('(\n[\s]+\n)+', '\n', highlight) #cleaning up chunks of white space
#    print('STRINGCLEANED'+repr(cleaned[:400]))
    cleaned=markup.urls(cleaned) #add links to text
    
    if searchterm:
        cleansearchterm=cleansterm(searchterm)
        log.debug(f'Searchterm cleaned: {cleansearchterm}')
        lastscrap=''
        try:
            splittext=re.split(cleansearchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
            if len(splittext) > 1:
                lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
        except:
            splittext=[cleaned]
        return splittext,lastscrap,cleansearchterm
    else:
    	   return [cleaned],'',''


@login_required
def check_solr(request):
    """API to check solr index is up"""
    jsonresponse={'error':True, 'solr_up':False,'message':'Unknown error checking solr index'}
    

    try:
        server=setup.check_solr(verbose=False) 
        if server.server_up:
            jsonresponse={'error':False, 'solr_up':True,'message': None}
    except Exception as e:
        pass
    
    return JsonResponse(jsonresponse)

@login_required
def check_bot(request):
    """API to check watcher threads are running"""
    jsonresponse={'error':True, 'sleuth_bot':False,'message':'Unknown error checking bot heartbeat'}

    try:
        heartbeat=watch_dispatch.HeartBeat().alive
        #log.debug(f'Heartbeat: {heartbeat}')
        if heartbeat:
            jsonresponse={'error':False, 'sleuth_bot':True,'message':''}
        else:
            jsonresponse.update({'error':False,'message':''})
    except Exception as e:
        log.debug(e)
        pass
    return JsonResponse(jsonresponse)


@login_required
def post_usertags(request):
    """API to update usertags from content page"""
    jsonresponse={'saved':False, 'valid_form':False,'message':'Unknown error saving usertag'}
    
    #GET AUTHORISED CORES AND DEFAULT
    try:
        thisuser=request.user
        storedcoreID=request.session.get('mycore','')
        authcores=authorise.AuthorisedCores(thisuser,storedcore=storedcoreID)
        #log.debug('Authcores: {}'.format(authcores.__dict__))
        mycore=authcores.mycore	
        if not request.is_ajax():
            return HttpResponse('API call: Not Ajax')
        else:
            if request.method == 'POST':
                log.debug('Raw Data: {}'.format( request.body))
                response_json = json.dumps(request.POST)
                data = json.loads(response_json)
                log.debug ("Json data: {}.".format(data))
                postdata=request.POST
                jsonresponse=update_usertags(data,thisuser.username,postdata,mycore)
                log.debug('Json response:{}'.format(jsonresponse))
            else:
                log.debug('Error: Get to API')
    except Exception as e:
        pass
    return JsonResponse(jsonresponse)


def update_usertags(data,username,postdata,mycore):
    log.info(f'User {username} updating usertags in index {mycore} with {data}') 
    try:
        form=TagForm('',postdata)
        #log.debug('Form data: {}'.format(form.__dict__))
        log.debug('Data posted: {} Form all: {}'.format(postdata,form.__dict__))
        if form.is_valid():
            # process the data in form.cleaned_data as required
            keywords=form.cleaned_data['keywords']
            log.debug('Keywords from form: {}'.format(keywords))
            #, type{}'.format([(word,type(word)) for word in keywords],type(keywords)))
            if keywords != [form.fields['keywords'].label]: #eliminate default

                """Permit only alphanumeric and numbers as user tags - support Cyrillic in Py3""" 
                keyclean=[re.sub(r'[^\w, ]','',item) for item in keywords]
                doc_id=form.cleaned_data['doc_id']
                log.debug(doc_id)
                if updateSolr.updatetags(doc_id,mycore,keyclean):
                    log.info('Update success of user tags: {} in solrdoc: {} by user {}'.format(keyclean,doc_id,username))
                    update_user_edits(doc_id,mycore,keyclean,username)
                    return {'saved':True, 'verified':True,'message':None}
                else:
                    log.debug('Update failed of user tags: {} in solrdoc: {}'.format(keyclean,doc_id))
                    return {'saved':False, 'verified':True,'message':'Update to index failed'}
            else:
                return {'saved':False, 'valid_form':False,'message':'Invalid tag'}
        else:
            log.debug('form not valid; errors: {}'.format(form.errors))
            return {'saved':False, 'verified':False,'message':'Invalid tag'}
            	  
    except Exception as e:
        log.error("Failed to edit usertags with data {} and error {}".format(postdata,e))
        return {'saved':False, 'valid_form':True,'message':'Unknown error saving usertags'}


@login_required
def testsearch(request,doc_id,searchterm):
	    #load solr index in use, SolrCore object
    corestring=request.session.get('mycore')
    if corestring:
        coreID=int(corestring)
    else:
        coreID=''
    if coreID:
        mycore=cores[coreID]
        results=solrJson.testresponse(doc_id,mycore,searchterm)
        log.debug(results)
        if len(results)>0:
            if 'highlight' in results[0].data:
                highlight=results[0].data['highlight']
                return HttpResponse(highlight)
        return HttpResponse(results)
    else:
        return HttpResponseRedirect('/')        
        


