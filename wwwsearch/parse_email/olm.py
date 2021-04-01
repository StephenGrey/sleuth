import zipfile,pathlib,tempfile,logging,os,shutil
from documents.file_utils import slugify

log = logging.getLogger('ownsearch.olm')
#based on https://github.com/alephdata/ingest-file/blob/master/ingestors/email/olm.py

class OLMextractor():
	
	def __init__(self,filepath):
		self.filepath=filepath
	
	
	def extract_message(self, root, zipf, name):
		# Individual messages are stored as message_xxx.xml files. We want to
		# process these files and skip the others
		if "message_" not in name or not name.endswith(".xml"):
			return
		# Create the parent folders as entities with proper hierarchy
		parent = self.extract_hierarchy(root, name)
		# Extract the xml file itself and put it on the task queue to be
		# ingested by OutlookOLMMessageIngestor as an individual message
		xml_path = self.extract_file(zipf, name)
		print(xml_path)
		
#        checksum = self.manager.store(xml_path, mime_type=MIME)
#        child = self.manager.make_entity("Document", parent=parent)
#        child.make_id(checksum)
#        child.add("contentHash", checksum)
#        child.add("mimeType", MIME)
#        self.manager.queue_entity(child)
#        try:
#            doc = self.parse_xml_path(xml_path)
#            # find all attachments mentioned in the current xml file, assign
#            # them their parent and put them on the queue to be processed
#            for el in doc.findall(".//messageAttachment"):
#                self.extract_attachment(zipf, child, el)
#        except ProcessingException:
#            pass
	def extract_file(self, zipf, name):
		"""Extract a message file from the OLM zip archive"""
		path = pathlib.Path(name)
		base_name = slugify(path.name)
		out_file = os.path.join(self.tmpdirname,base_name)
		log.debug(out_file)
		with open(out_file, "w+b") as outfh:
			try:
				with zipf.open(name) as infh:
					shutil.copyfileobj(infh, outfh)
			except KeyError:
				log.warning("Cannot load zip member: %s", name)
			except Exception as e:
				log.error(e)
		return out_file

	def extract_hierarchy(self, entity, name):
		"""Given a file path, create all its ancestor folders as entities"""
			
		folders=pathlib.PurePath(name).as_posix().split("/")[:-1]
		try:
			folders.remove('com.microsoft.__Messages')
		except ValueError:
			pass

		folderpath=os.path.join(*folders)		
		return folderpath

	def crawl(self,path):
		count=0
		
		try:
			# OLM files are zip archives with emails stored as xml files
			with tempfile.TemporaryDirectory() as self.tmpdirname:
				with zipfile.ZipFile(self.filepath, "r") as zipf:
					for name in zipf.namelist():
						count+=1
						if count>20:
							break
						try:
							self.extract_message(None, zipf, name)
						except Exception:
							log.exception("Error processing message: %s", name)
		except Exception as e:
			print (e)
			
			
	