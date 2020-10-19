from parse_email import crawl_email as crawl
import logging
log = logging.getLogger(__name__)
log.setLevel='DEBUG'

MASTER="R:\DATA BACKUP\Outlook CLEAN\Messages_new"
SF="R:\DATA BACKUP\Outlook CLEAN\orphans"
OF="R:\DATA BACKUP\Outlook CLEAN\Messages_dups"


#db=crawl.db(MASTER)
#db.rescan()
#db.message_scan()

#crawl.move_dups(db,search_folder=SF,target_folder=OF)

def crawling():
    cb=crawl.Compare(MASTER,SF,output_folder=OF)
    cb.rescan_all()

    for path in cb.search_local_dups():
        try:
            print(path)
        except Exception as e:
            print(e)
            
    #cb.session.close()

def inspect_local_dups():
    cb=crawl.Compare(MASTER,SF,output_folder=OF)
    cb.local.rescan()
    cb.inspect_local()

def purge_local_dups():
    cb=crawl.Compare(MASTER,SF,output_folder=OF)
    cb.inspect_local
    cb.purge_local()
    
def purge_combos():
    cb=crawl.Compare(MASTER,SF,output_folder=OF)
    cb.purge_dups_with_master()

def copy_blanks():
    cb=crawl.db(MASTER)
    cb.copy_blanks("R:\DATA BACKUP\Outlook CLEAN\copyblanks")

def hash_dups(folder):
    cb=crawl.db(folder)
    cb.rescan()
    return cb.dups.all()

log.debug('starting')
#crawling()
#inspect_local_dups()
#purge_local_dups()
#purge_combos()

dups=hash_dups("R:\DATA BACKUP\Outlook CLEAN\copyblanks")
print(dups)







