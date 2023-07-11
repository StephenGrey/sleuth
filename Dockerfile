#navigate to sleuth directory
#docker build . -t stephengrey1/sleuth:v1
#docker run -v ~/Documents:/data -it sleuth:v1 /bin/bash
#docker run -v $(pwd):/apps -it -p 8000:8000  sleuth:v1 /bin/bash

#docker run -v $(pwd)/configs:/var/sleuth -v $(pwd)/solrdata:/var/solr  -p 8000:8000 -idt stephengrey1/sleuth-java:v2
#docker exec -ti stephengrey1/sleuth-java:v2 /bin/bash
FROM python:3.8

ENV PYTHONUNBUFFERED=1
RUN apt-get update \
  && apt-get -y install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus tesseract-ocr-deu tesseract-ocr-fra

WORKDIR /apps
COPY . .


#adding Java install
RUN mkdir -p /etc/apt/sources.list.d
RUN cd solr_docker/resources && wget http://www.mirbsd.org/~tg/Debs/sources.txt/wtf-bookworm.sources
RUN mv solr_docker/resources/wtf-bookworm.sources /etc/apt/sources.list.d/
RUN apt update
RUN apt install openjdk-8-jdk -y

#install ICIJ extract
#MAKES I/etc/extensions/extract/extract-cli/target/extract-cli-3.7.2.jar

RUN apt install maven -y
RUN mkdir /etc/extensions
RUN cd /etc/extensions && git clone https://github.com/StephenGrey/extract.git
RUN cd /etc/extensions/extract && mvn install -DskipTests



#RUN git clone https://github.com/StephenGrey/sleuth.git
#RUN cd sleuth && git fetch origin
#RUN cd sleuth && git merge

RUN pip install -r requirements.txt
RUN pip install concurrent-log-handler
RUN pip install python-dateutil
RUN pip install msglite
RUN pip install extract-msg
RUN pip install emlx
RUN cp wwwsearch/usersettings.config.example wwwsearch/usersettings.config

#Edit this usersettings.config file to set the collectionbasepath. This directory should have subdirectories containing sets of documents you want to search. e.g /Users/Michael/Documents

#Also in the 'Django' sub-section, edit the 'secretkey' to something long and random. This is an important security feature in Django. You can also set 'Debug' to 'True' or 'False'. 'Debug' mode is inherently insecure so disable it if other users have access to your Sleuth machine.
#Now navigate to the wwwsearch directory. Set up the database:
EXPOSE 8000
RUN cd wwwsearch && python manage.py makemigrations
RUN cd wwwsearch && python manage.py migrate
#RUN cd wwwsearch && python manage.py createsuperuser
