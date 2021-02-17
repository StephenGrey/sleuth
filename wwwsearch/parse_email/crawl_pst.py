import os,re,tempfile
from documents import time_utils
from parse_email.email import alt_message_id, Email
import logging
try:
	log = logging.getLogger('ownsearch.crawlpst')
except:# prevent exception if used as stand alone outside Django
	log= logging.getLogger(__name__)
import win32com.client
from documents.file_utils import FileSpecs

IGNORE_FOLDERS=['Trash','Deleted Messages', 'Junk', 'Junk E-mail''Spam','Drafts','Sync Issues (This computer only)']

"""
PARSE THE EMAILS IN FOLDERS LOADED INTO AN ACTIVE OUTLOOK ACCOUNT

Windows Only // tested with Windows 10
Dependency: win32.com.client


Usage: 
from parse_email import crawl_pst as cp
o=cp.OutlookParser() 
i=cp.IndexParser(o.outlook,maxdepth=2) 
##TO DO : combine with email.py to send the parsed data to Solr



"""


class OutlookParser():
	"""Parse contents of Outlook folders"""
	def __init__(self):
		self.outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
		

	def parse(self,root=None,startdepth=0,maxdepth=2,rootname='Outlook',parse_items=False):
		ent=root if root else self.inbox 
		self._index=IndexParser(ent,depth=startdepth,maxdepth=maxdepth,rootname=rootname,parse=parse_items)

	def folders(self):
		return [(x.Name,x) for x in _folders(self.outlook)]
	
	def folder(self,name):
		return [o for n,o in self.folders() if n==name][0]
	
	@property
	def inbox(self):
		return self.outlook.GetDefaultFolder(6)
	
	@property
	def calendar(self):
		return self.outlook.GetDefaultFolder(9)
	# o.outlook.GetDefaultFolder(9).DefaultItemType==1
	
	@property
	def contacts(self):
		return self.outlook.GetDefaultFolder(10)
	#self.outlook.GetDefaultFolder(10).DefaultItemType==2

	def item_type(self,ent):
		return ent.DefaultItemType
		#0 is a message, 2 is a contact, 1 is a calendar item


class Index:
	"""an index of the folders - to a max depth"""
	def __init__(self,ent,depth=0,maxdepth=0,rootname='Outlook',parse=True,hash_attachments=False):
		self.hash_attachments=hash_attachments
		self.rootname=rootname
		self.ent=ent
		self.maxdepth=maxdepth
		self.file_index={}
		name=_attr(self.ent,'Name')
		if name in IGNORE_FOLDERS:
			log.info(f'Ignoring {rootname}')
			return
		else:
			log.info(f'Parsing: {name}')		
		_items=_attr(self.ent,'Items')
		count_items=_attr(_items,'Count')
		count_subfolders=_attr(self.ent.Folders,'Count')
		log.info(f"Depth:{depth}, Name: {name}, Items:{count_items}, Folders:{count_subfolders}")
		if depth==0 and parse: #parse items in the root
			self.parse_items()
			
		if depth<maxdepth:
			newdepth=depth+1
			for f in _folders(ent):
				try:
					_name=f.Name
				except:
					_name='UnknownFolder'
				foldername=os.path.join(rootname,_name)
				i=self._index(f,newdepth,rootname=foldername)
				if parse:
					i.parse_items()
	
	def _index(self,f,newdepth,rootname='Outlook'):
		return Index(f,depth=newdepth,maxdepth=self.maxdepth,rootname=rootname)
	
	def parse_items(self):
		"""override with some action"""
		#for i in _items(self.ent)
		print('pass')
		pass

class IndexParser(Index):
	""" parse the emails """
	def parse_items(self):
		print(f'parsing items in {self.ent.Name}')
		_count=0
		for msg in _items(self.ent):
			#print(f'MSG: {msg}')
			_count+=1
			if _count >5000:
				break
			item=Item(msg,rootname=self.rootname,hash_attachments=self.hash_attachments)
			item.parse()
			
			for meta in item.attachment_meta:
				_hash=meta.get('hash')
				if _hash and _hash in self.file_index:
					pass
					#print(f'Duplicate attachment: {meta} attached to message subject:{item.subject} Folder:{self.rootname}')
				else:
					self.file_index[_hash]=meta

	def _index(self,f,newdepth,rootname='Outlook'):
		return IndexParser(f,depth=newdepth,maxdepth=self.maxdepth,rootname=rootname)
	

class Item(Email):
	"""an individual Outlook message, with parse method"""
	def __init__(self,raw,rootname=None,hash_attachments=False):
		self.raw=raw
		self.rootname=rootname
		self.hash_attachments=hash_attachments
		self.filepath=None

	def _attr(self,attr):
		return getattr(self.raw,attr,None)
	
	def parse(self):
		try:
			self.message_type=self._attr("MessageClass")
			self.body=self._attr("Body")
			self.to=self._attr("To")
			self.cc=self._attr("CC")
			self.organiser=self._attr("Organiser")
			self.start=self._attr("Start")
			self.end=self._attr("End")
			self.location=self._attr("Location")
			self.required=self._attr("Required")
			self.importance=self._attr("Importance")
			self.subject=self._attr("Subject")
			self.body=self._attr("Body")
			self.recipients=self._attr("Recipients")
			self.sender=self._attr("Sender.Name")
			self.sender_address=self._attr("Sender.Address")
			self.conversationID=self._attr("ConversationID")
			self.conversationindex=self._attr("ConversationIndex")
			self.sender_email=self._attr("SenderEmailAddress")
			self.sender_name=self._attr("SenderName")
			self.size=self._attr("Size")
			self.last_mod=self._attr("LastModificationTime")
			self.entryID=self._attr("EntryID")
			self.body_format=self._attr("BodyFormat")
			self.attachments=self._attr("Attachments")
			self._header=self.get_header
			
			if self.message_type =='IPM.Appointment' and self.start:
				self.date=self.start
			
			self.content_enhance() #compose text from body and other details for contacts, appointments			
			self.message_id=self.get_message_id
			self.check_attachments()
	
				
#			if self.attachment_count>0:
#				log.info(self.attachment_summary)
			
		except AttributeError as e:
			log.error(self.raw.__dict__)
			log.error(self.__dict__)
			log.error(e)
	
	@property
	def get_header(self):
		"""pull the header"""
		try:
			return self.raw.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x007D001F")
		except:
			return None

	@property
	def get_message_id(self):
		"""parse the header to find the Message ID"""
		try:
			_id=self.raw.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x1035001F")
		except:
			_id=None
		if  _id:
			return _id
		elif self._header:
			try:
				_id_line=[x for x in self._header.split('\n') if x.startswith('Message-ID') or x.startswith('Message-Id')]
				_id=re.match('Message-I[D|d]:.*(<.*>)',_id_line[0])[1]
				if _id:
					return _id
			except Exception as e:
				#log.debug(self._header)
				#log.debug(e)
				pass
		_id=self.make_alt_id()
		return _id
		

		
	def check_attachments(self):
		self.attachment_count=self.raw.Attachments.Count
		self.attachment_meta=[]
		if self.attachment_count:
			self.attachment_summary="""
			==================================
			ATTACHMENTS:
			"""
		else:
			self.attachment_summary=''
		try:
			for att in self.raw.Attachments:
				meta={}
				meta['name']=att.DisplayName
				meta['size']=att.Size
				meta['filename']=att.FileName
				meta['index']=att.Index
				if self.hash_attachments:
					try:
						with tempfile.TemporaryDirectory() as tmpdirname:
							temppath=os.path.join(tmpdirname,meta['filename'])
							att.SaveAsFile(temppath)
							specs=FileSpecs(temppath,scan_contents=True)
							meta['hash']=specs.contents_hash
							meta['last_modified']=specs.last_modified
							#os.remove(temppath)
					except Exception as e:
						log.error(e)
						log.error(f'Failure on {meta}')
				self.attachment_meta.append(meta)
				small_hash=meta.get('hash',"         ")[-8]
				self.attachment_summary+=(f"""
{meta['name']}: {meta['size']} bytes, hash: {small_hash} """)
				if self.attachment_summary:
					self.attachment_summary+="============================"
		except Exception as e:
			log.error(e)




#all properties	[msg.ItemProperties(n).Name for n in range(90)]
def parse(ent):
		"""standalone parse for testing"""
		_count=0
		for msg in ent.Items:
#			_count+=1
#			if _count >5:
#				break
			print(msg)
			atts=[x for x in msg.Attachments]
			print(len(atts))
			if len(atts)>0:
				return msg
				

def _folders(ent):
	"""return a generator of sub folders"""
	for f in ent.Folders:
		yield f

def _items(ent):
	"""return a generator of items in a folder"""
	for i in ent.Items:
		yield i

def _contents(ent):
	"""return 2 geneators - one of folders , one of items"""
	yield (_folders(ent),_items(ent))
	
def _attr(obj,attr):
	"""fill missing attributes with None rather than raising exceptions"""
	try:
		return getattr(obj,attr,None)
	except AttributeError:
		return None
		
def __main__():
	pass
		
##https://docs.microsoft.com/en-us/dotnet/api/microsoft.office.interop.outlook.mailitem?redirectedfrom=MSDN&view=outlook-pia#properties_