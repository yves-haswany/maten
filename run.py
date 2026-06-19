"""from electionsmaten import create_app, db
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)
if __name__ == "__main__":
    app.run(debug=True)
"""

from  electionsmaten import create_app
import logging
import os
logging.basicConfig(level=logging.INFO)
basedir = os.path.abspath(os.path.dirname(__file__))  # <-- define basedir here

app=create_app()
logging.info("Starting FLASK App")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'maten.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret_key")
logging.info("App created successfully")
@app.route("/ping")
def ping():
   return "pong"
if __name__ == "__main__":
   app.run(debug=False,host="0.0.0.0",port=5000)
