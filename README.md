# searchbox
aim: a simple out-of-the-box web interface to search through thousands of unstructured documents

PROJECT AIM: SearchBox is an e-forensic tool. It provides a simple-to-install front end to exploit the capacity of the Big Data search engine, Solr. The use case: is a journalist or analyst seeking a quick dive to look through thousands of varied computer files.

Using Django and Python3 (or Python2), SearchBox provides a web interface to search a Solr index, as well as - for admin users - to bulk scan documents into that index.

It uses Solr's built-in integration with the Tika extraction engine to allow auto-extraction of a folder of documents, but can also used to search an index built with the [ICIJ extract](https://github.com/ICIJ/extract) project. The aim is to fully converge the extraction with this project.

There are other more sophisticated projects that allow you to accomplish similar searches, e.g. by using [Blacklight](http://projectblacklight.org/), the OCCRP's[Aleph](https://github.com/alephdata/aleph) or the New York Times's [Stevedore](https://t.co/eRVRLaHytQ). Check out these other solutions. 

The aim of this project is different, to deliver a basic e-forenisc solution 'out of the box' with minimum fuss or set-up, accessible to non-technical users. 

SECURITY NOTE: If you install SearchBox on a public-facing server, you will need appropriate additional security.  Such security is necessary layer over this project.

See the wiki for more details 
