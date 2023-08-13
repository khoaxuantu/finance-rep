import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        headers = {
            "X-RapidAPI-Key": os.environ.get("API_KEY"),
            "X-RapidAPI-Host": "apidojo-yahoo-finance-v1.p.rapidapi.com"
        }
        query_string = {"symbol": symbol, "region": "US"}

        # url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        # url = f"https://api.iex.cloud/v1/data/core/quote/{urllib.parse.quote_plus(symbol)}?token={api_key}"
        url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/stock/v2/get-summary"
        
        response = requests.get(url, headers=headers, params=query_string)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        # New API return a list containing a dict instead of a dict directly
        quote = response.json()["price"]
        return {
            "name": quote["longName"],
            "shortname": quote["shortName"],
            "price": quote["regularMarketPrice"],
            "symbol": quote["symbol"],
            "currency": quote["currency"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def timeformat(value):
    """Format timestamp"""
    return f"{value.year}-{value.month}-{value.day} {value.hour}:{value.minute}:{value.second} UTC"
