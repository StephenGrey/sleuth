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
echo
scp -r $keypath $localindex $remoteserver




