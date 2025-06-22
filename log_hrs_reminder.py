#Text reminder script

#This script will be used to be run as a chron job every weekday to remind
# myself or others to log work hours.

#handles arguments for CLI
import argparse
#handles mailing
import yagmail
#handles texting
import requests
#handles .env stuff
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import os
import json
import re
import logging

# setup the logging
# give it a filename to output to
# a = append, w = overwrite. We're going to do append because we want a history
# format the output to be a little more legible
# format the time stamps to be easier to read
logging.basicConfig(
    level=logging.INFO,
    filename="reminder.log",
    filemode="a",
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Log start of script
logging.info("Script started.")

#get the .env path
env_path = Path(__file__).resolve().parent / ".env"

#load .env file where sending email and password are stored
load_dotenv(dotenv_path=env_path)

#get json path from .env
json_path = os.getenv("JSON_PATH")

#initialize parser for CLI arguments
parser = argparse.ArgumentParser(description="This script sends a text or email reminder to target recipients at set time and date intervals")

#define keyword arguments for CLI
parser.add_argument("--recipients", nargs="*", help="A list of recipients")
parser.add_argument("--phones", nargs="*", help="A list of 10 digit phone numbers formatted 5555555555")
parser.add_argument("--time", type=str, help="The time to send. Formatted: HH:MM:AM")
parser.add_argument("--days", nargs="*", help="A list of the days to run. Formatted [M,T,W,TH,F,S,SU.]")
parser.add_argument("--message", type=str, help="Message body to be sent")
parser.add_argument("--subject", type=str, help="Subject line for email")
parser.add_argument("--file", type=str, help="A file to read from")
parser.add_argument("--method", type=str, help="How is the reminder being sent? Email, text or both?")

arguments = parser.parse_args()

def get_json_file():
    try:
        with open(json_path) as file:
            email_data = json.load(file)
        
        logging.info(f"{json_path} successfully loaded.")
        return email_data
    # Handle the exceptions and log them. Exit early.
    except FileNotFoundError:
        logging.exception(f"File not found: {json_path}")
        exit()
    except json.JSONDecodeError as e:
        logging.exception(f"JSON error: {e}")
        exit()
    except PermissionError:
        logging.exception(f"Permission denied accessing: {json_path}")
        exit()
    except Exception as e:
        logging.exception(f"Unhandle exception trying to access {json_path}: {e}")
        exit()


#Get functions to grab defaults from the JSON file for no, or partial arguments.
email_data = get_json_file()

def get_recipients():
    return email_data["recipients"]

def get_subject():
    return email_data["subjects"]["default"]

def get_message():
    return email_data["messages"]["default"]

def get_phone_numbers():
    return email_data["phone_numbers"]

def get_time():
    return email_data["time"]

def get_days():
    return email_data["days"]

def default_fallback():
    logging.warning("Ivalid dispatch key in default dispatch")
    raise ValueError("Ivalid dispatch key in default dispatch")

#dispatch dictionary to avoid messy if/elif chain.
default_dispatch = {
    "recipients": get_recipients,
    "phones": get_phone_numbers,
    "subject": get_subject,
    "message": get_message,
    "time": get_time,
    "days": get_days
}

#get methods for arguments

#get recipients
def get_arg_recipients():
    if vars(arguments)["recipients"]:
        return vars(arguments)['recipients']
    else:
        return None
           
#get phones
def get_arg_phones():
    if vars(arguments)["phones"]:
        return vars(arguments)["phones"]
    else:
        return None
#get message
def get_arg_message():
    if vars(arguments)["message"]:
        return vars(arguments)["message"]
    else:
        return None
#get subject
def get_arg_subject():
    if vars(arguments)["subject"]:
        return vars(arguments)["subject"]
    else:
        return None
#get method
def get_arg_method():
    if vars(arguments)["method"]:
        return vars(arguments)["method"]
    else:
        return None

def args_fallback():
    logging.error("Invalid argument key in argument dispatch")
    raise ValueError("Ivalid argument key in argument dispatch")
    
args_dispatch = {
    "recipients": get_arg_recipients,
    "phones": get_arg_phones,
    "message": get_arg_message,
    "subject": get_arg_subject,
    "method": get_arg_method
}

def arguments_or_default(key):
    #check if there's an argument to use, if not return the default
    return args_dispatch.get(key, args_fallback)() or default_dispatch.get(key, default_fallback)()

def validate_email(email):
    #check that email address is formatted correctly
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"

    return re.match(pattern, email)
    
def validate_phone(phone):
    #check that phone number is formatted 5555555555
    pattern = r"^\d{10}$"

    return re.match(pattern, phone)

def send_emails(recipient_list, message, subject):
    try: 
        mailer = yagmail.SMTP(os.getenv("EMAIL"), os.getenv("APP_PW"))

        #Loop through and message each recipient
        for recipient in recipient_list:
            if validate_email(recipient):
                # let user know something is happening
                print(f"Sending to {recipient}")
                mailer.send(recipient, subject, message)

                # log for referrence
                logging.info(f"Email sent to: {recipient}")
            else:
                logging.warning(f"Invalid email {recipient}")
    except yagmail.error.YagInvalidEmailAddress as e:
            logging.exception(f"unable to send. No username or password. {e}")
    except Exception as e:
            logging.exception(f"Unhandle exception in send_emails: {e}")

def send_texts(phone_list, message):
    try:
        #text all recipients
        #!!! ATTENTION !!!
        #apend _test to the API key and it will send a test message without using a credit.
        for text_recipient in phone_list:  
            if(validate_phone(text_recipient)): 
                resp = requests.post('https://textbelt.com/text', {
                    'phone': text_recipient,
                    'message': message,
                    'key': os.getenv("TB_API_KEY") + '_test',
                })

                # !!! ATTENTION !!!
                # We should be checking that the response JSON shows a succesful send
                # and handle and log the result

                # Let user see something has happened
                print(f"Sent to {text_recipient}")

                # log the API response for reference
                logging.info(f"textbelt response: {resp.json}")
            else:
                logging.warning(f"Invaild phone number: {text_recipient}")
    except Exception as e:
        logging.exception(f"Unhandled exception in send_texts: {e}")

def get_json_default(key):
    return default_dispatch.get(key, default_fallback)()

def assign_from_arguments():
    args_dict = vars(arguments)

    #check that there are arguments
    if any(args_dict.value()):
        args_dict = vars(arguments)
        #make a dictionary to hold values that are filled through arguments to be returned
        return_dict = {}

        for key in args_dict:
            if args_dict[key] != None:
                return_dict.update({key: args_dict[key]})

        return return_dict
    else:
        return None


def get_alert_method():
    # decided if we're sending emails, texts or both. Default case is email (it's free).
    if vars(arguments)["recipients"] and vars(arguments)["phones"] or vars(arguments)["method"] == "both":
        return "both"
    elif vars(arguments)["method"] == "email" or vars(arguments)["recipients"]:
        return "email"
    elif vars(arguments)["method"] == "text" or vars(arguments)["phones"]:
        return "text"
    else:
        return "email"
    
def send_alert():
    method = get_alert_method()
    #decide if we're sending emails, texts or both, run send_emails or send_texts functions with the arguments_or_default function
    if method == "email":
        send_emails(arguments_or_default("recipients"), arguments_or_default("message"), arguments_or_default("subject"))

    if method == "text":
        send_texts(arguments_or_default("phones"),arguments_or_default("message"))

    if method == "both":
        send_emails(arguments_or_default("recipients"), arguments_or_default("message"), arguments_or_default("subject"))
        send_texts(arguments_or_default("phones"),arguments_or_default("message"))

send_alert()

# log end of script
logging.info("Script ended")