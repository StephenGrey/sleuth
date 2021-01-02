import os,shutil
from documents import indexSolr,solrICIJ
from ownsearch import solrJson
from documents.models import Collection,File,Index
from documents.management.commands import setup
from documents.management.commands.setup import make_admin_or_login

## store any password to login later
PASSWORD = 'mypassword' 
MANUAL=False


class Tester():
	""" use the tests only index for testing solr indexing"""
	def __init__(self):
		self.password=PASSWORD
		self.username='myuser'
		self.my_email='myemail@test.com'
		#check admin user exists and login
		make_admin_or_login(self)
		self.mycore=solrJson.SolrCore('tests_only')
		self.check=True
		self.ocr=True

def check_exist(_list):
	"""eliminate fails with bad paths"""
	cleaned=[]
	for f in _list:
		if os.path.exists(f.filepath):
			cleaned.append(f)
		else:
			print(f'{f.filepath}does not exist' )
	return cleaned

def failed_messages(n=100,x=0,collection_id=None):
	"""take a sample of message files that failed	"""
	if collection_id:
		#collection=Collection.objects.get(id=collection_id)
		fails=File.objects.filter(indexedSuccess=False,indexedTry=True,collection=collection_id)
	else:
		fails=File.objects.filter(indexedSuccess=False,indexedTry=True,fileext='.msg')
	sample=fails[x:x+n]
	cleaned=check_exist(sample)
	return cleaned

def copy_files(fails,destination):
	"""copy list of files to another folder"""
	assert os.path.exists(destination)
	assert os.path.isdir(destination)
	for f in fails:
		shutil.copy(f.filepath, destination)

def extract(_file,tester,_test=False):
	extractor=indexSolr.ExtractFile(_file.filepath,tester.mycore,hash_contents=_file.hash_contents,sourcetext="testsource",test=_test,check=tester.check)
	return extractor 


def extract_icij(filepath,core):
	ext = solrICIJ.ICIJExtractor(filepath,core,ocr=True)
	return ext

#admingroup,usergroup=setup.make_admingroup(tester.admin_user,verbose=False)
#setup.make_default_index(usergroup,verbose=True,corename='tests_only')
#sampleindex=Index.objects.get(corename='tests_only')

def find_fails():
	sample=failed_messages(n=10000,x=0)
	#_try=sample[10]
	#print(f'trying {_try.filepath}')
	try_extract(sample)

def try_extract(sample):
	fails=[]
	tester=Tester()

	for _fail in sample:	
		try:
			_indexer=extract(_fail,tester)
			if _indexer.result==False:
				print(f'Fail:  filepath:{_fail.filepath}error:{_indexer.error_message}')
				fails.append(_fail)
				if len(fails)>100:
					break
			else:
				_indexer.post_process()
				result=_indexer.post_result
				if result==False:
					print(f'Fail:  filepath:{_fail.filepath}error:{_indexer.error_message}')
					fails.append(_fail)
					if len(fails)>100:
						break	
		except Exception as e:
			print(e)
	return fails
	

def try_folder(folder,ICIJ=False):
	fails=[]
	tester=Tester()
	_test=False
	for f in os.listdir(folder):
		filepath=os.path.join(folder,f)
		assert os.path.exists(filepath)	
		if ICIJ:
			try:
				_indexer=extract_icij(filepath,tester.mycore)
				result=_indexer.result
				error_message=_indexer.error_message
				if result is False:
					print(f'Fail:  filepath:{filepath}error:{_indexer.error_message}')
					fails.append(filepath)
					if len(fails)>100:
						break
			except Exception as e:
				print(e)			
		else:
		
			try:
				_indexer=indexSolr.ExtractFile(filepath,tester.mycore,sourcetext="testsource",test=_test,check=tester.check)
				if _indexer.result==False:
					print(f'Fail:  filepath:{filepath}error:{_indexer.error_message}')
					fails.append(filepath)
					if len(fails)>100:
						break
				else:
					_indexer.post_process()
					result=_indexer.post_result
					if result==False:
						print(f'Fail:  filepath:{filepath}error:{_indexer.error_message}')
						fails.append(filepath)
						if len(fails)>100:
							break	
			except Exception as e:
				print(e)
	return fails

#
#[28/Dec/2020 21:10:49] DEBUG [ownsearch.indexsolr:257] post process result True
#[28/Dec/2020 21:10:49] INFO [ownsearch.watch_dispatch:615] Removed job CollectionExtract.24
#[28/Dec/2020 21:10:4fro9] DEBUG [ownsearch.tasks:73] Task over: terminating TaskWorker.CollectionExtract.24