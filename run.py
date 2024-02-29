import imaplib
import email
from email.header import decode_header
import requests
import os
import base64
import json
from dotenv import load_dotenv
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Joplin and email account configurations
joplin_token = os.getenv('JOPLIN_TOKEN')
joplin_port = os.getenv('JOPLIN_PORT', '41184')
joplin_notes_url = f'http://localhost:{joplin_port}/notes?token={joplin_token}'
joplin_resources_url = f'http://localhost:{joplin_port}/resources?token={joplin_token}'
username = os.getenv('EMAIL_USERNAME')
password = os.getenv('EMAIL_PASSWORD')
imap_url = os.getenv('IMAP_URL')

def create_resource_in_joplin(file_path):
    try:
        # Open the file in binary mode
        with open(file_path, 'rb') as f:
            file_content = f.read()

        file_name = os.path.basename(file_path)
        mime_type = 'application/octet-stream'  # You might want to dynamically determine this based on the file type

        # Prepare the files payload for multipart encoding
        files = {
            'data': (file_name, file_content, mime_type),
            'props': (None, json.dumps({'title': file_name, 'filename': file_name}), 'application/json'),
        }

        # Note: The 'files' parameter is used instead of 'json' to ensure proper multipart/form-data encoding
        response = requests.post(joplin_resources_url, files=files)

        if response.status_code == 200:
            resource_id = response.json().get("id")
            return f"[{file_name}](:/{resource_id})"
        else:
            logging.error("Failed to create resource in Joplin: %s", response.text)
            return ""
    except Exception as e:
        logging.exception("Error creating resource in Joplin: %s", e)
        return ""

def save_attachment(part, filename):
    attachments_dir = "attachments"
    if not os.path.isdir(attachments_dir):
        os.mkdir(attachments_dir)
    filepath = os.path.join(attachments_dir, filename)
    with open(filepath, 'wb') as fp:
        fp.write(part.get_payload(decode=True))
    return filepath

def process_email(msg):
    cid_to_resource_link = {}
    body = ""
    attachments_paths = []

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))

        if part.get('Content-ID') and "inline" in content_disposition:
            # Process inline attachments (embedded images)
            content_id = part.get('Content-ID').strip('<>')
            filename = part.get_filename() or content_id
            filepath = save_attachment(part, filename)
            resource_link = create_resource_in_joplin(filepath)
            cid_to_resource_link[content_id] = resource_link
        elif "attachment" in content_disposition:
            # Process attachments
            filename = part.get_filename()
            filepath = save_attachment(part, filename)
            attachments_paths.append(filepath)
        elif content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
            # Process email body
            charset = part.get_content_charset()
            part_payload = part.get_payload(decode=True)
            body_content = part_payload.decode(charset) if charset else part_payload.decode()
            body += body_content + "\n"

    # Replace cid references in the HTML body with resource links
    for cid, link in cid_to_resource_link.items():
        body = body.replace(f'cid:{cid}', link)

    # Attach non-inline (regular) attachments to the note
    for filepath in attachments_paths:
        attachment_link = create_resource_in_joplin(filepath)
        body += "\n" + attachment_link

    return body

def create_note_in_joplin(subject, body):
    note = {"title": subject, "body": body}
    try:
        response = requests.post(joplin_notes_url, json=note)
        if response.status_code != 200:
            logging.error("Failed to create note in Joplin: %s", response.text)
    except Exception as e:
        logging.exception("Error creating note in Joplin: %s", e)

def check_emails():
    try:
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(username, password)
        mail.select('inbox')

        status, messages = mail.search(None, 'UNSEEN')
        if status == 'OK':
            for num in messages[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_header(msg['subject'])[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()
                        body = process_email(msg)
                        create_note_in_joplin(subject, body)
        mail.logout()
    except Exception as e:
        logging.exception("Failed to check emails: %s", e)

if __name__ == '__main__':
    check_emails()
