from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..models.master_models import (
    Tenant,
    District as TenantDistrict,
    SubDistrict as TenantSubDistrict,
    Sect as TenantSect,
    SubdistrictSectSeat as TenantSeat,

)


from ..db.master_db import db
Base = db.Model


def populate_tenant_database(tenant_id):

    ####################################################
    # Get tenant
    ####################################################

    tenant = Tenant.query.get(tenant_id)

    if tenant is None:
        raise Exception("Tenant not found.")

    ####################################################
    # Open tenant database
    ####################################################

    engine = create_engine(
        f"sqlite:///instance/{tenant.db_name}.db"
    )

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    tenant_session = Session()

    ####################################################
    # Copy districts
    ####################################################

    for district in tenant.districts:

        tenant_district = TenantDistrict(
            id=district.id,
            code=district.code,
            name=district.name
        )

        tenant_session.add(tenant_district)

        ################################################
        # Copy subdistricts
        ################################################

        for sub in district.subdistricts:

            tenant_sub = TenantSubDistrict(
                id=sub.id,
                district_id=sub.district_id,
                name=sub.name,
                description=sub.description
            )

            tenant_session.add(tenant_sub)

            ############################################
            # Copy seat allocations
            ############################################

            for allocation in sub.sect_allocations:

                ########################################
                # Copy sect once
                ########################################

                sect = allocation.sect

                exists = tenant_session.get(
                    TenantSect,
                    sect.id
                )

                if not exists:

                    tenant_session.add(
                        TenantSect(
                            id=sect.id,
                            name=sect.name,
                            religion=sect.religion
                        )
                    )

                ########################################
                # Copy allocation
                ########################################

                tenant_session.add(

                    TenantSeat(
                        id=allocation.id,
                        subdistrict_id=allocation.subdistrict_id,
                        sect_id=allocation.sect_id,
                        seats=allocation.seats
                    )

                )

    tenant_session.commit()
    tenant_session.close()