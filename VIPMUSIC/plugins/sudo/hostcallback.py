import os
import socket

import requests
import urllib3
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyromod.exceptions import ListenerTimeout

from VIPMUSIC import app

# Import your MongoDB database structure
from VIPMUSIC.utils.pastebin import VIPbin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEROKU_API_URL = "https://api.heroku.com"
HEROKU_API_KEY = os.getenv("HEROKU_API_KEY")
REPO_URL = "https://github.com/THE-VIP-BOY-OP/VIP-MUSIC"
BUILDPACK_URL = "https://github.com/heroku/heroku-buildpack-python"


async def is_heroku():
    return "heroku" in socket.getfqdn()


async def paste_neko(code: str):
    return await VIPbin(code)


def fetch_app_json(repo_url):
    app_json_url = f"{repo_url}/raw/master/app.json"
    response = requests.get(app_json_url)
    return response.json() if response.status_code == 200 else None


def make_heroku_request(endpoint, api_key, method="get", payload=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.heroku+json; version=3",
        "Content-Type": "application/json",
    }
    url = f"{HEROKU_API_URL}/{endpoint}"
    response = getattr(requests, method)(url, headers=headers, json=payload)
    return response.status_code, (
        response.json() if response.status_code == 200 else None
    )


async def collect_env_variables(message, env_vars):
    user_inputs = {}
    await message.reply_text(
        "Provide the values for the required environment variables. Type /cancel at any time to cancel the deployment."
    )
    for var_name in env_vars:
        try:
            response = await app.ask(
                message.chat.id,
                f"Provide a value for `{var_name}` or type /cancel to stop:",
                timeout=60,
            )
            if response.text == "/cancel":
                await message.reply_text("Deployment canceled.")
                return None
            user_inputs[var_name] = response.text
        except ListenerTimeout:
            await message.reply_text(
                "Timeout! You must provide the variables within 60 seconds. Restart the process to deploy"
            )
            return None
    return user_inputs


# Edit Environment Variables


@app.on_callback_query(filters.regex(r"^edit_vars:(.+)"))
async def edit_vars(client, callback_query):
    app_name = callback_query.data.split(":")[1]

    # Fetch environment variables from Heroku
    status, response = make_heroku_request(
        f"apps/{app_name}/config-vars", HEROKU_API_KEY
    )

    # Debugging output
    print(f"Status: {status}, Response: {response}")

    # Check if the response is successful and contains environment variables
    if status == 200 and isinstance(response, dict):
        if response:
            # Create buttons for each environment variable
            buttons = [
                [
                    InlineKeyboardButton(
                        var_name, callback_data=f"edit_var:{app_name}:{var_name}"
                    )
                ]
                for var_name in response.keys()
            ]

            # Add an option to add new variables and a back button
            buttons.append(
                [
                    InlineKeyboardButton(
                        "Add New Variable", callback_data=f"add_var:{app_name}"
                    )
                ]
            )
            buttons.append(
                [InlineKeyboardButton("Back", callback_data=f"app:{app_name}")]
            )

            reply_markup = InlineKeyboardMarkup(buttons)

            # Send the buttons to the user
            await callback_query.message.reply_text(
                "Select a variable to edit:", reply_markup=reply_markup
            )
        else:
            await callback_query.message.reply_text(
                "No environment variables found for this app."
            )
    else:
        await callback_query.message.reply_text(
            f"Failed to fetch environment variables. Status: {status}, Response: {response}"
        )


@app.on_callback_query(filters.regex(r"^edit_var:(.+):(.+)"))
async def edit_variable_options(client, callback_query):
    app_name, var_name = callback_query.data.split(":")[1:3]

    buttons = [
        [
            InlineKeyboardButton(
                "Edit", callback_data=f"edit_var_value:{app_name}:{var_name}"
            )
        ],
        [
            InlineKeyboardButton(
                "Delete", callback_data=f"delete_var:{app_name}:{var_name}"
            )
        ],
        [InlineKeyboardButton("Back", callback_data=f"edit_vars:{app_name}")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await callback_query.message.reply_text(
        f"Choose an option for the variable `{var_name}`:", reply_markup=reply_markup
    )


# Add New Variable
@app.on_callback_query(filters.regex(r"^add_var:(.+)"))
async def add_new_variable(client, callback_query):
    app_name = callback_query.data.split(":")[1]

    # Ask for variable name
    response = await app.ask(
        callback_query.message.chat.id,
        "Please send me the new variable name:",
        timeout=60,
    )
    var_name = response.text

    # Ask for variable value
    response = await app.ask(
        callback_query.message.chat.id,
        f"Now send me the value for `{var_name}`:",
        timeout=60,
    )
    var_value = response.text

    # Confirmation before saving
    buttons = [
        [
            InlineKeyboardButton(
                "Yes", callback_data=f"save_var:{app_name}:{var_name}:{var_value}"
            )
        ],
        [InlineKeyboardButton("No", callback_data=f"edit_vars:{app_name}")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await callback_query.message.reply_text(
        f"Do you want to save `{var_value}` for `{var_name}`?",
        reply_markup=reply_markup,
    )


# Save Variable
@app.on_callback_query(filters.regex(r"^save_var:(.+):(.+):(.+)"))
async def save_new_variable(client, callback_query):
    app_name, var_name, var_value = callback_query.data.split(":")[1:4]

    # Save the variable to Heroku
    status, result = make_heroku_request(
        f"apps/{app_name}/config-vars",
        HEROKU_API_KEY,
        method="patch",
        payload={var_name: var_value},
    )

    if status == 200:
        await callback_query.message.reply_text(
            f"Variable `{var_name}` with value `{var_value}` saved successfully."
        )
    else:
        await callback_query.message.reply_text(f"Failed to save variable: {result}")
