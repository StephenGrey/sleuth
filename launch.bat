echo "Activating Python Environment"
call ..\..\..\env\Scripts\activate
echo "launching Sleuth server"
python wwwsearch\manage.py runserver

