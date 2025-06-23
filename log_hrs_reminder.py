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
from dotenv import load_dotenv
import os
import json
import re
import logging


# Since we're running with Task Scheduler locally we need to give it the directory
# for the log file so it doesn't try to write to one in system32....sigh
parent_directory = Path(__file__).parent
log_file = parent_directory / "reminder.log"

# setup the logging
# give it a filename to output to
# a = append, w = overwrite. We're going to do append because we want a history
# format the output to be a little more legible
# format the time stamps to be easier to read
logging.basicConfig(
    level=logging.INFO,
    filename=log_file,
    filemode="a",
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Log start of script
logging.info("Script started.")

script_dir = os.path.dirname(os.path.abspath(__file__))

#get the .env path
env_path = Path(__file__).resolve().parent / ".env"

os.chdir(script_dir)
#load .env file where sending email and password are stored
load_dotenv(dotenv_path=os.path.join(script_dir, ".env"))

#get json path from .env
json_path = os.getenv("JSON_PATH")

#initialize parser for CLI arguments
parser = argparse.ArgumentParser(description="This script sends a text or email reminder to target recipients at set time and date intervals")

#define keyword arguments for CLI
parser.add_argument("--recipients", nargs="*", help="A list of recipients")
parser.add_argument("--phones", nargs="*", help="A list of 10 digit phone numbers formatted 5555555555")
parser.add_argument("--message", type=str, help="Message body to be sent")
parser.add_argument("--subject", type=str, help="Subject line for email")
parser.add_argument("--file", type=str, help="A file to read from")
parser.add_argument("--method", type=str, help="How is the reminder being sent? Email, text or both?")

# !!! ATTENTION !!!
# We'll comment these for now but we should use them to write a config for cron once we're ready for that

# parser.add_argument("--time", type=str, help="The time to send. Formatted: HH:MM:AM")
# parser.add_argument("--days", nargs="*", help="A list of the days to run. Formatted [M,T,W,TH,F,S,SU.]")

# !!! UPDATE !!!
# Converting arguments in to a dictionary to reduce the amount of function calls
arguments = vars(parser.parse_args())
logging.info(f"arguments: {arguments}")

# !!! UPDATE !!!
# Made a single get argument function and reducing the amount of vars() function calls to clean thing up
def get_arg(key):
    #check valid key
    if key in arguments:
        if arguments.get(key):
            return arguments.get(key)
        else:
            return None
    else:
        logging.error("Invalid key in argument: {key}")
        raise ValueError
    
def get_json_file():
    try:
        with open(os.path.join(script_dir, ".json")) as file:
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

json_data = get_json_file()
logging.info(f"JSON: {json_data}")

# !!! UPDATE !!!
# made a single get for JSON data to clean up. Also moved it up to better match scripts
# progressive logic
def get_json(key):
    if key in json_data:
        if json_data[key]:
            return json_data[key]
        else:
            return None
    else:
        logging.error(f"Invalid Key for JSON: {key}")
        raise ValueError

def arguments_or_default(key):
    #check if there's an argument to use, if not return the default
    # return args_dispatch.get(key, args_fallback)() or default_dispatch.get(key, default_fallback)()
    return get_arg(key) or get_json(key)

def validate_email(email):
    #check that email address is formatted correctly
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"

    return re.match(pattern, email)
    
def validate_phone(phone):
    #check that phone number is formatted 5555555555
    pattern = r"^\d{10}$"

    return re.match(pattern, phone)

def log_text_response(response_data, phone):
    if response_data["success"]:
        logging.info(f"text successfully sent to {phone}")
    else:
        logging.warning(f"text failed to: {phone}")

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
        # !!! UPDATE !!!
        # Assigning api key outside of loop to reduce function calls and clean up

        # !!! ATTENTION !!!
        # Make a function to assign the API key or test key based on arguments or json
        # the API requires credits and we don't want to have to buy when we can test for free
        api_key = os.getenv("TB_API_KEY")
        test_key = api_key + "_test"

        for text_recipient in phone_list:  
            if(validate_phone(text_recipient)): 
                resp = requests.post('https://textbelt.com/text', {
                    'phone': text_recipient,
                    'message': message,
                    'key': test_key,
                })

                response_data = json.dumps(resp.json())

                # Let user see something has happened
                print(f"Sent to {text_recipient}")

                # log the API response for reference
                log_text_response(response_data, text_recipient)
            else:
                logging.warning(f"Invaild phone number: {text_recipient}")
    except Exception as e:
        logging.exception(f"Unhandled exception in send_texts: {e}")

def get_json_default(key):
    return get_json(key)

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
    # decided if we're sending emails, texts or both. Defaulting to text rather than email. I prefer the text.
    if arguments["recipients"] and arguments["phones"] or arguments["method"] == "both":
        return "both"
    elif arguments["method"] == "email" or arguments["recipients"]:
        return "email"
    elif arguments["method"] == "text" or ["phones"]:
        return "text"
    else:
        return "text"
    
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

print("Done")

# log end of script
logging.info("Script ended")
