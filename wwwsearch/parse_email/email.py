import os,json,collections,logging,hashlib,tempfile
from documents import time_utils
from documents.file_utils import FileSpecs,make_relpath,parent_hash, get_contents_hash
from documents.updateSolr import post_jsondoc,check_hash_in_solrdata,make_atomic_json,post_jsonupdate
from ownsearch.solrJson import search_meta
from documents import indexSolr
from msglite import Message,Attachment
import unicodedata
import extract_msg

from ownsearch.solrJson import SolrCore
log = logging.getLogger('ownsearch.email')

try:
	from documents.indexSolr import DOCSTORE
except:
	DOCSTORE=''

#Parts of this code incorporated from Aleph code base
TIME_CONSTANTS={
"SENT":['0039'],
"RECEIVED":['0E06'],
"CREATION_TIME":['3007'],
"LAST_MODIFIED":['3008'],
"END":['8004','8006','0061','8015'],
"START":['0060','8003','8005','800B','8014'],
"REMINDER":['8013'],
"REPLY_TIME":['8033'],
}

DEFAULT_CORE=SolrCore('tests_only')

class LightMessage(Message):
    """ignore attachments completely"""
    def parseAttachments(self):
        return None

class LazyMessage(Message):
	"""Not very strict parser! Parse a message even if some attachments fail"""
	
	def parseAttachments(self):
		""" Returns a list of all attachments. """
		
		attachments = []
		for path in self.list_paths():
			if path.startswith("__attach"):
				try:
					attachments.append(Attachment(self, path))
				except TypeError as e:
					log.warning('Could not parse attachment in message %s',self.path)
					self.error_message='Skipped attachment on type error'
				except Exception as e:
					log.warning ('Could not parse an attachment in message %s',self.path)
					log.debug(e)
					self.error_message='Skipped attachment on unknown error'
		return attachments


class Email():
	"""parse an Outlook .msg file and index it to solr index"""
	def __init__(self,filepath,sourcetext='Not known',mycore=DEFAULT_CORE,docstore=DOCSTORE,extract_attachments=True,level=0,in_memory=False,root_id=None,parent_id=None):
		self.docstore=docstore
		self.error_message=None
		self.extract_attachments=extract_attachments
		self.result=None
		self.filepath=filepath
		self.sourcetext=sourcetext
		self.level=level
		self.mycore=mycore
		self.error_message=None
		self.in_memory=in_memory
		self.attachment_list=[]
		self.root_id=root_id
		self.parent_id=parent_id
		self.get_specs()

	def get_specs(self):
		specs=FileSpecs(self.filepath)###
		self.filename=specs.name
		try:
			self.parent_folder=make_relpath(specs.parent_folder,docstore=self.docstore)
			self.relpath=make_relpath(self.filepath,docstore=self.docstore)
		except ValueError:
			self.parent_folder=specs.parent_folder
			self.relpath="Failed relpath"
		self.size=specs.length

		self.contents_hash=specs.contents_hash
		if not self.root_id:
			if self.level==0:
				self.root_id=self.contents_hash
			else:
				self.root_id=None
		
		if self.mycore.parenthashfield:
			self.parenthash=parent_hash(self.relpath)

	def process(self):
		"""parse and then extract, catching errors"""
		try:
			self.parse()
		#	log.debug(self.__dict__)
		except Exception as e:
			self.error_message=f'Cannot parse {self.filepath} Exception: {e}'
			log.error(self.error_message)
			return
		try:
			self.extract()
		except Exception as e:
			self.error_message=f'Cannot extract {self.filepath}. Exception: {e}'
			log.error(self.error_message)
			return
	
	def parse(self):
		"""parse fields from message"""
		if self.extract_attachments:
			#if email is in memory & not a file then add to object before coming here
			if not self.in_memory:
				self.parsed=LazyMessage(self.filepath)
				try:
					self.error_message=self.parsed.error_message
				except:
					pass
		else:
			self.parsed=LightMessage(self.filepath)
			self.error_message=None
		#log.info(self.parsed.header._headers)
		self.parse_times() #extract all the different times
		
		self.attachments_exist=True if self.parsed.attachments else False
		self.title=self.parsed.subject
		self._from=self.parsed.header.get('From')
		self.to=self.parsed.header.get('To')
		self.author=self._from
		self.bcc=self.parsed.bcc
		self.recipient_emails=[x.email for x in self.parsed.recipients]
		self.senders=self.parsed.senders
		self.cc=self.parsed.cc
		self.sender=self.parsed.getStringField("0C1A")
		self.sender_address=self.parsed.getStringField("0C1F")
		self.subject=self.parsed.subject
		self.thread_id=self.parsed.header.get('Thread-Index')
		self.content_type=self.parsed.header.get('Content-Type')
		self.message_id=self.parsed.header.get('Message-ID')
		self.originating_ip=self.parsed.header.get('x-originating-ip')
		self.location=self.parsed.getStringField("800D")
		if not self.location:
			self.location=self.parsed.getStringField("800A")
		self.required=self.parsed.getStringField("0E04")
		self.organiser=self.parsed.getStringField("0042")
		self.start=self.time_props.get('START')
		self.end=self.time_props.get('END')
		self.last_mod=self.time_props.get('LAST_MODIFIED')
		self.creation_time=self.time_props.get('CREATION_TIME')
				
		self.message_type=self.parsed.getStringField("001A")
		self.content_type=["application/vnd.ms-outlook"]
		self.body=self.parsed.body
		self.index_text=self.body
		
		try:
			self.date=time_utils.parse_time(self.parsed.date)
		except:
			self.date=None

		if self.message_type =='IPM.Appointment' and self.start:
			self.date=self.start
		
		self.content_enhance() #compose text from body and other details for contacts, appointments
		if not self.message_id:
			self.message_id=self.make_alt_id()
			

	
	def make_alt_id(self):
		"""substitute a message ID if not exists"""
		try:
			_time=self.date
		except:
			_time=None
		text2hash=self.text if self.text else self.contents_hash
		_sender=next(item for item in [self.sender_address,self.sender,"@Unknown_source"] if item)
		
		if not _time or not text2hash or not _sender:
			log.debug(f'Making alternate for {self.filepath} with missing value. time:{_time},{text2hash[:20]+"..."},{_sender}')
		return alt_message_id(_time,text2hash,_sender)

	
	def parse2(self):
		"""parse fields using msg_parser app"""
		self.parsed=extract_msg.Message(self.filepath)
		self.content_type=["application/vnd.ms-outlook"]
		self.body=self.parsed.body
		self.text=self.body #remove_control_characters(self.body)
		self.date=self.parsed.date
		self.title=self.parsed.subject
		self._from=self.parsed.header.get('From')
		self.to=self.parsed.header.get('To')
		self.author=self._from
		self.subject=self.parsed.subject
		self.message_id=self.parsed.header.get('Message-ID')
		self.thread_id=self.parsed.header.get('Thread-Index')
		self.content_type=self.parsed.header.get('Content-Type')
		
	def parse_times(self):
		self.time_props={}
		for key,prop_list in TIME_CONSTANTS.items():
			try:
				for prop in prop_list:
					try:
						val=clean_time(self.parsed.mainProperties.get(prop+'0040').value)
						if val:
							self.time_props[key]=val
							break
					except:
						pass
			except Exception as e:
				log.error(e)
				log.error(prop)
	
	def save_attachments(self,target_folder):
		"""dump attachments into a folder"""
		for attach in self.parsed.attachments:
			try:
				if attach.type !='msg':
					open(os.path.join(target_folder,attach.longFilename),'wb').write(attach.data)
			except Exception as e:
				log.error(e)
				log.error(f'target_folder: {target_folder}, filename:{attach.longFilename}, attachment:{attach.__dict__}')
	
	
	def content_enhance(self):
		"""add content to text for indexing and display"""
		if self.message_type =='IPM.Appointment':
			self.text=f'Appointment: \n{self.subject}\nOrganiser: {self.organiser}\nTime: FROM: {self.start} TO: {self.end}\nLocation: {self.location}\nText: {self.body}'
			self.index_text=self.text
		elif self.message_type=='IPM.Contact':
			self.text='Contact: \nText: {self.body}'
			self.index_text=self.text
		else:
			self.text=self.body #remove_control_characters(self.b ody)
	
	
	def extract(self):
		"""index the email"""

		if self.in_memory:
			self.solr_id=self.message_id
		else:
			self.solr_id=self.contents_hash
		
		#first deal with attachments
		if self.extract_attachments and self.attachments_exist:
			self.emit_attachments()
		log.debug(self.attachment_list)					#TODO remove
		doc=collections.OrderedDict()  #keeps the JSON file in a nice order
		

		doc[self.mycore.unique_id]=self.solr_id
		if self.mycore.hashcontentsfield != self.mycore.unique_id:
			doc[self.mycore.hashcontentsfield]=self.contents_hash #also store hash in its own standard field
		doc[self.mycore.rawtext]=self.text
		doc['preview_html']=self.body
		doc['content_type']=self.content_type
		doc[self.mycore.sourcefield]=self.sourcetext
		if self.date:
			doc[self.mycore.datefield]=time_utils.ISOtimestring(self.date)	
		doc['title']=self.title
		doc['message_from']=self._from
		doc["message_from_email"]=self.sender_address
		doc['message_cc']=self.cc
		doc["message_cc_email"]=""
		doc['message_to']=self.to
		doc["message_to_email"]=self.recipient_emails
		doc["message_bcc"]=self.bcc
		doc["attachment_list"]=self.attachment_list
		doc['author']=self.author
		doc['subject']=self.subject
		doc['extract_parent_paths']=[self.parent_folder]
		doc['extract_level']=[f"{self.level}"]
		doc['message_raw_header_message_id']=self.message_id
		doc["message_raw_header_thread_index"]=self.thread_id
		doc["message_raw_header_x_originating_ip"]=self.originating_ip
		
		if self.parent_id:
			doc["extract_parent_id"]=self.parent_id
		if self.root_id:
			doc["extract_root"]=self.root_id
		
		doc[self.mycore.docnamesourcefield]=self.filename
		doc[self.mycore.docpath]=self.relpath
		doc[self.mycore.parenthashfield]=self.parenthash
		doc[self.mycore.docsizesourcefield1]=self.size
		doc['sb_meta_only']=False
		log.info(f' Indexing: {self.filepath}with id:  {self.contents_hash}')
		#log.debug(doc)
		post_result,status=self._index(doc)
		self.result=status
		if not status:
			log.info(post_result)
			self.error_message=post_result
		return
	
	
	def add_attachment_meta(self,filename,_hash,level,parent_id):
		doc={}  #keeps the JSON file in a nice order
#		doc[self.mycore.unique_id]=_hash
		doc[self.mycore.sourcefield]=self.sourcetext
		doc[self.mycore.docnamesourcefield]=filename
		doc[self.mycore.docpath]=self.relpath	#keep original root file as the path
		doc[self.mycore.parenthashfield]=self.parenthash
#       "extract_paths":["/Users/Stephen/Code/Sleuth/wwwsearch/tests/testdocs/msg/test_with_attachment.msg"],
		doc['extract_parent_paths']=[self.parent_folder]
		doc['extract_level']=[f"{level}"]
		doc['extract_parent_id']=[parent_id]
		doc['extract_root']=[self.contents_hash]
		doc['sb_source']=["some source"]
		doc['sb_meta_only']=False
		data=make_atomic_json(_hash,doc,self.mycore.unique_id)
		response,poststatus=post_jsonupdate(data,self.mycore,test=False,check=True)
		log.debug('Response: {} PostStatus: {}'.format(response,poststatus))
#		post_result,status=self._index(doc)
#		if not status:
#			log.info(post_result)
#			self.error_message=post_result
#		return		
		

	def emit_attachments(self):
		"""index attachments in solr, if not already there"""
		log.info('extracting attachments')
		
		if self.level>3:
			print('max level stop')
			return
		
		#put file attachments into a temporary folder and extract
		try: #to do catch exceptions
			with tempfile.TemporaryDirectory() as tmpdirname:
				print('created temporary directory', tmpdirname)
				self.save_attachments(tmpdirname)
				for x in os.listdir(tmpdirname):
					log.info(f'Attempting to index attachment: {x}')
					path=os.path.join(tmpdirname,x)
					_hash=get_contents_hash(path,blocksize = 65536)
					self.attachment_list.append((x,_hash))
					if _hash:
						existing=check_hash_in_solrdata(_hash,self.mycore)
						if existing:
							log.info('Attachment exists already in the index')
						else:
							ext=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='',docstore=tmpdirname,test=False,ocr=True,meta_only=False,check=True,retry=False,level=self.level+1)
							self.add_attachment_meta(x,_hash,self.level+1,self.contents_hash)
		except Exception as e:
			log.error(e)
			
		#deal with messages attached to messag
		for attach in self.parsed.attachments:
			#log.info(attach.__dict__)
			if attach.type=='msg':
				
				msg=Email(self.filepath,sourcetext=self.sourcetext,mycore=self.mycore,docstore=self.docstore,extract_attachments=self.extract_attachments,level=self.level+1,in_memory=True,root_id=self.root_id,parent_id=self.solr_id)
				msg.parsed=attach.data
				msg.parse()
				if msg.message_id:
					previous=search_meta("message_raw_header_message_id",msg.message_id,self.mycore)
				else:
					log.info('No message id stored')
					previous=None
				if previous:
					log.info('Attachment message {msg.message_id} already indexed')
					try:
						doc_id=previous[0].id
						self.attachment_list.append((f'EmailMessage: {msg.subject}',doc_id))
						continue
					except Exception as e:
						log.error(e)
				else:
					msg.extract()
					self.attachment_list.append((f'EmailMessage: {msg.subject}',msg.message_id))
		

	

		"""other fields that could be added"""
#        "subject":["Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule"],
#        "message_to":["Hilton, Joy (Palmer)"],
#        "message_raw_header_message_id":"<B7EE98A869777C49ACF006A8AA90665C0EDFE311@HZNGRANMAIL2.granite.nhroot.int>",
#        "last_modified":["2016-02-04T15:29:28Z"],
#        "content_length":[71680],
#        "author":["Wood, Tracy"],
#        "message_from":"Wood, Tracy",
#        "resourcename":["2016-02-04 email to FW Newport AOC 15-020 WD - Fuss  O'Neill Draft Scope of Work  Schedule-NHDES comments.msg"],
#        "message_raw_header_x_originating_ip":"[10.6.13.20]",
#        "message_raw_header_thread_index":"AdFfTWwWhtwyaqseQwS87vZU25Z7AQACrM7wAAIsEVA=",
#        "title":["FW: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule"],
#        "message_from_email":"Tracy.Wood@des.nh.gov",
#        "content_type":["application/vnd.ms-outlook"],
#        "message_to_display_name":["Hilton, Joy (Palmer)"],
#        "extract_id":"38f3c0bd853aa49dc3963050633e93c8382c9a435c43760b2fe4315d0d06d647",
#        "extract_base_type":["application/vnd.ms-outlook"],
#        "extract_paths":["mixed_folder/2016-02-04 email to FW Newport AOC 15-020 WD - Fuss  O'Neill Draft Scope of Work  Schedule-NHDES comments.msg"],
#        "extract_parent_paths":["/Users/Stephen/Code/Sleuth/wwwsearch/tests/testdocs/mixed_folder"],
#        "extract_level":["0"],
#        "tika_content":["FW: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\tFrom\n\tWood, Tracy\n\tTo\n\tHilton, Joy (Palmer)\n\tRecipients\n\tHilton.Joy@epa.gov\n\nFYI.\n\n\n\n \n\n\n\nFrom: Jeffrey McDonald [mailto:JMcDonald@fando.com] \nSent: Thursday, February 04, 2016 9:28 AM\nTo: Wood, Tracy; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: RE: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nThank you, this is very helpful!\n\n\n\n \n\n\n\nJeff McDonald, PE\nAssociate\nFuss & O'Neill, Inc | | \n860.646.2469 x5339 | jmcdonald@fando.com | cell: 802.324.7720 \nwww.fando.com | twitter | facebook | linkedin\n\n\n\nFrom: Wood, Tracy [mailto:Tracy.Wood@des.nh.gov] \nSent: Thursday, February 04, 2016 8:11 AM\nTo: Jeffrey McDonald; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nPaul/Jeff/Rene,\n\n\n\n \n\n\n\nThank you for coming to DES last Thursday, January 28th to present the Draft Scope of Work for Newport’s Facilities Plan update.  DES has had the opportunity to review the Draft Scope of Work and offers the following comments:\n\n\n\n \n\n\n\nProject Understanding\n\n\n\n·         EPA AO 09-015 issued on March 6, 2009 was not “subsequently amended” but superseded by DES AOC 15-020 WD on September 1, 2015.  Revise first paragraph accordingly.\n\n\n\n·         Item c) states to perform pilot testing of up to two (2) preferred alternatives.  If additional pilot testing is determined to be necessary it is expected that the Town will undergo additional pilot testing as necessary.\n\n\n\nScope of Services\n\n\n\n·         2)f) Existing and projected flow.  Keep in mind that if the new WWTF will have an average daily design flow greater than 1.3 mgd, then Newport will have to address anti-degradation.\n\n\n\n·         3)d)vi) Present and proposed future discharge permits.  Please contact Ellen Weitzler (Weitzler.Ellen@epa.gov, tel. no. 617-918-1582) of EPA Region 1 to initiate discussion of  future discharge permits.  \n\n\n\nSchedule\n\n\n\n·         Meets the December 31, 2017 requirement of Section E.1. of DES AOC 15-020 WD to submit an updated facility plan with implementation schedule for final recommended alternative to upgrade Newport WWTF to meet its 2007 NPDES permit limits. \n\n\n\nIf you have any questions or comments please do not hesitate to contact me.\n\n\n\n \n\n\n\nThank you,\n\n\n\n-Tracy\n\n\n\n \n\n\n\nTracy L. Wood, PE, Administrator\n\n\n\nWastewater Engineering Bureau, NHDES\n\n\n\n29 Hazen Drive, PO Box 95, Concord, NH 03302\n\n\n\nTel: (603) 271-2001  |  Fax: (603) 271-4128\n\n\n\n \n\n\n\n\n\n\n"],
#        "sb_source":["Test source"],
#		        "message_to_email":["Hilton.Joy@epa.gov"],
#        "subject":["Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule"],
#        "message_to":["Hilton, Joy (Palmer)"],
#        "message_raw_header_message_id":"<B7EE98A869777C49ACF006A8AA90665C0EDFE311@HZNGRANMAIL2.granite.nhroot.int>",
#        "last_modified":["2016-02-04T15:29:28Z"],
#        "content_length":[71680],
#        "author":["Wood, Tracy"],
#        "message_from":"Wood, Tracy",
#        "resourcename":["2016-02-04 email to FW Newport AOC 15-020 WD - Fuss  O'Neill Draft Scope of Work  Schedule-NHDES comments.msg"],
#        "message_raw_header_x_originating_ip":"[10.6.13.20]",
#        "message_raw_header_thread_index":"AdFfTWwWhtwyaqseQwS87vZU25Z7AQACrM7wAAIsEVA=",
#        "title":["FW: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule"],
#        "message_from_email":"Tracy.Wood@des.nh.gov",
#        "content_type":["application/vnd.ms-outlook"],
#        "message_to_display_name":["Hilton, Joy (Palmer)"],
#        "extract_id":"38f3c0bd853aa49dc3963050633e93c8382c9a435c43760b2fe4315d0d06d647",
#        "extract_base_type":["application/vnd.ms-outlook"],

#        "extract_level":["0"],
#        "tika_content":["FW: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\tFrom\n\tWood, Tracy\n\tTo\n\tHilton, Joy (Palmer)\n\tRecipients\n\tHilton.Joy@epa.gov\n\nFYI.\n\n\n\n \n\n\n\nFrom: Jeffrey McDonald [mailto:JMcDonald@fando.com] \nSent: Thursday, February 04, 2016 9:28 AM\nTo: Wood, Tracy; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: RE: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nThank you, this is very helpful!\n\n\n\n \n\n\n\nJeff McDonald, PE\nAssociate\nFuss & O'Neill, Inc | | \n860.646.2469 x5339 | jmcdonald@fando.com | cell: 802.324.7720 \nwww.fando.com | twitter | facebook | linkedin\n\n\n\nFrom: Wood, Tracy [mailto:Tracy.Wood@des.nh.gov] \nSent: Thursday, February 04, 2016 8:11 AM\nTo: Jeffrey McDonald; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nPaul/Jeff/Rene,\n\n\n\n \n\n\n\nThank you for coming to DES last Thursday, January 28th to present the Draft Scope of Work for Newport’s Facilities Plan update.  DES has had the opportunity to review the Draft Scope of Work and offers the following comments:\n\n\n\n \n\n\n\nProject Understanding\n\n\n\n·         EPA AO 09-015 issued on March 6, 2009 was not “subsequently amended” but superseded by DES AOC 15-020 WD on September 1, 2015.  Revise first paragraph accordingly.\n\n\n\n·         Item c) states to perform pilot testing of up to two (2) preferred alternatives.  If additional pilot testing is determined to be necessary it is expected that the Town will undergo additional pilot testing as necessary.\n\n\n\nScope of Services\n\n\n\n·         2)f) Existing and projected flow.  Keep in mind that if the new WWTF will have an average daily design flow greater than 1.3 mgd, then Newport will have to address anti-degradation.\n\n\n\n·         3)d)vi) Present and proposed future discharge permits.  Please contact Ellen Weitzler (Weitzler.Ellen@epa.gov, tel. no. 617-918-1582) of EPA Region 1 to initiate discussion of  future discharge permits.  \n\n\n\nSchedule\n\n\n\n·         Meets the December 31, 2017 requirement of Section E.1. of DES AOC 15-020 WD to submit an updated facility plan with implementation schedule for final recommended alternative to upgrade Newport WWTF to meet its 2007 NPDES permit limits. \n\n\n\nIf you have any questions or comments please do not hesitate to contact me.\n\n\n\n \n\n\n\nThank you,\n\n\n\n-Tracy\n\n\n\n \n\n\n\nTracy L. Wood, PE, Administrator\n\n\n\nWastewater Engineering Bureau, NHDES\n\n\n\n29 Hazen Drive, PO Box 95, Concord, NH 03302\n\n\n\nTel: (603) 271-2001  |  Fax: (603) 271-4128\n\n\n\n \n\n\n\n\n\n\n"],
#        "sb_source":["Test source"],
#		
		
	def _index(self,doc):
		"""index to solr"""
		jsondoc=json.dumps([doc])
		result,status=post_jsondoc(jsondoc,self.mycore)
		return result,status
		
		

def alt_message_id(last_mod,body,sender_email):
	"""make a message ID for when none exists"""
	_time=time_utils.condensed_timestring(last_mod)
	_hash=hashlib.md5(body.encode('utf-8')).hexdigest()[-8:]
	_sender=sender_email
	return _time+_hash+_sender



def remove_control_characters(s):
	return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")


def msgEpoch(inp):
	return (inp - 116444736000000000) / 10000000.0

def clean_time(inp):
	return time_utils.timefromstamp(msgEpoch(inp))


def parse_times(msg):
	time_props={}
	props=msg.parsed.mainProperties.keys()
	time_props=[x for x in props if x[-3:]=='040']
	if True:
		for prop in time_props:
			
			try:
				val=clean_time(msg.parsed.mainProperties.get(prop).value)
				print(f'Property: {prop} Value: {val}')
			except AttributeError as e:
				pass
			except Exception as e:
				log.error(e)
				log.error(prop)


def parse_strings(msg):
	props=msg.parsed.mainProperties.keys()
	s_props=[x for x in props if x[-3:]=='01F']
	if True:
		for prop in s_props:
			print(prop)
			try:
#				val=msg.parsed.mainProperties.get(prop).value
#				print(f'Property: {prop} Value: {val}')
				print(msg.parsed.getStringField(prop[:4]))
			except AttributeError as e:
				pass
			except Exception as e:
				log.error(e)
				log.error(prop)
#

"""

040 data type - time - use MsgEpoch ton convert

"""