import pandas as pd

from electionsmaten import create_app, db
from electionsmaten.models import BallotPen, Tenant

app = create_app()

with app.app_context():

    tenant_id = 1
    district_id = 13

    file_path = "electionsmaten/UserWebID.xls"
    df = pd.read_excel(file_path)

    print(df.head())
    print(df.columns)

    username_column = df.columns[0]

    # ✅ Get tenant
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        raise Exception(f"Tenant {tenant_id} not found")

    for _, row in df.iterrows():
        username = str(row[username_column]).strip()

        # Extract serial number
        serial_number = username[len(str(tenant_id)) + 1:]

        # Validate district
        if not serial_number.startswith(f"{district_id}D"):
            print(f"Skipping invalid row: {username}")
            continue

        # Avoid duplicates
        existing = BallotPen.query.filter_by(username=username).first()
        if existing:
            continue

        # ✅ Create ballot pen
        pen = BallotPen(
            username=username,
            password=username,  # ✅ password = username
            serial_number=serial_number,
            district_id=district_id
        )

        # ✅ Link tenant (many-to-many)
        pen.tenants.append(tenant)

        db.session.add(pen)

    db.session.commit()

    print("✅ Ballot pens created successfully")