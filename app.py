from crypt import methods
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from sqlalchemy import Float, false, null, true
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Query full user's stocks
    user_stocksInfo = db.execute("SELECT symbol, compName, shares \
                                  FROM stocks_info\
                                  WHERE symbol IS NOT NULL\
                                  AND compName IS NOT NULL\
                                  AND userid = ?", session["user_id"])
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    have_stocks = false
    # Initialize holding symbol price and holding value
    # price {symbol: price}
    # hold {symbol: total value (shares * price["symbol"])}
    # total [total value (shares * price["symbol"])]
    price = {}
    hold = {}
    total = []
    # Query the symbols which the user holds
    symbols = db.execute("SELECT symbol, shares FROM stocks_info WHERE userid = ?\
                          AND symbol IS NOT NULL AND shares IS NOT NULL", session["user_id"])

    if len(symbols) != 0:
        have_stocks = true
        for symbol in symbols:
            sym_info = lookup(symbol["symbol"])
            if not sym_info:
                break
            price[symbol["symbol"]] = sym_info["price"]
            hold[symbol["symbol"]] = price[symbol["symbol"]] * int(symbol["shares"])

    total = hold.values()

    return render_template("index.html", user=user_stocksInfo, price=price, cash=user_cash,
                            have_stocks=have_stocks, hold=hold, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST
    if request.method == "POST":
        # Collect input symbol
        symb = request.form.get("symbol").upper().strip()
        symb_lookup = lookup(symb)

        # Collect input shares amount
        input_shares = request.form.get("shares")
        if not input_shares or not input_shares.isnumeric():
            return apology("invalid amount of shares", 400)

        shares = float(input_shares)

        # Validate symbol
        if not symb_lookup:
            return apology("invalid symbol", 400)

        # Validate the shares amount
        elif not shares >= 0:
            return apology("invalid amount of shares", 400)

        # Expected amount of cash to spend
        expect_spend = shares * symb_lookup["price"]

        # Query how much cash the user has
        avail_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Apology if user does not has enough money
        if avail_cash[0]["cash"] < expect_spend:
            return apology("cannot afford to buy", 400)

        # Update the shares amount after buying
        # Check if the user buy a symbol for the first time
        shares_stored = db.execute("SELECT * FROM stocks_info \
                                    WHERE userid = ? AND symbol = ?",
                                    session["user_id"], symb_lookup["symbol"])
        # Insert the new amount of shares into the database
        if len(shares_stored) != 1:
            db.execute("INSERT INTO stocks_info (userid, compName, symbol, shares)\
                        VALUES (?, ?, ?, ?)",
                        session["user_id"], symb_lookup["name"], symb_lookup["symbol"], shares)

        # Update the new amount of shares into the database
        else:
            # Query the amount of holding shares
            holding_shares = db.execute("SELECT shares FROM stocks_info\
                                         WHERE userid = ? AND symbol = ?",
                                         session["user_id"], symb_lookup["symbol"])

            db.execute("UPDATE stocks_info \
                        SET shares = ?\
                        WHERE userid = ? AND symbol = ?",
                        holding_shares[0]["shares"] + shares,
                        session["user_id"], symb_lookup["symbol"])

        # Deduct the cash in user's account
        modify_cash = avail_cash[0]["cash"] - expect_spend
        db.execute("UPDATE users\
                    SET cash = ?\
                    WHERE id = ?", modify_cash, session["user_id"])

        # Update transaction log
        db.execute("INSERT INTO transaction_log (userid, symbol, shares_in_out, price, method, time)\
                    VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                    session["user_id"], symb_lookup["symbol"], shares, symb_lookup["price"], 'Bought')

        flash("Buy successfully")
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query the transaction log
    trans_log = db.execute("SELECT * FROM transaction_log WHERE userid = ?", session["user_id"])

    return render_template("history.html", transactions=trans_log)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached rout via POST
    if request.method == "POST":
        # Get quote
        quo = request.form.get("symbol").upper().strip()

        quo_info = lookup(quo)

        if not quo_info:
            return apology("invalid symbol", 400)

        else:
            return render_template("quoted.html", quo_info=quo_info)

    # User reached rout via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # forget any user id
    session.clear()

    # User reached rout via "POST"
    if request.method == "POST":
        exclude_char = "[@_!#$%^&*()<>?/\|}{~:]"

        # Submit the user input
        user = request.form.get("username")
        pwd = request.form.get("password")
        val_pwd = request.form.get("confirmation")

        # Ensure the user's input is not blank or the username already exists
        if not user:
            return apology("must provide username", 400)

        for char in user:
            if char in exclude_char:
                return apology(f"{char} is not allowed for username", 400)

        # Ensure the password input is not blank or matched
        if not pwd:
            return apology("must provide password", 400)

        # Ensure user confirms correct password
        elif pwd != val_pwd:
            return apology("passwords do not match", 400)

        # Query the database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", user)

        if len(rows) == 1:
            return apology("username has already existed", 400)

        # Insert the new user into users database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", user,
                    generate_password_hash(pwd))
        id_query = db.execute("SELECT id FROM users WHERE username = ?", user)
        db.execute("INSERT INTO stocks_info (userid) VALUES (?)", id_query[0]["id"])

        return redirect("/login")

    # User reached route via "GET"
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Query available symbols
    symb_query = db.execute("SELECT symbol, shares FROM stocks_info\
                             WHERE symbol IS NOT NULL\
                             AND userid = ?", session["user_id"])

    # User reached route via POST
    if request.method == "POST":

        # Get a selected symbol
        get_symbol = request.form.get("symbol")
        if not get_symbol:
            return apology("invalid symbol", 403)
        else:
            symb_info = lookup(get_symbol)

        # Get an amount of shares that the users want to sell
        input_shares = request.form.get("shares")
        if not input_shares or not input_shares.isnumeric():
            return apology("invalid amount of share", 403)

        shares_to_sell = float(input_shares)
        if not shares_to_sell > 0:
            return apology("invalid amount of share", 403)

        # Check if the users have enough shares to sell
        user_shares = db.execute("SELECT shares FROM stocks_info\
                                  WHERE symbol = ?\
                                  AND userid = ?", get_symbol, session["user_id"])
        if user_shares[0]["shares"] < shares_to_sell:
            return apology("not enough shares to sell", 400)

        # Query the cash amount of the users:
        recent_cash = db.execute("SELECT cash FROM users\
                                  WHERE id = ?", session["user_id"])

        # Update the cash after selling
        cash_after_sell = recent_cash[0]["cash"] + (shares_to_sell * symb_info["price"])
        # Update users database
        db.execute("UPDATE users\
                    SET cash = ?\
                    WHERE id = ?", cash_after_sell, session["user_id"])
        # Update stocks_info database
        if (user_shares[0]["shares"] - shares_to_sell) == 0:
            db.execute("DELETE FROM stocks_info WHERE userid = ? AND symbol = ?", session["user_id"], get_symbol)

        else:
            db.execute("UPDATE stocks_info\
                        SET shares = ?\
                        WHERE userid = ? AND symbol = ?",
                        user_shares[0]["shares"] - shares_to_sell, session["user_id"], get_symbol)

        # Update transaction log
        db.execute("INSERT INTO transaction_log (userid, symbol, shares_in_out, price, method, time)\
                    VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                    session["user_id"], symb_info["symbol"], shares_to_sell, symb_info["price"], 'Sold')

        flash("Sell successfully")
        return redirect("/")

    # User reached rout via GET
    else:
        return render_template("sell.html", symbols=symb_query)


@app.route("/changePassword", methods=["GET", "POST"])
@login_required
def changePassword():
    """Change password"""
    if request.method == "POST":

        # Get and validate the input password
        current_pwd = request.form.get("password")
        pwd_to_change = request.form.get("change_password")
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        if not current_pwd:
            return apology("Must provide password", 404)
        elif not check_password_hash(rows[0]["hash"], current_pwd):
            return apology("invalid password", 403)

        if not pwd_to_change:
            return apology("password to change cannot be blank", 404)

        # Update new password
        db.execute("UPDATE users SET hash = ? WHERE id = ?",
                    generate_password_hash(pwd_to_change), session["user_id"])

        # Forget any id
        session.clear()

        return redirect("/login")

    else:
        return render_template("pwChangeUI.html")


@app.route("/addCash", methods=["POST"])
@login_required
def addCash():
    """Add additional cash into user's account"""

    # Get input cash
    cash_added = float(request.form.get("cash"))
    if not cash_added > 0:
        return apology("Invalid amount of cash", 403)

    # Query available cash
    avail_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Update additional to database
    return_cash = cash_added + avail_cash[0]["cash"]
    db.execute("UPDATE users SET cash = ? WHERE id = ?", return_cash, session["user_id"])

    return redirect("/")


@app.route("/BuyOrSell", methods=["POST"])
@login_required
def BuyOrSell():
    """ Redirect buy or sell route """

    if request.form.get("buy") == "BUY":
        return redirect("/buy", code=307)
    elif request.form.get("sell") == "SELL":
        return redirect("/sell", code=307)
