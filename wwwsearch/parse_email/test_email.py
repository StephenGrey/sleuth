from documents.test_indexing import ExtractTest
from documents import updateSolr,indexSolr
from ownsearch.solrJson import get_email_meta
from parse_email import email as eml
import os
from pathlib import Path

class ExtractEmail(ExtractTest):
	
	def test_oldstyle(self):
		_relpath='msg/test_with_attachment.msg'
		_id='75481fed33c6d494009453e26d3696ac40d97e6d783321990ad6e1e55f67c5b7'
#		updateSolr.delete(_id,self.mycore)
#		extractor=self.extract_document(_id,_relpath)

		updateSolr.delete(_id,self.mycore)
		path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
		ext=indexSolr.solrICIJ.ICIJExtractor(path,self.mycore,ocr=False)
		self.assertTrue(ext.result)
		
		ext=indexSolr.ICIJ_Post_Processor(path,self.mycore,hash_contents=_id,sourcetext="some source",docstore=self.docstore,test=False,check=True)


	def test_alt_attach(self):
		_relpath='msg/test_with_attachment.msg'
		_id='75481fed33c6d494009453e26d3696ac40d97e6d783321990ad6e1e55f67c5b7'
		updateSolr.delete(_id,self.mycore)
		
		path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
		
		msg=eml.Email(path,docstore=self.docstore)
		msg.parse()
		
		#delete the attachments
		updateSolr.delete("c084c76cd72b99b6ddbdcb672820b0051ffff37c68c5d239b15fcf8c16f6c2cd",self.mycore)
		updateSolr.delete("a86b1d51b75dc76ae8aeda701324807d7d1250158b3aed864c5709bf534fe182",self.mycore)
		
		#index body and any attachmetns
		msg.extract()
	
		res=get_email_meta(_id,self.mycore)[0]
		self.assertTrue(res.data.get('message_raw_header_message_id')=='<B7ACD02A303171428B7670C9BDA64F990D82891B@Mail.private.fando.com>')
		self.assertTrue(res.data.get('message_raw_header_thread_index')=='AdN7ODXmM+YmSEixToyuhkKTglBU9w==')
		self.assertTrue(res.data.get('message_raw_header_x_originating_ip')=='[192.168.200.16]')
		
		res=get_email_meta("c084c76cd72b99b6ddbdcb672820b0051ffff37c68c5d239b15fcf8c16f6c2cd",self.mycore)[0]
		self.assertTrue(res.data.get('docpath')== ['msg/test_with_attachment.msg'])
		self.assertTrue(res.docname=='image001.gif')
		res=get_email_meta("a86b1d51b75dc76ae8aeda701324807d7d1250158b3aed864c5709bf534fe182",self.mycore)[0]
		self.assertTrue(res.data.get('docpath')== ['msg/test_with_attachment.msg'])
		self.assertTrue(res.docname=='20171215_Newport, NH - Response to DRAFT Facility Plan Comments.pdf')

		#'docpath': ['msg/test_with_attachment.msg'





	def test_email_alt(self):
		"""test email with alternative parser"""
		_relpath='msg/test_email.msg'
		_id='5b6fcfc9fe87b050255bb695a4616e3c7abddf282e6397fd868e03c1b0018fb0'
		updateSolr.delete(_id,self.mycore)
		
		path=os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/testdocs', _relpath))
		
		#first a test run, then a full extract into index        
		self.assertTrue(os.path.exists(path))
		
		
		extractor=indexSolr.ExtractFile(path,self.mycore,hash_contents='',sourcetext='Test source',docstore=self.docstore,retry=True)
		self.assertTrue(extractor.alt_tried)
		
		doc=updateSolr.check_hash_in_solrdata(_id,self.mycore)
		
		#print(doc.data['message_to'])
		#print(self.docstore)
		
		self.assertEquals(doc.data['message_to'],"'Adele Fulton' <AFulton@townandcitylaw.com>, \"Paul J. Brown\" <finance@newportnh.net>")
		self.assertEquals(doc.data['message_from'],'"Wood, Tracy" <Tracy.Wood@des.nh.gov>')
		self.assertEquals(doc.data['message_raw_header_message_id'],'<B7EE98A869777C49ACF006A8AA90665C63B8A2@HZNGRANMAIL1.granite.nhroot.int>')
		self.assertEquals(doc.date,'2015-07-29T17:58:40Z')
		self.assertEquals(doc.data['title'], 'Newport Adimistrative Order by Consent (AOC) Status')
		self.assertEquals(Path(doc.data['docpath'][0]),Path('msg/test_email.msg'))
