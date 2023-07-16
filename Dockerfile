#to build:
#make a directory:
#1/ git clone https://github.com/StephenGrey/sleuth.git
#2/ docker build . -t stephengrey1/sleuth:v2
#3/ in working folder, make a 'configs' and a 'solrdata' folders.
#docker run -v $(pwd)/configs:/var/sleuth -v $(pwd)/solrdata:/var/solr --name "sleuth-java" -p 8000:8000 -idt stephengrey1/sleuth:v0.1:  TO START UP THE CONTAINER
#   docker exec -ti sleuth-java2 bash -c "/apps/copy_defaults.sh"
#3/ copy the docker-compose.yml ino working folder to launch all services; edit environment variables.
#4/ 
#5/ docker exec -ti sleuth-java /bin/bash  TO ENTER THE CONTAINER
# AND THEN USE user "python wwwsearch/manage.py setup" and ""python wwwsearch/manage.py createsuperuser" to set up the indexx to  to copy config files you can edit to host compotuer
#  docker exec -it sleuth_empty-sleuth-1 /bin/bash/launch 0:8000
# AND launch or test server with ./launch 0:8000 or use python wwwsearch/manage.py to run different commands (see wiki docs)
# FINALLY SHUT DOWN CONTAINER AND SWITCH TO DOCKER-COMPOSE TO RUN FULL SET UP
# 
FROM python:3.8

ENV PYTHONUNBUFFERED=1
RUN apt-get update \
  && apt-get -y install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus tesseract-ocr-deu tesseract-ocr-fra

WORKDIR /apps

#copy Sleuth code from Github, or local development copy
COPY . .  
#RUN git clone https://github.com/StephenGrey/sleuth.git

#adding Java install
RUN mkdir -p /etc/apt/sources.list.d

#SOURCE FILES TO IMPLEMENT JAVA 8 - WORKAROUND http://www.mirbsd.org/~tg/Debs/sources.txt/wtf-bookworm.sources
RUN mv solr_docker/resources/wtf-bookworm.sources /etc/apt/sources.list.d/
RUN apt update
RUN apt install openjdk-8-jdk -y

#install ICIJ extract
#MAKES I/etc/extensions/extract/extract-cli/target/extract-cli-3.7.2.jar

RUN apt install maven -y
RUN mkdir /etc/extensions
RUN cd /etc/extensions && git clone https://github.com/StephenGrey/extract.git
RUN cd /etc/extensions/extract && mvn install -DskipTests

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

