# My-CS50-finance-2022

The project initially is a [problem set](https://cs50.harvard.edu/x/2022/psets/9/finance/) provided by CS50
for practicing Flask application with SQLite.
I got inspired from it so have started a small project trying to replicate [CS50 finance](https://finance.cs50.net).
But instead of replicating it 100%, I'm trying to extend some new intergrations and making some changes as well. Here
are the changes that I have made, compared with the web required to made in the problem set.
- <b>Problem set's web:</b>

    + Database: SQLite
    + The assignment package only includes <code>static/</code>, <code>templates/</code>, <code>app.py</code>,
    <code>helpers.py</code>, <code>requirements.txt</code>. There is no deployment in the assignment.

- <b>This project:</b>

    + Database: Firestore
    + Included all the files in the assignment package, and a new <code>Dockerfile</code> for the deployment.
    + Deployed via [Cloud Run](https://cloud.google.com/run) in [GCP](https://cloud.google.com)
    + Added more flash messages as well as a link to stocks catalog so that the clients can interact with the web app
    easier.
