# searchbox
aim: a simple out-of-the-box web interface to search through thousands of unstructured documents

PROJECT AIM: provide a simple-to-install front end to exploit the capacity of Big Data search engines like Solr. The use case: is a journalist or analyst seeking a quick dive into mass of dirty data.
This is an interim experimental working solution, while other more sophisticated projects continue to develop and become more accessible to less technical users.

Using Django and Python2, SearchBox provides a web interface to search a Solr index, as well as - for admin users - to bulk scan documents into that index.
It uses Solr's built-in integration with the Tika extraction engine to allow auto-extraction of a folder of documents, but can also used to search an index built with the [ICIJ extract](https://github.com/ICIJ/extract) project. The aim is to fully converge the extraction with this project.

There are many other ways to achieve this task, e.g. by using [Blacklight](http://projectblacklight.org/), the OCCRP's[Aleph](https://github.com/alephdata/aleph) or the New York Times's [Stevedore](https://t.co/eRVRLaHytQ). Check out these other solutions. The aim here is something simpler, to deliver a solution 'out of the box'. 

SECURITY NOTE: any web interface installed on a public-facing server will need to be appropriately secured. Such security is necessary layer over this project.

See the wiki for more details 
