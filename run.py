import imaplib
import email
from email.header import decode_header
import requests
import os
import base64
import json
from dotenv import load_dotenv
import logging
import mimetypes
import html2text



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

# Folder to receive notes (Buffer) Joplin ID
buffer_folder_id = '386c2f4fa2d441bd96e9596c8bbff7e5'  


def create_resource_in_joplin(file_path):
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()

        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            logging.warning(f"Could not guess the MIME type for {file_name}. Defaulting to 'application/octet-stream'.")
            mime_type = 'application/octet-stream'

        # Create the payload for the POST request
        files = {
            'data': (file_name, file_content, mime_type),
            'props': (None, json.dumps({'title': file_name, 'filename': file_name}), 'application/json'),
        }

        # Make the POST request to the Joplin API to create the resource
        response = requests.post(joplin_resources_url, files=files)
        logging.info(f"Joplin API response for creating resource: {response.text}")  # Log the response text
 

        if response.status_code == 200:
            resource_id = response.json().get("id")
            if resource_id:
                if mime_type.startswith('image/'):
                    # If the file is an image, return Markdown for displaying the image
                    return f"![{file_name}](:/{resource_id})"
                else:
                    # If the file is not an image, return Markdown for a downloadable link
                    return f"[{file_name}](:/{resource_id})"
            else:
                logging.error("Received a 200 response but no resource ID was found in the response.")
                return ""
        else:
            logging.error(f"Failed to create resource in Joplin: {response.status_code} {response.text}")
            return ""
    except Exception as e:
        logging.exception("Exception occurred while creating resource in Joplin:")
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
    h = html2text.HTML2Text()
    h.ignore_links = False

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))

        # Handling inline images
        if 'inline' in content_disposition and part.get('Content-ID'):
            content_id = part.get('Content-ID').strip('<>')
            filename = part.get_filename()
            filepath = save_attachment(part, filename)
            resource_link = create_resource_in_joplin(filepath)
            if resource_link:
                cid_to_resource_link[content_id] = resource_link  # Store Markdown link directly

        elif 'attachment' in content_disposition:
            filename = part.get_filename()
            if filename:
                filepath = save_attachment(part, filename)
                attachment_link = create_resource_in_joplin(filepath)
                body += f"\n{attachment_link}"  # Append link to body

        elif content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
            charset = part.get_content_charset()
            part_payload = part.get_payload(decode=True)
            body_content = part_payload.decode(charset) if charset else part_payload.decode(errors='replace')
            if 'html' in content_type:
                body += h.handle(body_content)  # Convert HTML to Markdown
            else:
                body += body_content  # Append plain text directly

    # Replace 'cid' references in the email body
    for cid, link in cid_to_resource_link.items():
        body = body.replace(f'cid:{cid}', link)

    return body


def create_note_in_joplin(subject, body, folder_id):
    note = {"title": subject, "body": body, "parent_id": folder_id}
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
                        # Log the final body content before creating a note in Joplin
                        logging.info("Final body content:")
                        logging.info(body)
                        # Now create the note in Joplin with the subject and body
                        create_note_in_joplin(subject, body, buffer_folder_id)
        mail.logout()
    except Exception as e:
        logging.exception("Failed to check emails: %s", e)


def find_folder_id(folder_name):
    folders_url = f'http://localhost:{joplin_port}/folders?token={joplin_token}'
    try:
        response = requests.get(folders_url)
        if response.status_code == 200:
            folders = response.json()
            print(f"Folders JSON: {folders}")  # Diagnostic print statement
            for folder in folders:
                if folder['title'] == folder_name:
                    return folder['id']
            logging.error(f'Folder "{folder_name}" not found.')
            return None
        else:
            logging.error(f"Failed to fetch folders: {response.text}")
            return None
    except Exception as e:
        logging.exception("Error fetching folders: %s", e)
        return None

#to find folder id uncomment 2 lines below and comment the if

#buffer_folder_id = find_folder_id('Buffer')
#print(buffer_folder_id)


if __name__ == '__main__':
    check_emails()


