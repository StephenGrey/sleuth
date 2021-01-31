import os,re
import logging
try:
	log = logging.getLogger('ownsearch.crawlpst')
except:# prevent exception if used as stand alone outside Django
	log= logging.getLogger(__name__)
import win32com.client

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

	def folders(self):
		return [(x.Name,x) for x in _folders(self.outlook)]
	
	def folder(self,name):
		return [o for n,o in self.folders() if n==name][0]


class Index:
	"""an index of the folders - to a max depth"""
	def __init__(self,ent,depth=0,maxdepth=0):
		self.ent=ent
		self.maxdepth=maxdepth
		name=_attr(self.ent,'Name')
		_items=_attr(self.ent,'Items')
		count_items=_attr(_items,'Count')
		count_subfolders=_attr(self.ent.Folders,'Count')
		print(f"Depth:{depth}, Name: {name}, Items:{count_items}, Folders:{count_subfolders}")

		if depth<maxdepth:
			newdepth=depth+1
			for f in _folders(ent):
				i=self._index(f,newdepth)
				i.parse_items()
	
	def _index(self,f,newdepth):
		return Index(f,depth=newdepth,maxdepth=self.maxdepth)
	
	def parse_items(self):
		"""override with some action"""
		#for i in _items(self.ent)
		print('pass')
		pass

class IndexParser(Index):
	""" parse the emails """
	def parse_items(self):
		_count=0
		for msg in _items(self.ent):
			#print(f'MSG: {msg}')
			_count+=1
			if _count >50:
				break
			item=Item(msg)
			item.parse()

	def _index(self,f,newdepth):
		return IndexParser(f,depth=newdepth,maxdepth=self.maxdepth)
	

class Item():
	"""an individual Outlook message, with parse method"""
	def __init__(self,raw):
		self.raw=raw

	def _attr(self,attr):
		return getattr(self.raw,attr,None)
	
	def parse(self):
		try:
			self.body=self._attr("Body")
			self.to=self._attr("To")
			self.cc=self._attr("CC")
			self.importance=self._attr("Importance")
			self.subject=self._attr("Subject")
			self.body=self._attr("Body")
			self.recipients=self._attr("Recipients")
			self.sender=self._attr("Sender")
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
			self.message_id=self.get_message_id
		
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
				return _id
			except Exception as e:
				#log.debug(self._header)
				#log.debug(e)
				pass
		return None
		
#all properties	[msg.ItemProperties(n).Name for n in range(90)]
def parse(ent):
		"""standalone parse for testing"""
		_count=0
		for msg in ent.Items:
#			_count+=1
#			if _count >5:
#				break
			item=Item(msg)
			item.parse()

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