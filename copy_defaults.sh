mkdir /var/solr/data -p
cp -r /apps/default_indexes/data/* /var/solr/data/
cp /apps/wwwsearch/usersettings.config.example /var/sleuth/
cp /apps/wwwsearch/usersettings.config /var/sleuth/
cp /apps/wwwsearch/solrdefaults.config /var/sleuth/
#start with blank database cp /apps/wwwsearch/db.sqlite3 /var/sleuth/
cp /apps/docker-compose.yml /var/sleuth/
