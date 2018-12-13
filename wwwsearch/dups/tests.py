# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

from documents.test_indexing import IndexTester
from documents import file_utils
from documents.models import File,Collection,Source,Index


# Create your tests here.
class Dups(IndexTester):
    def setUp(self):
        
        self.makebase()
        
    def test_indexmaker(self):
        index_collections=Collection.objects.all()
        _ind=[x for x in file_utils.Index_Maker(self.testdups_path,index_collections)._index]
        
        print(_ind)
        self.assertEquals(_ind[0],'<li class="du">\n\n<span style="color:red;">HilaryEmailC05793347.pdf</span>\n\n</li>')

        
    def test_dupindex(self):
        index_collections=Collection.objects.all()
        _ind=[x for x in file_utils.Dups_Index_Maker(self.testdups_path,index_collections)._index]
        self.assertTrue('tests/testdocs/dups/HilaryEmailC05793347.pdf' in _ind[0])
        
        print(_ind)
        pass
        
        
    
    


