import pysolr

core=raw_input ('DELETE ALL contents: which core?')
print(core)
solrurl='http://localhost:8983/solr/'+core
solr = pysolr.Solr(solrurl, timeout=10)
print ('\nDeleting everything from '+core)
q=raw_input('\nAre you sure? (yes/no)')
if q=='yes':
    solr.delete(q='*:*')
    print ('deleted')
