# services/tenant_service.py

import logging
from ..db.tenant_db import create_database

logger = logging.getLogger(__name__)


def init_tenant_db_registry(app):

    with app.app_context():

        from ..models.master_models import Tenant

        tenants = Tenant.query.all()

        if not tenants:
            logger.info("No tenants found in master DB")
            return

        logger.info(f"Found {len(tenants)} tenants")

        for tenant in tenants:

            db_name = tenant.db_name  # IMPORTANT FIX

            logger.info(f"Creating DB for tenant: {tenant.username}")

            create_database(db_name)

        logger.info("Tenant DB initialization complete")