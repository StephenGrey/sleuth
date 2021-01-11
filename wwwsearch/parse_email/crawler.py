import os
from .email import Email
from msglite import Message
from documents import indexSolr,updateSolr
from ownsearch import solrJson

MYCORE=solrJson.SolrCore('tests_only')
DOCSTORE=indexSolr.DOCSTORE

#import extract_msg


def crawler(parent_folder):
		for dirName, subdirs, fileList in os.walk(parent_folder): #go through every subfolder in a folder
			for filename in fileList: #now through every file in the folder/subfolder
				path = os.path.join(dirName, filename)
				yield path 

def check_email_indexing(folder):
	errors=[]
	
	#ERASE EVERYTHING FROM TESTS_ONLY 
	res,status=updateSolr.delete_all(MYCORE)
	assert status is True
	
	for path in crawler(folder):
		try:
			#msg = Message(path)
			#print(msg.subject )
			#print(msg.body
			#msg2=extract_msg.Message(path)
			
			#msg=Email(path)
			#msg.process()
			extractor=indexSolr.ExtractFile(path,MYCORE,hash_contents='',sourcetext='Test source',docstore=DOCSTORE,retry=True)
			if not extractor.result:
				raise Exception(f"{extractor.error_message}")
		except Exception as e:
			print(e)
			print(f'Error with {path}')
			errors.append((path,e))
	print(f'Errors: {errors}')

def check_email_4errors(folder):
	errors=[]
	counter=1
	for path in crawler(folder):
		try:
			msg=Email(path)
			msg.parse()
			counter+=1
			if counter %100==0:
				print(f'Messages parsed: {counter}')
		except Exception as e:
			print(e)
			print(f'Error with {path}')
			errors.append((path,e))
	return errors
