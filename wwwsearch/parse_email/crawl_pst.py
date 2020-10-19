import olefile,os

f="R:\DATA BACKUP\Outlook CLEAN\Reuters2016.pst"

assert os.path.exists(f)

assert olefile.isOleFile(f)
ole = olefile.OleFileIO(f)


##https://stackoverflow.com/questions/5077625/reading-e-mails-from-outlook-with-python-through-mapi
#
#import win32com.client
#
#outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
#
#inbox = outlook.GetDefaultFolder(6) # "6" refers to the index of a folder - in this case,
#                                    # the inbox. You can change that number to reference
#                                    # any other folder
#messages = inbox.Items
#message = messages.GetLast()
#body_content = message.body
#print body_content
#
#
##https://docs.microsoft.com/en-us/dotnet/api/microsoft.office.interop.outlook.mailitem?redirectedfrom=MSDN&view=outlook-pia#properties_