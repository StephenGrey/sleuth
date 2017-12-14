# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

"""
from __future__ import unicode_literals
from .forms import SearchForm
from documents.models import File,Collection,SolrCore
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.db.models.base import ObjectDoesNotExist
import solrSoup, re, os, logging, unicodedata
from documents import solrcursor
from usersettings import userconfig as config
log = logging.getLogger('ownsearch.views')
docbasepath=config['Models']['collectionbasepath']


@login_required
def do_search(request,page=0,searchterm='',direction='',pagemax=0,sorttype='',tag1=''):
#    log.debug('SESSION CACHE: '+str(vars(request.session)))
    log.debug('TAG1: '+tag1)
    try:

    #GET AUTHORISED CORES AND DEFAULT
        corelist,defaultcoreID,choice_list=authcores(request)
#        print(str(choice_list))
        log.debug('AUTHORISED CORE CHOICE: '+str(choice_list))
        log.debug('DEFAULT CORE ID:'+str(defaultcoreID))
        
        #set initial default sorttype
        if sorttype=='':
            sorttype='relevance'
    #GET THE INDEX get the solr index, a SolrCore object, or choose the default
        if 'mycore' not in request.session:  #set default if no core selected
            log.debug('no core selected.. setting default')
            request.session['mycore']=defaultcoreID
        coreID=int(request.session.get('mycore'))
        #print(vars(request.session),'COREID:'+str(coreID),' CORELIST:'+str(corelist))
        if coreID in corelist:
            mycore=corelist[coreID]
        elif defaultcoreID in corelist:
            mycore=corelist[defaultcoreID]
            request.session['mycore']=defaultcoreID
            coreID=defaultcoreID
        else:
            log.warning('Cannot find any valid coreID in authorised corelist')
            return HttpResponse('Missing any config data for any authorised index: contact administrator')
    
    #SET THE RESULT PAGE    
        page=int(page) #urls always returns strings only
        #print('page',page,'searchterm',searchterm,'direction',direction)
        if direction == 'next':
            page=page+1
        if direction == 'back':
            page=page-1
        #print('page',page)
    
    #DO SEARCH IF PAGE ESTABLISHED 
        
        if page > 0: #if page value not default (0) then proceed directly with search
            resultlist=[]
            form = SearchForm(choice_list,str(coreID),sorttype)
            log.info('User '+request.user.username+' searching with searchterm: '+searchterm+' and tag \"'+tag1+'\" on page '+str(page))
            try:
                startnumber=(page-1)*10
                if sorttype=='relevance':
                    #if 'relevance' search then return the results 'as is'
                    if tag1:
                        filters={'tagnames_list':tag1}
                    else:
                        filters={}
                    #filters={'tagnames_list':'Joseph Muscat'}
                    resultlist,resultcount,facets=solrSoup.solrSearch(searchterm,sorttype,startnumber,core=mycore, filters=filters)
                    pagemax=int(resultcount/10)+1
                    #tagcheck=[result.data for result in resultlist]
                    #log.debug(str(tagcheck))
                else:
                    fullresults=request.session['results']
                    #try to retrieve full results from session (if search sorted by other than relevance)
                    #if RESULTS EXIST THEN JUST EXTRACT RESULT SET 
                    if fullresults: #search already done                    
                        resultlist=[]
                        for id,data,date,datetext,docname in fullresults[startnumber:startnumber+10]:
                            resultlist.append(solrSoup.Solrdoc(data,date=date,datetext=datetext,docname=docname,id=id))
    #                    log.debug(resultlist)
                        resultcount=len(fullresults)
                        pagemax=int(resultcount/10)+1
                        
                    #ELSE DO THE SEARCH FOR THE FIRST TIME AND THEN STORE
                    else:
                    #FOR SEARCHES ON OTHER KEY WORDS >> DO A COMPLETE CURSOR SEARCH, SORT, THEN STORE RESULTS
                        log.info('User '+request.user.username+' searching with searchterm: '+searchterm+' and using sorttype '+sorttype)
                        sortedresults=solrcursor.cursorSearch(searchterm,sorttype,mycore)
                        #log.debug(sortedresults)
                        resultcount=len(sortedresults)
                        fullresultlist=[]
                        if resultcount>0:
                            for n, itemlist in enumerate(sortedresults):
                                for item in sortedresults[itemlist]:
                                    item.data['resultnumber']=n+1
                                    fullresultlist.append(item)
                        #get the first page of results
                        resultlist=fullresultlist[:10]
                        facets=[]
#                        log.debug(resultlist)
#                        log.debug([doc.__dict__ for doc in resultlist])
                        pagemax=int(resultcount/10)+1

                        if resultcount > 10:
#                            page = 1
                            #store the full results  -- pulling the data elements from the solr response]
                            request.session['results']=[(result.id,result.data,result.date,result.datetext,result.docname) for result in fullresultlist]
#                        else:
#                            page = 0


            except Exception as e:
                print(e)
                log.error(str(e))
                log.debug(sorttype)
                log.debug(str(resultlist))
                resultlist=[]
                facets=[]
                resultcount=0
                pagemax=0

    #PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN DO FIRST SEARCH
        # if this is a POST request we need to process the form data
        elif request.method == 'POST': #if data posted from form
    
            # create a form instance and populate it with data from the request:
            form = SearchForm(choice_list,str(coreID),sorttype,request.POST)
            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required
                #print(vars(form))
                searchterm=form.cleaned_data['search_term']
                sorttype=form.cleaned_data['SortType']
                coreselect=int(form.cleaned_data['CoreChoice'])
                if coreselect != coreID:  #NEW INDEX SELECTED
                    log.debug('change core')
                    coreID=coreselect  #new solr core ID
                    request.session['mycore']=coreID  #store the chosen index
        #            mycore=corelist[coreID]  #select new SolrCore object
                    log.debug('selected core'+str(coreselect))
                request.session['results']='' #clear results from any previous searches
                #DEBUG
                
                return HttpResponseRedirect("/ownsearch/searchterm={}&nextafterpage=0&sorttype={}".format(searchterm,sorttype))
                
                    
        # START BLANK FORM if a GET (or any other method) we'll create a blank form
        else:
            form = SearchForm(choice_list,str(coreID),sorttype)
            resultlist = []
            resultcount=-1

        return render(request, 'searchform.html', {'form': form, 'tagfilter':tag1,'facets':facets,'pagemax': pagemax, 'results': resultlist, 'searchterm': searchterm, 'resultcount': resultcount, 'page':page, 'sorttype': sorttype})

    except solrSoup.SolrCoreNotFound as e:
        log.error('Index not found on solr server')
        return HttpResponse('Index not found on solr server : check configuration')
    except solrSoup.SolrConnectionError as e:
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
def get_content(request,doc_id,searchterm): #make a page showing the extracted text, highlighting searchterm
    
    #load solr index in use, SolrCore object
    try:
        #GET INDEX
        #only show content if index defined in session:
        if request.session.get('mycore') is None:
            log.info('Get content request refused; no index defined in session')
            return HttpResponseRedirect('/') 
        coreID=int(request.session.get('mycore'))
        corelist,defaultcoreID,choice_list=authcores(request)
        mycore=corelist[coreID]

        #GET DEFAULTS
        #set max size of preview text to return (to avoid loading up full text of huge document in browser)
        try:
            contentsmax=int(config['Display']['maxcontents'])
        except:
            contentsmax=10000

        #get a document content - up to max size characters
        results=solrSoup.gettrimcontents(doc_id,mycore,contentsmax).results  #returns SolrResult object
        try:
            result=results[0]
#            log.debug(vars(result))
        except KeyError:
            return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)
            
        docname=result.docname
        docpath=result.data['docpath']
        datetext=result.datetext
        #DIVERT IF PREVIEW HTML IN SOLR INDEX (in case of scraped web pages, or other HTML)
        html=result.data.get('preview_html','')
        data_ID=result.data.get('SBdata_ID','') #pulling ref to doc if stored in local database
        log.debug('Data ID '+str(data_ID)) 
        if html:
            return render(request, 'blogpost.html', {'body':html, 'docid':data_ID[0],'docname':docname,'docpath':docpath,'datetext':datetext})
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
        splittext,lastscrap=cleanup(searchterm,highlight)
        
        return render(request, 'contentform.html', {'docsize':docsize, 'doc_id': doc_id, 'splittext': splittext, 'searchterm': searchterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath, 'hashfile':hashfilename, 'fileid':matchfile_id,'docexists':authflag})
        

    except Exception as e:
        log.error(str(e))
        return HttpResponseRedirect('/') 

@login_required
def get_bigcontent(request,doc_id,searchterm,mycore,contentsmax): #make a page of highlights, for MEGA files
#        
    res=solrSoup.bighighlights(doc_id,mycore,searchterm,contentsmax)
    log.debug(res)
    if len(res.results)>0:
        #if more than one result, take the first
        result=res.results[0]
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


def cleanup(searchterm,highlight):
    cleaned=re.sub('(\n[\s]+\n)+', '\n\n', highlight) #cleaning up chunks of white space
    lastscrap=''
    try:
        splittext=re.split(searchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
        if len(splittext) > 1:
            lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
    except:
        splittext=[cleaned]
    return splittext,lastscrap
    

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
        results=solrSoup.testresponse(doc_id,mycore,searchterm)
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
        cores[core.id]=solrSoup.SolrCore(core.corename)
        corenumber=str(core.id)
        coredisplayname=core.coreDisplayName
        choice_list +=((corenumber,coredisplayname),) #value/label
    try:
        defaultcoreID=int(config['Solr']['defaultcoreid'])
        #print(defaultcoreID,cores)
        assert defaultcoreID in cores     
    except Exception as e:
        log.debug('Default core ('+str(defaultcoreID)+') set in userconfigs is not found in authorised indexes: first available is made default')
        try:
            log.debug(str(cores)+' '+str(choice_list))
            defaultcoreID=int(choice_list[0][0])#if no default found, take first in list as new default
#            defaultcoreID=cores.keys()[0]  #take any old core, if default not found
        except Exception as e:
            log.error('No valid and authorised index set in database: fix in /admin interface')
            log.error(str(e))
            cores={}
            defaultcoreID=0
    return cores, defaultcoreID, choice_list

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

