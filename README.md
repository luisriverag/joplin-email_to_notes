Send emails to your Joplin

#You'll need to 

pip install requests
pip install python-dotenv

#Add a .env with

EMAIL_USERNAME=username@domain.com
EMAIL_PASSWORD=password
IMAP_URL=imap.server.com
JOPLIN_TOKEN=token
JOPLIN_PORT=41184

#Joplin token is the one you generate for the webclip

#Run it manually (or add to cron)
python3 run.py
