# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function



import PyPDF2,sys,os, logging
from PyPDF2.utils import PdfReadError
log = logging.getLogger('ownsearch.docs.check_pdf')

class PDFCheckException(Exception):
    pass

def main(path):
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
        return check(path)
            

def crawl(path):
    if os.path.isdir(path):
        print('Filepath is directory')
        for root, dirs, files in os.walk(path):
            for name in files:
                try:
                    main(os.path.join(root, name))
                except PdfReadError:
                    print(f'Pdf read error for filepath: {path}')
                except PDFCheckException as e:
                    print(f'Error: {e}')      
    else:
        print('No directory to crawl')

def check(path):
    if True:
        with open(path,'rb') as f:
            pdfReader = PyPDF2.PdfFileReader(f)
            num_pages = pdfReader.numPages
            count = 0
            text = ""
            
            #The while loop will read each page
            while count < num_pages:
                pageObj = pdfReader.getPage(count)
                count +=1
                text += pageObj.extractText()
                slimtext = text[0:20] if len(text)>20 else text
                
        if text=="":
            log.debug(f'PATH: {path} has no text / IMAGE PDF')
            return False
        else:
        	  log.debug(f'PATH: {path} TEXT: {slimtext}')
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

