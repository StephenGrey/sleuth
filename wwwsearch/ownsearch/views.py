# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

"""
from __future__ import unicode_literals
from .forms import SearchForm,TagForm
from documents.models import File,Collection,SolrCore,UserEdit
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.db.models.base import ObjectDoesNotExist
import solrJson, re, os, logging, unicodedata, urllib
from documents import solrcursor,updateSolr
from datetime import datetime
from usersettings import userconfig as config
log = logging.getLogger('ownsearch.views')
docbasepath=config['Models']['collectionbasepath']
import pages

@login_required
def do_search(request,page=0,searchterm='',direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3=''):
#    log.debug('SESSION CACHE: '+str(vars(request.session)))
    searchpage=pages.Page(page_number=page,searchterm=searchterm,direction=direction,pagemax=pagemax,sorttype=sorttype,tag1field=tag1field,tag1=tag1,tag2field=tag2field,tag2=tag2,tag3field=tag3field,tag3=tag3)
    
    #GET PARAMETERS
    searchpage.searchterm=urllib.unquote_plus(searchterm)
    searchpage.filters={tag1field:tag1,tag2field:tag2,tag3field:tag3}
    searchpage.filters.pop('','') #remove blank filters
    #print(searchpage.filters)
    if tag1 or tag2 or tag3:
        searchpage.tagfilters=True
    else:
        searchpage.tagfilters=False
    log.debug('Filters: {}'.format(searchpage.filters))
    try:
    #GET AUTHORISED CORES AND DEFAULT
        corelist,DEFAULTCOREID,choice_list=authcores(request)
#        print(str(choice_list))
        log.debug('AUTHORISED CORE CHOICE: '+str(choice_list))
        log.debug('DEFAULT CORE ID:'+str(DEFAULTCOREID))

    #GET THE INDEX get the solr index, a SolrCore object, or choose the default
        if 'mycore' not in request.session:  #set default if no core selected
            log.debug('no core selected.. setting default')
            request.session['mycore']=DEFAULTCOREID
        searchpage.coreID=int(request.session.get('mycore'))
        #print(vars(request.session),'COREID:'+str(coreID),' CORELIST:'+str(corelist))
        if searchpage.coreID in corelist:
            searchpage.mycore=corelist[searchpage.coreID]
        elif DEFAULTCOREID in corelist:
            searchpage.mycore=corelist[DEFAULTCOREID]
            request.session['mycore']=DEFAULTCOREID
            searchpage.coreID=DEFAULTCOREID
        else:
            log.warning('Cannot find any valid coreID in authorised corelist')
            return HttpResponse('Missing any config data for any authorised index: contact administrator')
    
    #SET THE RESULT PAGE    
        searchpage.page_number=int(searchpage.page_number) #urls always returns strings only
        log.info('Page: {}'.format(searchpage.page_number))
    
    #DO SEARCH IF PAGE ESTABLISHED 
        
        if searchpage.page_number > 0: #if page value not default (0) then proceed directly with search
            searchpage.resultlist=[]
            form = SearchForm(choice_list,str(searchpage.coreID),searchpage.sorttype,searchpage.searchterm)
            log.info('User {} searching with searchterm: {} and tag \"{}\" and tag2 \"{}\" on page {}'.format(request.user.username,searchpage.searchterm,searchpage.tag1,searchpage.tag2,searchpage.page_number))
            try:
                searchpage.startnumber=(searchpage.page_number-1)*10
#                if sorttype=='relevance':
                if True:
                   
                    searchpage.results,searchpage.resultcount,searchpage.facets,searchpage.facets2,searchpage.facets3=solrJson.solrSearch(searchpage.searchterm,searchpage.sorttype,searchpage.startnumber,core=searchpage.mycore, filters=searchpage.filters, faceting=True)
                    searchpage.pagemax=int(searchpage.resultcount/10)+1

                    if searchpage.page_number>1:
                        searchpage.backpage=searchpage.page_number-1
                    else:
                        searchpage.backpage=''
                    if searchpage.page_number<searchpage.pagemax:
                        searchpage.nextpage=searchpage.page_number+1
                    else:
                        searchpage.nextpage=''

            except Exception as e:
#                print(e)
                log.error('Error {}'.format(e))
                log.debug(searchpage.sorttype)
                log.debug(str(searchpage.resultlist))
                searchpage.clear_()

    #PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN REDIDRECT WITH A GET TO DO FIRST SEARCH
        # if this is a POST request we need to process the form data
        elif request.method == 'POST': #if data posted from form
    
            # create a form instance and populate it with data from the request:
            form = SearchForm(choice_list,str(searchpage.coreID),searchpage.sorttype,searchpage.searchterm,request.POST)
            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required
                #print(vars(form))
                searchpage.searchterm=form.cleaned_data['search_term']
                searchpage.sorttype=form.cleaned_data['SortType']
                coreselect=int(form.cleaned_data['CoreChoice'])
                if coreselect != searchpage.coreID:  #NEW INDEX SELECTED
                    log.debug('change core')
                    searchpage.coreID=coreselect  #new solr core ID
                    request.session['mycore']=searchpage.coreID  #store the chosen index
        #            mycore=corelist[coreID]  #select new SolrCore object
                    log.debug('selected core'+str(coreselect))
#                request.session['results']='' #clear results from any previous searches
                
                searchpage.searchterm_urlsafe=urllib.quote_plus(searchpage.searchterm.encode('utf-8'))
                searchpage.searchurl="/ownsearch/searchterm={}&page=1&sorttype={}".format(searchpage.searchterm_urlsafe,searchpage.sorttype)
                request.session['lastsearch']=searchpage.searchurl
                return HttpResponseRedirect(searchpage.searchurl)
                
                    
        # START BLANK FORM if a GET (or any other method) we'll create a blank form; and clear last search
        else:
            form = SearchForm(choice_list,str(searchpage.coreID),searchpage.sorttype,searchpage.searchterm)
            searchpage.clear_()
            searchpage.resultcount=-1
            request.session['lastsearch']=''

        #print(resultlist)
        searchpage.searchterm_urlsafe=urllib.quote_plus(searchpage.searchterm.encode('utf-8'))
        searchpage.filterlist=[(tag,searchpage.filters[tag]) for tag in searchpage.filters]
        log.debug('Filter list : {}'.format(searchpage.filterlist))
        return render(request, 'searchform.html', {'form': form, 'page':searchpage})

    except solrJson.SolrCoreNotFound as e:
        log.error('Index not found on solr server')
        return HttpResponse('Index not found on solr server : check configuration')
    except solrJson.SolrConnectionError as e:
        log.error(e)
        return HttpResponse('No response from solr server : check network connection, solr status')

@login_required
def download(request,doc_id,hashfilename): #download a document from the docstore
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
    if authid(request,thisfile) is False:
        log.warning(thisfile.filename+' not authorised or not present')
        return HttpResponse('File NOT authorised for download')    

    file_path = thisfile.filepath
    if os.path.exists(file_path):
        cleanfilename=slugify(os.path.basename(file_path))
        with open(file_path, 'rb') as thisfile:
            response=HttpResponse(thisfile.read(), content_type='application/force-download')
            response['Content-Disposition'] = 'inline; filename=' + cleanfilename
            log.info('DOWNLOAD User: '+str(request.user)+' Filepath: '+file_path)
            return response
        raise Http404
    else:
        return HttpResponse('File not stored on server')


@login_required
def get_content(request,doc_id,searchterm,tagedit='False'): #make a page showing the extracted text, highlighting searchterm
    log.debug('Get content for doc id: {} from search term {}'.format(doc_id,searchterm))
    searchterm=urllib.unquote_plus(searchterm)
    searchurl=request.session.get('lastsearch','/ownsearch') #get the search page to return to, or home page
    #load solr index in use, SolrCore object
    if True:
        #GET INDEX
        #only show content if index defined in session:
        if request.session.get('mycore') is None:
            log.info('Get content request refused; no index defined in session')
            return HttpResponseRedirect('/') 
        coreID=int(request.session.get('mycore'))
        corelist,defaultcoreID,choice_list=authcores(request)
        mycore=corelist[coreID]

    #HANDLE EDITS OF USER TAGS
    useredit=request.session.get('useredit','')
    log.debug('useredit: {}'.format(useredit))
    if useredit=='True':
        useredit=True	
    else:
        useredit= False
    if request.method == 'POST': #if data posted from form
        # create a form instance and populate it with data from the request:
        form = TagForm('',request.POST)
        print(request.POST)
            # check whether it's valid:
        if request.POST.get('edit','')=='Edit':
            log.debug('Editing user tags')
            request.session['useredit']='True'
            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(doc_id,searchterm))
        elif request.POST.get('save','')=='Save':
            log.debug('Save user tags')
            request.session['useredit']=''
            if form.is_valid():
                # process the data in form.cleaned_data as required
                keywords=form.cleaned_data['keywords']
                keyclean=[re.sub(r'[^a-zA-Z0-9, ]','',item) for item in keywords]
                updateresult=updateSolr.updatetags(doc_id,mycore,keyclean)
                if updateresult:
                    log.info('Update success of user tags: {} in solrdoc: {} by user {}'.format(keyclean,doc_id,request.user.username))
                    edit=UserEdit(solrid=doc_id,usertags=keyclean,corename=mycore.name)
                    edit.username=request.user.username
                    edit.time_modified=solrJson.timeaware(datetime.now())
                    edit.save()
                else:
                    log.debug('Update failed of user tags: {} in solrdoc: {}'.format(keyclean,doc_id))
            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(doc_id,searchterm))
    else:
        #GET DEFAULTS
        #set max size of preview text to return (to avoid loading up full text of huge document in browser)
        try:
            contentsmax=int(config['Display']['maxcontents'])
        except:
            contentsmax=10000

        #get a document content - up to max size characters
        results=solrJson.gettrimcontents(doc_id,mycore,contentsmax).results  #returns SolrResult object
        try:
            result=results[0]
            #log.debug(vars(result))
        except KeyError:
            return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)
            
        docname=result.docname
        docpath=result.data['docpath']
        datetext=result.datetext
        
        data_ID=result.data.get('SBdata_ID','') #pulling ref to doc if stored in local database
        #if multivalued, take the first one
        if isinstance(data_ID,list):
            data_ID=data_ID[0]
        log.debug('Data ID '+str(data_ID)) 
        if True:
            initialtags=result.data.get(mycore.usertags1field,'')
            if not isinstance(initialtags,list):
                initialtags=[initialtags]
            tagstring=','.join(map(str, initialtags))
#            log.debug('{},{}'.format(initialtags,tagstring))
            form = TagForm(tagstring)
            
            tags1=result.data.get('tags1',[False])[0]
            if tags1=='':
                tags1=False
#            log.debug('tag1: {}'.format(tags1))

        #USE SPECIAL TEMPLATE TO PREVIEW HTML IN SOLR INDEX (in case of scraped web pages, or other HTML)
        html=result.data.get('preview_html','')
        if html:
            searchterm_urlsafe=urllib.quote_plus(searchterm)
            return render(request, 'blogpost.html', {'form':form,'body':html, 'tags1':tags1,'tagstring':tagstring,'initialtags': initialtags,'useredit':useredit,'docid':data_ID,'solrid':doc_id,'docname':docname,'docpath':docpath,'datetext':datetext,'data':result.data,'searchterm': searchterm, 'searchterm_urlsafe': searchterm_urlsafe, 'searchurl':searchurl})
#        log.debug('Full result '+str(result.__dict__))    

        #DIVERT ON BIG FILE
        try:
            highlight=result.data['highlight']
        except KeyError:
            highlight=''
            log.debug('No highlight found')

        log.debug('Highlight length: '+str(len(highlight)))
        #detect if large file (contents greater or equal to max size)
        if len(highlight)==contentsmax:
           #go get large highlights instead
           res=get_bigcontent(request,doc_id,searchterm,mycore,contentsmax)
           return res
           
        docsize=result.data['solrdocsize']
        rawtext=result.data['rawtext']
        hashcontents=result.data['hashcontents']

#        #check if file is registered and authorised to download
        authflag,matchfile_id,hashfilename=authfile(request,hashcontents,docname)

    #clean up the text for display
        splittext,lastscrap,cleanterm=cleanup(searchterm,highlight)
        
        #print(result.data)
        return render(request, 'contentform.html', {'docsize':docsize, 'doc_id': doc_id, 'splittext': splittext, 'searchterm': cleanterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath, 'hashfile':hashfilename, 'fileid':matchfile_id,'tags1':tags1,'tagstring':tagstring,'initialtags': initialtags,'useredit': useredit,'docexists':authflag, 'data':result.data, 'form':form, 'searchurl':searchurl})
        

#    except Exception as e:
#        log.error(str(e))
#        return HttpResponseRedirect('/') 

@login_required
def get_bigcontent(request,doc_id,searchterm,mycore,contentsmax): #make a page of highlights, for MEGA files
#        
    log.debug('GET BIGCONTENT')
    res=solrJson.bighighlights(doc_id,mycore,searchterm,contentsmax)
#    log.debug('{}'.format(res.__dict__))
    if len(res.results)>0:
        #if more than one result, take the first
        result=res.results[0]
#        log.debug(result.data)
        docsize=result.data['solrdocsize']
        docpath=result.data['docpath']
        rawtext=result.data['rawtext']
        docname=result.docname
        hashcontents=result.data['hashcontents']
        highlights=result.data['highlight'] 

    #check if file is registered and authorised to download
        authflag,matchfile_id,hashfilename=authfile(request,hashcontents,docname)

        return render(request, 'bigcontentform.html', {'docsize':docsize, 'doc_id': doc_id, 'highlights': highlights, 'hashfile':hashfilename, 'fileid':matchfile_id,'searchterm': searchterm,'docname':docname, 'docpath':docpath, 'docexists':authflag})
    else:
        return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)


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
        
    cleansearchterm=cleansterm(searchterm)
    log.debug(cleansearchterm)
    lastscrap=''
    try:
        splittext=re.split(cleansearchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
        if len(splittext) > 1:
            lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
    except:
        splittext=[cleaned]
    return splittext,lastscrap,cleansearchterm
    

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
        print results
        if len(results)>0:
            if 'highlight' in results[0].data:
                highlight=results[0].data['highlight']
                return HttpResponse(highlight)
        return HttpResponse(results)
    else:
        return HttpResponseRedirect('/')        
        


def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    shortName, fileExt = os.path.splitext(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    return value+fileExt

##set up solr indexes
@login_required
def authcores(request):
    cores={}
    choice_list=()
    thisuser=request.user
    groupids=[group.id for group in thisuser.groups.all()]
    log.debug('authorised groups for user: '+str(groupids))
    corelist=(SolrCore.objects.filter(usergroup_id__in=groupids))
    log.debug('authorised core list '+str(corelist))
    for core in corelist:
        cores[core.id]=solrJson.SolrCore(core.corename)
        corenumber=str(core.id)
        coredisplayname=core.coreDisplayName
        choice_list +=((corenumber,coredisplayname),) #value/label
    try:
        DEFAULTCOREID=int(config['Solr']['defaultcoreid'])
        #print(defaultcoreID,cores)
        assert DEFAULTCOREID in cores     
    except Exception as e:
        log.debug('Default core ('+str(DEFAULTCOREID)+') set in userconfigs is not found in authorised indexes: first available is made default')
        try:
            log.debug(str(cores)+' '+str(choice_list))
            DEFAULTCOREID=int(choice_list[0][0])#if no default found, take first in list as new default
#            defaultcoreID=cores.keys()[0]  #take any old core, if default not found
        except Exception as e:
            log.error('No valid and authorised index set in database: fix in /admin interface')
            log.error(str(e))
            cores={}
            DEFAULTCOREID=0
    return cores, DEFAULTCOREID, choice_list

#CHECK IF FILE WITH SAME HASH EXISTS IN DATABASE, AUTHORISED FOR DOWNLOAD AND IS PRESENT ON  MEDIA
def authfile(request,hashcontents,docname,acceptothernames=True):
    matchfiles=File.objects.filter(hash_contents=hashcontents) #find local registered files by hashcontents
    if matchfiles:
        log.debug('hashcontents: '+hashcontents)    
    #get authorised cores
        #user groups that user belongs to
        authgroupids=[group.id for group in request.user.groups.all()]
        log.debug('authorised groups for user: '+str(authgroupids))
        #indexes that user is authorised for
        authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
        log.debug(str(authcoreids)+'.. cores authorised for user')
        
    #find authorised file
        altlist=[]
        for f in matchfiles:
            fcore=Collection.objects.get(id=f.collection_id).core_id  #get core of database file
            if fcore in authcoreids and os.path.exists(f.filepath) and docname==f.filename:
                #FILE AUTHORISED AND EXISTS LOCALLY
                log.debug('matched authorised file'+f.filepath)
                return True,f.id,f.hash_filename
            
            #finding authorised file that match hash and exist locally but have different filename
            elif fcore in authcoreids and os.path.exists(f.filepath):
                altlist.append(f)
         #if no filenames match, return a hashmatch
        if acceptothernames and altlist:
            log.debug('hashmatches with other filenames'+str(altlist))
            #return any of them
            log.debug('returning alternative filename match'+altlist[0].filepath)
            return True,altlist[0].id,altlist[0].hash_filename
        
#        #ALTERNATIVE METHOD _ MATCH SET OF AUTHORISED CORES WITH CORES CONTAINING FILE 
#        collection_ids=[matchfile.collection_id for matchfile in matchfiles]
#        log.debug(str(collection_ids)+'.. collections containing file')
#        #indexes that contain the file
#        coreids=[collection.core_id for collection in Collection.objects.filter(id__in=collection_ids)]
#        log.debug(str(coreids)+' .. cores containing file')
#        #test if indexes containing file match authorised indexes
#        if not set(authcoreids).isdisjoint(coreids):
#            #I.E.??? RETURNS TRUE IF ANY IN FIRST LIST MATCHES ANY IN SECOND LIST (SET INTERSECTION)
            
    #return blanks
    return False,'',''
        
def authid(request,doc):
    coreid=Collection.objects.get(id=doc.collection_id).core_id
    #print(coreid)
    #user groups that user belongs to
    authgroupids=[group.id for group in request.user.groups.all()]
    #print(authgroupids)
    #indexes that user is authorised for
    authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
    #print(authcoreids)
    if coreid in authcoreids:
        return True
    else:
        return False

