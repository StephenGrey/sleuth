import emlx,tempfile,logging,os,sys,traceback
from documents import time_utils
from documents.file_utils import get_contents_hash
from .email import Email,DEFAULT_CORE,DOCSTORE
log = logging.getLogger('ownsearch.eml')
from documents.models import Collection,File
from documents.updateSolr import check_hash_in_solrdata
from documents import indexSolr

class EMLX(Email):
	
	def __init__(self,path,extract_attachments=True,sourcetext='Not known',mycore=DEFAULT_CORE,docstore=DOCSTORE,level=0,in_memory=False,root_id=None,parent_id=None):
		self.filepath=path
		
		if self.filepath.startswith("\\\\?\\"):
			self.shortpath=self.filepath[4:]
		else:
			self.shortpath=self.filepath
		
		self.msg = emlx.read(self.filepath)
		self.extract_attachments=extract_attachments
		self.docstore=docstore
		self.sourcetext=sourcetext
		self.level=level
		self.mycore=mycore
		self.result=None
		self.error_message=None	
		self.in_memory=in_memory
		self.attachment_list=[]
		self.root_id=root_id
		self.parent_id=parent_id
		self.get_specs()
	
	def parse(self):
		
		self.title=self.msg.headers.get('Subject')
		self.content_type=["message/rfc822"]
		self._from=self.msg.headers.get('From')
		self.sender_address=None
		
		self.to=self.msg.headers.get('To')
		self.recipient_emails=None
		self.cc=self.msg.headers.get('CC')
		self.bcc=self.msg.headers.get('BCC')
		self.message_id=self.msg.headers.get('Message-ID')
		
		self.last_mod=self.msg.plist.get('date-last-viewed')
		self.creation_time=self.msg.plist.get('date-received')
		if self.last_mod:
			self.date=time_utils.timestamp2aware(self.last_mod)
		else:
			self.date=time_utils.timestamp2aware(self.creation_time)
		self.thread_id=self.msg.plist.get('conversation-id')
		self.attachment_count=self.msg.plist['flags'].get('attachment_count')
		self.priority=self.msg.plist['flags'].get('priority_level')
		self.junk=self.msg.plist['flags'].get('is_not_junk')
		
		self.attachments_exist=True if self.attachment_count else False

		self.author=self._from
		self.sender=self._from
		self.subject=self.title
		
		self.originating_ip=self.msg.headers.get('x-originating-ip')
		self.html=self.msg.html
		if self.msg.text:
			self.body=self.msg.text
		elif self.msg.html:
			self.body=self.msg.html
		self.index_text=self.body
		self.text=self.body

	
	
	def emit_attachments(self):
		"""index attachments, if not already there"""
		log.info('extracting attachments')
				
		#put file attachments into a temporary folder and extract
		try: #to do catch exceptions
			with tempfile.TemporaryDirectory() as tmpdirname:
				log.debug('created temporary directory', tmpdirname)
				self.save_attachments(tmpdirname)
				for x in os.listdir(tmpdirname):
					log.info(f'Attempting to index attachment: {x}')
					path=os.path.join(tmpdirname,x)
					_hash=get_contents_hash(path,blocksize = 65536)
					self.attachment_list.append(f'"{x}","{_hash}"')
					if _hash:
						existing=check_hash_in_solrdata(_hash,self.mycore)
						if existing:
							log.info('Attachment exists already in the index')
						else:
							ext=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext=self.sourcetext,docstore=tmpdirname,test=False,ocr=True,meta_only=False,check=True,retry=False,level=self.level+1)
							self.add_attachment_meta(x,_hash,self.level+1,self.contents_hash)
				
		except Exception as e:
			log.error(e)
				
				
	def save_attachments(self,targetfolder):
		"""dump attachments into a folder"""

		for part in self.msg.walk():
			ctype=part.get_content_type()
			disp=part.get('Content-Disposition')
			if not disp:
				continue
			filename=part.get_filename()
			fullpath=os.path.join(targetfolder,filename)
			with open(fullpath, 'wb') as fp:
				log.info(f'saving attachment to {fullpath}')
				fp.write(part.get_payload(decode=True))
				
			

#fp = open('test.mov', 'wb')
#fp.write(part.get_payload(decode=True))

def check_collection(_id,mycore,sourcetext=""):
	collection=Collection.objects.get(id=_id)
	_files=File.objects.filter(collection=collection,fileext='.emlx')
	indexed=0
	for f in _files:
#		if True:
		if f.filename.startswith('.'):
#			pass
#		else:
			res=indexSolr.check_file_in_solrdata(f,mycore)
			if res:
				if res.date:
					log.info(f'Date records exists for {f.filepath} with solrid: {f.solrid}')
					continue
			try:
				res=indexSolr.ExtractFile(f.filepath,mycore,retry=True,sourcetext=sourcetext,docstore=indexSolr.DOCSTORE)
				if res.result:
					log.info(f'Succesful extract of {f.filepath} with solrid: {f.solrid}')
					indexed+=1
			except Exception as e:
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_exc(limit=4, file=sys.stdout)
				log.error(e)
				log.error(f'Error with : {f.filepath} with solrid: {f.solrid}')
	print(f'Indexed total of {indexed} files')
