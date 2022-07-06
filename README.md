# My-CS50-finance

I practiced my Flask tutorials by finishing CS50's problem set<br>
Link to the assignment: https://cs50.harvard.edu/x/2022/psets/9/finance/
<br><br>
C$50 Finance is a web app via which you can manage portfolios of stocks. Not only will this tool allow you to check real stocks’ actual prices and portfolios’ values, it will also let you buy (okay, “buy”) and sell (okay, “sell”) stocks by querying 
[IEX](https://exchange.iex.io/products/market-data-connectivity/) 
for stocks’ prices.

## Configuring
Before getting started on this assignment, we’ll need to register for an API key in order to be able to query IEX’s data. To do so, follow these steps:
- Visit iexcloud.io/cloud-login#/register/.
- Select the “Individual” account type, then enter your name, email address, and a password, and click “Create account”.
- Once registered, scroll down to “Get started for free” and click “Select Start plan” to choose the free plan.
- Once you’ve confirmed your account via a confirmation email, visit https://iexcloud.io/console/tokens.
- Copy the key that appears under the Token column (it should begin with pk_).
- In your terminal window, execute:
<pre>$ export API_KEY=value</pre>

## Running
Start Flask’s built-in web server:
- <pre>$ flask run</pre>
