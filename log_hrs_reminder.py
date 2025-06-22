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

# !!! ATTENTION !!!
# JSON file is hardcoded to default file. Add logic for file selection through argument and use a default fallback in the .env
#get the path for the file because dotenv isn't finding it on it's own. Figure out later:
env_path = Path(__file__).resolve().parent / "gmail.env"
json_path = Path(__file__).resolve().parent / "email_data.json"
#load .env file where sending email and password are stored
load_dotenv(dotenv_path=env_path)

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

with open(json_path) as file:
        email_data = json.load(file)

#Get functions to grab defaults from the JSON file for no, or partial arguments.
#****TO_UPDATE**** add logging as well as printed messages. Maybe a single function to handle that so
# we can see who was messaged, what was messaged, and when. 
# Also confirmations for texts if we can.
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

def default():
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
    
args_dispatch = {
    "recipients": get_arg_recipients,
    "phones": get_arg_phones,
    "message": get_arg_message,
    "subject": get_arg_subject,
    "method": get_arg_method
}

def arguments_or_default(key):
    #check if there's an argument to use, if not return the default
    return args_dispatch[key]() or default_dispatch[key]()

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
                print(f"Sending to {recipient}")
                mailer.send(recipient, subject, message)
            else:
                print(f"invalid email: {recipient}")

    except yagmail.error.YagInvalidEmailAddress as e:
            print(f"unable to send. No username or password. {e}")
    except Exception as e:
            print(f"Unable to send. {e}")

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

                print(f"Sent to {text_recipient}. -- Response {resp.json()}")
            else:
                print(f"invalid {text_recipient}")
    except Exception as e:
        print(f"Exception in text function: {e}")

def get_json_default(key):
    return default_dispatch.get(key, default)()

def assign_from_arguments():
    #check that there are arguments
    if any(vars(arguments).values()):
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
    #decide if we're sending emails, texts or both run use send_emails or send_texts functions with the arguments_or_default function
    if method == "email":
        send_emails(arguments_or_default("recipients"), arguments_or_default("message"), arguments_or_default("subject"))

    if method == "text":
        send_texts(arguments_or_default("phones"),arguments_or_default("message"))

    if method == "both":
        send_emails(arguments_or_default("recipients"), arguments_or_default("message"), arguments_or_default("subject"))
        send_texts(arguments_or_default("phones"),arguments_or_default("message"))

send_alert()