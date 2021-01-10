import os,json,collections,logging
from documents import time_utils
from documents.file_utils import FileSpecs,make_relpath,parent_hash
from documents.updateSolr import post_jsondoc
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

DEFAULT_CORE=SolrCore('tests_only')


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
	def __init__(self,filepath,sourcetext='Not known',mycore=DEFAULT_CORE,docstore=DOCSTORE):
		self.docstore=docstore
		self.error_message=None
		self.result=None
		self.filepath=filepath
		self.sourcetext=sourcetext
		self.mycore=mycore
		specs=FileSpecs(self.filepath)###
		self.filename=specs.name
		self.relpath=make_relpath(self.filepath,docstore=self.docstore)
		self.size=specs.length
		self.contents_hash=specs.contents_hash
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
		self.parsed=LazyMessage(self.filepath)
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
	
	def parse2(self):
		"""parse fields using msg_parser app"""
		self.parsed=extract_msg.Message(self.filepath)
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
		
	
	
	def extract(self):
		"""index the email"""
		doc=collections.OrderedDict()  #keeps the JSON file in a nice order
		doc[self.mycore.unique_id]=self.contents_hash #using the hash of the HTML body as the doc ID
		if self.mycore.hashcontentsfield != self.mycore.unique_id:
			doc[self.mycore.hashcontentsfield]=self.contents_hash #also store hash in its own standard field
		doc[self.mycore.rawtext]=self.text
		doc['preview_html']=self.body
		doc[self.mycore.sourcefield]=self.sourcetext
		if self.date:
			doc[self.mycore.datefield]=time_utils.iso_parse(self.date)	
		doc['title']=self.title,
		doc['message_from']=self._from,
		doc['message_to']=self.to,
		doc['author']=self.author,
		doc['subject']=self.subject
		doc['extract_parent_paths']=[self.filepath]
		doc['extract_level']=["0"]
		doc['message_raw_header_message_id']=self.message_id
		doc[self.mycore.docnamesourcefield]=self.filename
		doc[self.mycore.docpath]=self.relpath
		doc[self.mycore.parenthashfield]=self.parenthash
		doc[self.mycore.docsizesourcefield1]=self.size
		doc['sb_meta_only']=False

		post_result,status=self._index(doc)
		self.result=status
		if not status:
			log.info(post_result)
			self.error_message=post_result
		return

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
#        "extract_paths":["mixed_folder/2016-02-04 email to FW Newport AOC 15-020 WD - Fuss  O'Neill Draft Scope of Work  Schedule-NHDES comments.msg"],
#        "extract_parent_paths":["/Users/Stephen/Code/Sleuth/wwwsearch/tests/testdocs/mixed_folder"],
#        "extract_level":["0"],
#        "tika_content":["FW: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\tFrom\n\tWood, Tracy\n\tTo\n\tHilton, Joy (Palmer)\n\tRecipients\n\tHilton.Joy@epa.gov\n\nFYI.\n\n\n\n \n\n\n\nFrom: Jeffrey McDonald [mailto:JMcDonald@fando.com] \nSent: Thursday, February 04, 2016 9:28 AM\nTo: Wood, Tracy; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: RE: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nThank you, this is very helpful!\n\n\n\n \n\n\n\nJeff McDonald, PE\nAssociate\nFuss & O'Neill, Inc | | \n860.646.2469 x5339 | jmcdonald@fando.com | cell: 802.324.7720 \nwww.fando.com | twitter | facebook | linkedin\n\n\n\nFrom: Wood, Tracy [mailto:Tracy.Wood@des.nh.gov] \nSent: Thursday, February 04, 2016 8:11 AM\nTo: Jeffrey McDonald; LaBranche, Rene; Paul J. Brown\nCc: Spanos, Stergios; Roberts, Steve; Kessler, Kenneth; Hilliard, Brian\nSubject: Newport AOC 15-020 WD - Fuss & O'Neill Draft Scope of Work & Schedule\n\n\n\n \n\n\n\nPaul/Jeff/Rene,\n\n\n\n \n\n\n\nThank you for coming to DES last Thursday, January 28th to present the Draft Scope of Work for Newport’s Facilities Plan update.  DES has had the opportunity to review the Draft Scope of Work and offers the following comments:\n\n\n\n \n\n\n\nProject Understanding\n\n\n\n·         EPA AO 09-015 issued on March 6, 2009 was not “subsequently amended” but superseded by DES AOC 15-020 WD on September 1, 2015.  Revise first paragraph accordingly.\n\n\n\n·         Item c) states to perform pilot testing of up to two (2) preferred alternatives.  If additional pilot testing is determined to be necessary it is expected that the Town will undergo additional pilot testing as necessary.\n\n\n\nScope of Services\n\n\n\n·         2)f) Existing and projected flow.  Keep in mind that if the new WWTF will have an average daily design flow greater than 1.3 mgd, then Newport will have to address anti-degradation.\n\n\n\n·         3)d)vi) Present and proposed future discharge permits.  Please contact Ellen Weitzler (Weitzler.Ellen@epa.gov, tel. no. 617-918-1582) of EPA Region 1 to initiate discussion of  future discharge permits.  \n\n\n\nSchedule\n\n\n\n·         Meets the December 31, 2017 requirement of Section E.1. of DES AOC 15-020 WD to submit an updated facility plan with implementation schedule for final recommended alternative to upgrade Newport WWTF to meet its 2007 NPDES permit limits. \n\n\n\nIf you have any questions or comments please do not hesitate to contact me.\n\n\n\n \n\n\n\nThank you,\n\n\n\n-Tracy\n\n\n\n \n\n\n\nTracy L. Wood, PE, Administrator\n\n\n\nWastewater Engineering Bureau, NHDES\n\n\n\n29 Hazen Drive, PO Box 95, Concord, NH 03302\n\n\n\nTel: (603) 271-2001  |  Fax: (603) 271-4128\n\n\n\n \n\n\n\n\n\n\n"],
#        "sb_source":["Test source"],
#		

		
	def _index(self,doc):
		"""index to solr"""
		jsondoc=json.dumps([doc])
		result,status=post_jsondoc(jsondoc,self.mycore)
		return result,status


def remove_control_characters(s):
	return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

