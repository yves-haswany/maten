from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engines={}



def get_tenant_session(db_name):


    if db_name not in engines:


        engine=create_engine(


            f"sqlite:///tenants/{db_name}")


        Session=sessionmaker(bind=engine)


        engines[db_name]=Session()



    return engines[db_name]
