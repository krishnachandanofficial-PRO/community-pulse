# github_api.py - Talking to GitHub.
# Reads the token, makes GET requests (read-only), and explains errors.

import os
import sys
import time

import requests
from dotenv import load_dotenv

API_URL = "https://api.github.com"


# Loads GITHUB_TOKEN from the .env file. In: nothing. Out: the token text.
# Stops the program if the token is missing. The token is never printed.
def read_token():
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("No GITHUB_TOKEN found. Put GITHUB_TOKEN=your_token in a .env file.")
        sys.exit(1)
    return token


# Turns a GitHub error code into a plain-English message.
# In: the status code number. Out: a message to print.
def explain_error(status_code):
    if status_code == 401:
        return "GitHub said 401: your token is wrong or expired. Check GITHUB_TOKEN in .env."
    if status_code == 403:
        return "GitHub said 403: you hit the rate limit, or your token cannot see this repo."
    if status_code == 404:
        return "GitHub said 404: repo not found. Check the name is written as owner/repo."
    return "GitHub returned an unexpected error, code " + str(status_code) + "."


# Makes one GET request to GitHub, after a short pause so we are polite.
# In: the path after api.github.com (like "/repos/fastapi/fastapi/issues") and the token.
# Out: the JSON data (or None if it failed) and how many API calls we have left.
def get_json(path, token):
    time.sleep(0.1)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
    try:
        response = requests.get(API_URL + path, headers=headers, timeout=30)
    except requests.RequestException:
        print("Could not reach GitHub. Check your internet connection.")
        return None, 0
    if response.status_code != 200:
        print(explain_error(response.status_code))
        return None, 0
    calls_left = int(response.headers.get("X-RateLimit-Remaining", "5000"))
    return response.json(), calls_left
