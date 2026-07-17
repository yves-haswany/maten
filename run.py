"""from electionsmaten import create_app, db
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)
if __name__ == "__main__":
    app.run(debug=True)
"""

from electionsmaten import create_app
from electionsmaten.services.tenant_service import init_tenant_db_registry

app = create_app()

init_tenant_db_registry(app)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)