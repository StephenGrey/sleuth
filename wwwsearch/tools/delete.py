"""Delete all documents in a solr index"""
import sys
try:
    import wwwsearch_connect #Connect to Django project
except:
    pass
import ownsearch.solrJson as s
import documents.updateSolr as u

def main(core):
    mycore=s.SolrCore(core)
    
    try:
       mycore.ping()
    except Exception as e:
       print (e)
       print ('Core does not exist, or Solr server not reached')
       exit()
           
    print ('\nDeleting everything from '+core)
    try:
        q=raw_input('\nAre you sure? (yes/no)')
    except NameError: #python3
        q=input('\nAre you sure? (yes/no)')
    
    if q=='yes':
        res,status=u.delete_all(mycore)
        if status==True:
            print ('deleted')
        else:
            print (res,status)
            print ('Delete failed')


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        try:
            main(raw_input ('DELETE ALL contents: which core?'))
        except NameError: #python3
            main(input('DELETE ALL contents: which core?'))
            
    

