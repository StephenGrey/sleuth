#docker run -v ~/Documents:/data -it sleuth:v1 /bin/bash
#


FROM python:3.8
WORKDIR /apps
RUN git clone https://github.com/StephenGrey/sleuth.git
RUN cd sleuth && git fetch origin
RUN cd sleuth && git merge
RUN pip install -r sleuth/requirements.txt
RUN pip install concurrent-log-handler
RUN pip install python-dateutil
RUN pip install msglite
RUN pip install extract-msg
RUN pip install emlx
RUN cd sleuth && cp wwwsearch/usersettings.config.example wwwsearch/usersettings.config
RUN ls
#Edit this usersettings.config file to set the collectionbasepath. This directory should have subdirectories containing sets of documents you want to search. e.g /Users/Michael/Documents

#Also in the 'Django' sub-section, edit the 'secretkey' to something long and random. This is an important security feature in Django. You can also set 'Debug' to 'True' or 'False'. 'Debug' mode is inherently insecure so disable it if other users have access to your Sleuth machine.

#Now navigate to the wwwsearch directory. Set up the database:

RUN cd sleuth/wwwsearch && python manage.py makemigrations
RUN cd sleuth/wwwsearch && python manage.py migrate
RUN cd sleuth/wwwsearch && python manage.py createsuperuser

