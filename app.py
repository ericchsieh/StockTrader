import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
#Token: export API_KEY=pk_2fc00a6010704860848279f81f32bc96

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
    user_id = session["user_id"]

    transactions_db = db.execute("SELECT symbol, SUM(shares) AS shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    # row 0, column cash
    cash = cash_db[0]["cash"]

    stocks_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", user_id)
    symbol_names = []
    grand_total = 0.0
    portfolio_total = 0.0

    # Generate a list of stock names
    for i in range(len(stocks_db)):
        symbol = stocks_db[i]["symbol"]
        stock = lookup(symbol.upper())
        symbol_names.append(stock["name"])

    # Compute total stocks + cash value
    for i in range(len(stocks_db)):
        symbol = stocks_db[i]["symbol"]
        stock = lookup(symbol.upper())
        this_shares_db = db.execute("SELECT shares FROM transactions WHERE user_id = ?", user_id)
        this_shares = this_shares_db[i]["shares"]
        grand_total += stock["price"] * this_shares

    portfolio_total = grand_total
    grand_total += cash

    # round numbers to two decimal place
    portfolio_total = round(portfolio_total, 2)
    grand_total = round(grand_total, 2)

    # Format numbers to have commas
    portfolio_total = "{:,}".format(portfolio_total)
    #cash = "{:,}".format(cash)
    grand_total = "{:,}".format(grand_total)

    '''We are passing symbol_names inside a zip because the symbol names are not included in the transaction database.'''
    # Removed passing individually: database = transactions_db, name = symbol_names...
    return render_template("index.html", transactions_symbol=zip(transactions_db,symbol_names), cash = cash, total = grand_total, portfolio_total = portfolio_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    else:
        """CHECK FOR CONDITIONS"""
        symbol = request.form.get("symbol")
        stock = lookup(symbol.upper())
        # User must input a stock symbol
        if not symbol:
            return apology("Field Required: Must Enter Symbol")
        #Must enter a valid stock symbol
        if stock == None:
            return apology("Symbol Does Not Exist")
        # User must choose number of shares to buy
        if not request.form.get("shares"):
            return apology("Missing input Number of shares.")
        # User must enter valid share number, int only. No non-numeric
        if not str.isnumeric(request.form.get("shares")):
            return apology("Values are non-numeric.")
        # Do not accept negative shares
        if 0 >= int(request.form.get("shares")):
            return apology("Enter Valid Shares.")

        """INITIATE BUYING PROCESS"""
        shares = int(request.form.get("shares"))
        transaction_value = shares * stock["price"]
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        # access cash value as a nested list.
        user_cash = user_cash_db[0]["cash"]
        # SQL todo: Make new table called transactions.
        # todo: Check if user have enought money to make the purchase: (compute stock price) - (user's bank).
        if user_cash < transaction_value:
            return apology("Not Enough Cash.")

        update_cash = user_cash - transaction_value
        # todo: Update cash to reflect purchased stock: (user's bank) - (compute stock price).
        # UPDATE table_name SET column1 = value1, column2 = value2, ... WHERE condition;
        db.execute("UPDATE users SET cash = ? WHERE id = ?", update_cash, user_id)
        # import datetime
        date = datetime.datetime.now()
        # INSERT INTO table_name (column1, column2, column3, ...) VALUES (value1, value2, value3, ...);
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], date)

        # Shares bought
        flash_message_stock_symbol = stock["symbol"]
        flash_message_stock_name = stock["name"]
        flash_message_stock_price = stock["price"]
        flash(f"You have bought {shares} shares of {flash_message_stock_symbol} ({flash_message_stock_name})! At ${flash_message_stock_price} per share. Total: ${transaction_value}.")

        return redirect("/")

        # TODO: Purchase the stock: Input N shares into user's portfolio. ????

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions_db = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=user_id)

    stocks_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", user_id)
    symbol_names = []
    grand_total = 0.0
    portfolio_total = 0.0

    return render_template("history.html", transactions = transactions_db)

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """User can add cash"""
    if request.method == "GET":
        return render_template("add.html")
    else:
        # error message for empty field
        if not request.form.get("add_cash"):
            return apology("Must Enter Cash Amount.")
        # Add Cash
        input_cash = int(request.form.get("add_cash"))
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        # access cash value as a nested list.
        user_cash = user_cash_db[0]["cash"]
        update_cash = user_cash + input_cash
        # UPDATE table_name SET column1 = value1, column2 = value2, ... WHERE condition;
        db.execute("UPDATE users SET cash = ? WHERE id = ?", update_cash, user_id)

        return redirect("/")

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Field Required: Must Enter Symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol Does Not Exist")

        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else: # if the method is POST
        username = request.form.get("username")
        password_made = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("Username field required.")

        if not password_made:
            return apology("Password field required.")

        if not confirmation:
            return apology("Confirmation required.")

        # check if password matches
        if password_made == confirmation and password_made != None:
            # declaration of user password
            password = password_made
        else:
            return apology("Password do not match.")

        # check if username already exist in database
        if len(db.execute("SELECT username FROM users WHERE username == :username", username=username)) == 0:
            password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=password_hash)
            return redirect("/")
        else:
            return apology("Username already exists")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "GET":
        symbols_user = db.execute("SELECT symbol FROM transactions WHERE user_id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in symbols_user])
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if symbol == "Select stock...":
            return apology("Must Select A Stock")

        if not request.form.get("shares"):
            return apology("Missing field: Number of shares")

        #if shares <= 0:
        #    return apology("Invalid input.")

        # Check if user has the input number of shares in their portfolio
        user_shares_db = db.execute("SELECT shares FROM transactions WHERE user_id = :id AND symbol = :symbol", id=user_id, symbol=symbol)
        user_shares = user_shares_db[0]["shares"]

        shares = int(request.form.get("shares"))
        if not shares <= user_shares:
            return apology("You don't have this many shares of: " + symbol)

        # Perform the purchase
        stock = lookup(symbol.upper())
        transaction_value = shares * stock["price"]
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        update_shares = shares*-1#user_shares - shares
        update_cash = user_cash + transaction_value
        date = datetime.datetime.now()
        # look up user_id transaction, update the shares under symbol
        #db.execute("UPDATE transactions SET shares = ? WHERE id = ? AND symbol = ?", update_shares, user_id, symbol)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], update_shares, stock["price"], date)
        # update user cash the stock price sold amount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", update_cash, user_id)

        # Shares bought
        flash_message_stock_symbol = stock["symbol"]
        flash_message_stock_name = stock["name"]
        flash_message_stock_price = stock["price"]
        flash(f"You have sold {shares} shares of {flash_message_stock_symbol} ({flash_message_stock_name})! At ${flash_message_stock_price} per share. Total: ${transaction_value}.")
        return redirect("/")


