Send emails to your Joplin

#You'll need to 

pip install -r requirements.txt

#Add a .env with

EMAIL_USERNAME=username@domain.com
EMAIL_PASSWORD=password
IMAP_URL=imap.server.com
JOPLIN_TOKEN=token
JOPLIN_PORT=41184

#Joplin token is the one you generate for the webclip

#Run it manually (or add to cron)
python3 run.py

#WITH VENV

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 run.py
