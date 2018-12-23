#!/bin/bash
echo Upload an index to remote Solr server
read -p 'Name of local index to copy: ' localindex
read -p 'Remote server address: ' remoteserver
read -p 'Key path ? ' keypath
if [ $keypath != '']
then
   $key="-i $keypath"
fi
echo Attempting secure copy ...
echo $key
scp -r $key $localindex $remoteserver
echo 
echo CHECKLIST on your remote server ...
echo 1. mv yourindexname /var/solr/data/  (or other location of solr indexes)
echo 2. chown solr:solr (or other user that solr uses)(
echo 3. edit /var/solr/data/indexname/core.properties (e.g. nano core.properties)
echo        so as you have 'name=indexname'
echo 4. restart solr server (e.g. sudo service apache2 restart)
echo 5. via SearchBox admin  https://yourURL/admin  create a SolrCore entry to point to new index






