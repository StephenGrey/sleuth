import sys, os
import unicodedata
# modified from https://superuser.com/a/237571

#usage 
#...rename('/Users/USername/temp') >>> rename to ascii
#   main .... scan and find unicode

def main(argv):
    if len(argv) != 2:
        raise Exception('Syntax: unicodecheck.py <directory>')

    startdir = argv[1]
    if not os.path.isdir(startdir):
        raise Exception('"%s" is not a directory' % startdir)
        

    for r in recurse_breadth_first(startdir, is_unicode_filename):
        decoded_str=r.decode("utf-8")
        #decoded_str = r.decode("windows-1252")
        new=unicodedata.normalize('NFKD', decoded_str).encode('ascii','ignore')
        print(new)
        
def rename(startdir):
    if not os.path.isdir(startdir):
        raise Exception('"%s" is not a directory' % startdir)
        
    for r in recurse_breadth_first(startdir, is_unicode_filename):
        decoded_str=r.decode("utf-8")
        #decoded_str = r.decode("windows-1252")
        newname=unicodedata.normalize('NFKD', decoded_str).encode('ascii','ignore')
        
        print ('RENAMING : '+r)
        print ('TO : '+newname)
        #question = r'Rename FROM:{0} TO:{1}   (yes/no)?'.format(r,newname)
        rename = raw_input('Go ahead?').lower()
        if rename.startswith('y'):
            os.rename(r, newname)
        else: 
            print ('skipped :'+newname)

def recurse_breadth_first(dirpath, test_func):
    namesandpaths = [(f, os.path.join(dirpath, f)) for f in os.listdir(dirpath)]

    for (name, path) in namesandpaths:
        if test_func(name):
            yield path

    for (_, path) in namesandpaths:
        if os.path.isdir(path):
            for r in recurse_breadth_first(path, test_func):
                yield r


def is_unicode_filename(filename):
    return any(ord(c) >= 0x7F for c in filename)


if __name__ == '__main__':
    main(sys.argv)