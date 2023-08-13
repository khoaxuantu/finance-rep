from crypt import methods
import os

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from firebase_admin import credentials, firestore, initialize_app
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, timeformat
from builder import Users

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["timeformat"] = timeformat

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# db = SQL("sqlite:///finance.db")

# Initialize Firestore DB
cred = credentials.Certificate('./keys/firestorekey.json')
# cred = credentials.Certificate('firestorekey.json')
default_app = initialize_app(cred)
db = firestore.client()
users_ref = db.collection('users')
transaction = db.transaction()

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


@firestore.transactional
def update_stocks(transaction, user_ref, amount, method, symbol, shares):
    """Update user's stocks via transaction
    
    :param obj transaction: db.transaction()
    :param obj user_ref: A reference to document 'user_id' in the collection 'users'
    :param float amount: An amount money for processing
    :param string method: '+' or '-'
    :param string symbol: A symbol of a stock
    :param int shares: An amount of shares for processing
    """
    snapshot = user_ref.get(transaction=transaction)
    stock_ref = user_ref.collection('stocks').document(symbol)
    stock_snapshot = stock_ref.get(transaction=transaction)
    if method == '+':
        newCash = snapshot.get('cash') - amount
        newShares = stock_snapshot.get('shares') + shares
    else:
        newCash = snapshot.get('cash') + amount
        newShares = stock_snapshot.get('shares') - shares
    # Update cash and share amounts
    transaction.update(user_ref, {
        "cash": newCash
    })
    if newShares > 0:
        transaction.update(stock_ref, {
            "shares": newShares
        })
        stock_ref = None
    return stock_ref


@firestore.transactional
def update_logs(transaction, user_ref, method, price, symbol, shares):
    """Update user's transaction logs via firestore transaction
    
    :param obj transaction: db.transaction()
    :param obj user_ref: A reference to document 'user_id' in the collection 'users'
    :param string method: "Bought" or "Sold"
    :param float price: The price per shares of a stock
    :param string symbol: A symbol of a stock
    :param int shares: An amount of shares for processing
    """
    # Update transaction num
    snapshot = user_ref.get(transaction=transaction)
    newTransactionNum = snapshot.get('transaction_num') + 1
    transaction.update(user_ref, {
        "transaction_num": newTransactionNum
    })
    # Update new log, set the new transaction num as a new log's id
    logs_ref = user_ref.collection('transaction_log').document(str(newTransactionNum))
    logs_ref.set({
        "method": method,
        "price": price,
        "symbol": symbol,
        "process_shares": shares,
        "time": firestore.SERVER_TIMESTAMP
    })


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Query full user's stocks
    user_ref = users_ref.document(session["user_id"])
    userQuery = user_ref.get()
    cash = userQuery.get('cash')
    docs = user_ref.collection('stocks').stream()
    userStocksInfo = []
    for doc in docs:
        userStocksInfo.append(doc.to_dict())
    # app.logger.debug(userStocksInfo[0])
    
    # Initialize holding symbol price and holding value
    # userStockVal {
    #   symbol: {
    #       price: price
    #       hold: total value (shares * price["symbol"])
    #   }
    # }
    # total[]: total value (shares * price["symbol"])
    have_stocks = False
    userStockVal = {}
    total = []

    if len(userStocksInfo) != 0:
        have_stocks = True
        for symbol in userStocksInfo:
            newDict = {}
            symbInfo = lookup(symbol["symbol"])
            if not symbInfo:
                return apology("exceed number of API calls", 400)
            newDict["price"]= symbInfo["price"]["raw"]
            newDict["hold"] = symbol["shares"] * symbInfo["price"]["raw"]
            total.append(newDict["hold"])

            userStockVal[symbol["symbol"]] = newDict

    return render_template("index.html", user=userStocksInfo, cash=cash, total=total,
                            have_stocks=have_stocks, value=userStockVal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST
    if request.method == "POST":
        user_ref = users_ref.document(session["user_id"])
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
        expect_spend = shares * symb_lookup["price"]["raw"]

        # Query how much cash the user has
        avail_cash = user_ref.get().get('cash')

        # Apology if user does not has enough money
        if avail_cash < expect_spend:
            return apology("cannot afford to buy", 400)
        else:
            avail_cash -= expect_spend

        # Update the shares amount after buying
        # Check if the user buy a symbol for the first time
        # Insert the new amount of shares into the database
        stock_ref = user_ref.collection('stocks').document(symb)
        stock_doc = stock_ref.get()
        if not stock_doc.exists:
            user_ref.update({"cash": avail_cash})
            stock_ref.set({
                "name": symb_lookup["name"],
                "symbol": symb_lookup["symbol"],
                "shares": shares
            })

        # Update the new amount of shares into the database
        else:
            update_stocks(transaction, user_ref, expect_spend, '+',
                          symb_lookup["symbol"], shares)

        # Update transaction log
        update_logs(transaction, user_ref, "Bought", symb_lookup["price"]["raw"],
                    symb_lookup["symbol"], shares)

        flash("Buy successfully!")
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    trans_log = []
    userQuery = users_ref.document(session["user_id"]).get()
    trans_num = userQuery.get('transaction_num')
    # Query the transaction log
    if trans_num != 0:
        # log_path = session["user_id"] + '/transaction_log'
        trans_log_ref = users_ref.document(session["user_id"]).collection('transaction_log')
        query = trans_log_ref.order_by("time", direction=firestore.Query.DESCENDING)
        trans_log_docs = query.stream()
    for doc in trans_log_docs:
        trans_log.append(doc.to_dict())
    # app.logger.debug(trans_log[0])

    return render_template("history.html", transactions=trans_log)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id (Do not enable this call due to flash message)
    # session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        user = request.form.get("username")
        pw = request.form.get("password")
        # Ensure username and password was submitted
        if not user:
            return apology("must provide username", 400)
        elif not pw:
            return apology("must provide password", 400)

        # Query database for username
        userQuery = users_ref.document(user).get()
        doc = userQuery.to_dict()
        # Ensure username exists and password is correct
        if not userQuery.exists or not check_password_hash(doc["password"], pw):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = user

        # Redirect user to home page
        flash("Log in successfully!")
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
        userQuery = users_ref.document(user).get()
        if userQuery.exists:
            return apology("username has already existed", 400)

        # Insert the new user into users database
        newUser = Users()
        newUser.setUsername(user)
        newUser.setPw(generate_password_hash(pwd))

        users_ref.document(user).set(newUser.to_dict())

        flash("Register successfully!")
        return redirect("/login")

    # User reached route via "GET"
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get user ref and stocks ref
    user_ref = users_ref.document(session["user_id"])
    stocks_ref = user_ref.collection('stocks')
    # Query available symbols
    stock_dicts = {}
    stocks_query = stocks_ref.stream()
    for stock in stocks_query:
        stock_dicts[stock.id] = stock.to_dict()

    # User reached route via POST
    if request.method == "POST":

        # Get a selected symbol
        get_symbol = request.form.get("symbol")
        if not get_symbol:
            return apology("invalid symbol", 400)
        else:
            symb_info = lookup(get_symbol)
            if not symb_info:
                return apology("exceed number of API calls", 400)

        # Get an amount of shares that the users want to sell
        input_shares = request.form.get("shares")
        if not input_shares or not input_shares.isnumeric():
            return apology("invalid amount of share", 400)

        shares_to_sell = float(input_shares)
        if not shares_to_sell > 0:
            return apology("invalid amount of share", 400)

        # Check if the users have enough shares to sell
        user_shares = stock_dicts[get_symbol]["shares"]
        if user_shares < shares_to_sell:
            return apology("not enough shares to sell", 400)

        # # Query the cash amount of the users:
        # recent_cash = user_ref.get('cash')

        # # Update the cash after selling
        # cash_after_sell = recent_cash + (shares_to_sell * symb_info["price"])
        # Update users and stocks info database
        stock_ref = update_stocks(transaction, user_ref, shares_to_sell * symb_info["price"]["raw"],
                                  '-', get_symbol, shares_to_sell)
        if stock_ref is not None:
            stock_ref.delete()

        # Update transaction log
        update_logs(transaction, user_ref, 'Sold', symb_info["price"]["raw"], get_symbol,
                    shares_to_sell)

        flash("Sell successfully!")
        return redirect("/")

    # User reached rout via GET
    else:
        return render_template("sell.html", symbols=stock_dicts)


@app.route("/changePassword", methods=["GET", "POST"])
@login_required
def changePassword():
    """Change password"""
    
    if request.method == "POST":
        user_ref = users_ref.document(session["user_id"])
        user = user_ref.get()

        # Get and validate the input password
        current_pwd = request.form.get("password")
        pwd_to_change = request.form.get("change_password")
        stored_pwd = user.get('password')

        if not current_pwd:
            return apology("Must provide password", 400)
        elif not check_password_hash(stored_pwd, current_pwd):
            return apology("invalid password", 400)

        if not pwd_to_change:
            return apology("password to change cannot be blank", 400)

        # Update new password
        user_ref.update({
            "password": generate_password_hash(pwd_to_change)
        })

        # Forget any id
        session.clear()

        flash("Password has been changed successfully!")
        return redirect("/login")

    else:
        return render_template("pwChangeUI.html", changePw=True)


@app.route("/addCash", methods=["POST"])
@login_required
def addCash():
    """Add additional cash into user's account"""

    # Get input cash
    cash_added = float(request.form.get("cash"))
    if not cash_added > 0:
        return apology("Invalid amount of cash", 400)

    # Get an user ref
    user_ref = users_ref.document(session["user_id"])

    # Update additional to database
    user_ref.update({"cash": firestore.Increment(cash_added)})

    return redirect("/")


@app.route("/BuyOrSell", methods=["POST"])
@login_required
def BuyOrSell():
    """ Redirect buy or sell route """

    if request.form.get("buy") == "BUY":
        return redirect("/buy", code=307)
    elif request.form.get("sell") == "SELL":
        return redirect("/sell", code=307)
