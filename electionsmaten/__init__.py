from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate



db=SQLAlchemy()

migrate=Migrate()



def create_app():

    app=Flask(__name__)


    app.config["SECRET_KEY"]="devsecret"



    app.config["SQLALCHEMY_DATABASE_URI"]="sqlite:///maten_master.db"



    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False


    db.init_app(app)

    migrate.init_app(app,db)

    from . import master_models
    from . import tenant_models
    


    from .routes.backend.admin import admin_bp
    from .routes.backend.tenant import tenant_bp
    from .routes.auth import auth_bp


    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tenant_bp)



    return app
