import os
from .email import Email
from msglite import Message
#import extract_msg


def crawler(parent_folder):
		for dirName, subdirs, fileList in os.walk(parent_folder): #go through every subfolder in a folder
			for filename in fileList: #now through every file in the folder/subfolder
				path = os.path.join(dirName, filename)
				yield path 
 
 
def check_email(folder):
	errors=[]
	for path in crawler(folder):
		try:
			#msg = Message(path)
			#print(msg.subject )
			#print(msg.body
			#msg2=extract_msg.Message(path)
			
			msg=Email(path)
			msg.process()
			
			
		except Exception as e:
			print(e)
			print(f'Error with {path}')
			errors.append((path,e))
		
		print(errors)
		