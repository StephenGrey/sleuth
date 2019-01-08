# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function


import PyPDF2,sys,os, logging,time
from PyPDF2.utils import PdfReadError
log = logging.getLogger('ownsearch.docs.check_pdf')

class PDFCheckException(Exception):
    pass

def main(path,verbose=False):
    if not os.path.exists(path):
        log.debug('File does not exist')
        raise PDFCheckException('File does not exist')
    elif os.path.isdir(path):
        log.debug('Filepath is directory')
        raise PDFCheckException('Is a directory')
    elif os.path.splitext(path)[1] != '.pdf':
        log.debug(f'PATH: \'{path}\' is not a PDF')
        raise PDFCheckException('Not a PDF')
    else:
        return check(path,verbose=verbose)
            

def crawl(path):
    if os.path.isdir(path):
        log.debug('Filepath is directory')
        for root, dirs, files in os.walk(path):
            for name in files:
                try:
                    filepath=os.path.join(root, name)
                    log.info(filepath)
                    checked=main(filepath)
                    
                    log.info(f'{name} OCRd: {checked}')
                    
                except PdfReadError:
                    log.info(f'Pdf read error for filepath: {path}')
                except PDFCheckException as e:
                    log.info(f'Error: {e}')      
    else:
        log.debug('No directory to crawl')


def check_dir(path):
    "crawl folder, identify OCRd PDFs"
    if os.path.isdir(path):
        log.debug('Filepath is directory')
        for root, dirs, files in os.walk(path):
            for name in files:
                try:
                    file_path=os.path.join(root, name)
                    filename, file_extension = os.path.splitext(name)
                    if file_extension=='.pdf':
                        start=time.time()
                        result=main(file_path)
                        elapsed=int((time.time()-start)*10)/10
                        log.info(f'{name} OCRd: {result} in {elapsed} secs')
                    else:
                        pass
                        #log.debug(f'{name} not a pdf')
                except PdfReadError:
                    log.info(f'Pdf read error for filepath: {path}')
                except PDFCheckException as e:
                    log.info(f'Error: {e}')      
    else:
        log.debug('No directory to crawl')
    


def check(path,verbose=False):
    if True:
        with open(path,'rb') as f:
            pdfReader = PyPDF2.PdfFileReader(f)
            num_pages = pdfReader.numPages
            count = 0
            text = ""
            if verbose:
                log.debug(f'Page count: {num_pages}')
            #The while loop will read each page
            while count < num_pages:
                pageObj = pdfReader.getPage(count)
                count +=1
                pagetext =pageObj.extractText()
                
                if verbose:
                    log.debug(pageObj.get('/Annots'))
                    log.info(f'Page #{count}: {pageObj.keys()}')
                    log.info(f'Page #{count}: text: {pagetext}')
                text+=pagetext
                slimtext = text[:100]# if len(text)>20 else text
                if len(text)>100: 
                    break
        if text=="":
            log.debug(f'PATH: {path} has no text / IMAGE PDF')
            return False
        else:
            log.debug(f'PATH: {path} has text e.g sample: {slimtext}')
            return True
        


if __name__ == '__main__':
   if len(sys.argv)>1:
       filepath = sys.argv[1]
       if os.path.isdir(filepath):
           crawl(filepath)
       else:
           try:
               hasOCR=main(filepath)
               if hasOCR:
                   print(f'PATH: {filepath} has embedded text')
               else:
                   print(f'PATH: {filepath} has no text / IMAGE PDF')
           except PdfReadError:
               print(f'Pdf read error for filepath: {filepath}')

   else:
       'Usage: python check_pdf.py ~/path/to/apdf.pdf'

