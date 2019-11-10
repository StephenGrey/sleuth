# sleuth
Simple out-of-the-box web interface to search through thousands of unstructured documents. 

OBJECT: Sleuth is an e-forensic tool. It provides a simple-to-install front end to exploit the capacity of the Big Data search engine, Solr. The use case: is a journalist or analyst seeking a quick dive to look through hundreds of thousands of varied computer files.
The software is in development but is currently working well enough on Mac, Linux and Windows machines, from small laptops to production servers.

Using Django and Python3, Sleuth provides a web interface to search a Solr index, as well as - for admin users - to bulk scan documents into that index.
It also has a capability to inspect media for duplicates and orphan files, allowing for example a scan of a new document collection to discover new data.

It uses Solr's built-in integration with the Tika extraction engine to allow auto-extraction of a folder of documents, but can also used to search an index built with the [ICIJ extract](https://github.com/ICIJ/extract) project. The aim is to fully converge the extraction with this project.
.
There are other more sophisticated projects that allow you to accomplish similar searches, e.g. by using [Blacklight](http://projectblacklight.org/), the OCCRP's[Aleph](https://github.com/alephdata/aleph) or the New York Times's [Stevedore](https://t.co/eRVRLaHytQ). Check out these other solutions. 

The aim of this project is different, to deliver a basic e-forenisc solution 'out of the box' with minimum fuss or set-up, accessible to non-technical users. 

SECURITY NOTE: If you install Sleuth on a public-facing server, you will need appropriate additional security.  Such security is necessary layer over this project.

See the wiki for more details 
