from electionsmaten import create_app, db
from electionsmaten.models import BallotPen, Tenant
from werkzeug.security import generate_password_hash

TENANT_ID = 2
DISTRICT_ID = 13
TOTAL_BALLOTS = 361


def get_tenant_letter(tenant_id):
    return chr(64 + tenant_id)  # 2 → B


def generate_ballot_username(tenant_id, district_id, serial):
    letter = get_tenant_letter(tenant_id)
    return f"{tenant_id}{letter}{district_id}D{serial:04d}"


def generate_ballots():
    tenant = Tenant.query.get(TENANT_ID)

    if tenant is None:
        print("❌ Tenant not found")
        return

    print(f"✅ Generating ballots for Tenant {TENANT_ID} in District {DISTRICT_ID}")

    created = 0
    skipped = 0

    for i in range(1, TOTAL_BALLOTS + 1):  # 1 → 361

        username = generate_ballot_username(TENANT_ID, DISTRICT_ID, i)
        serial_number = f"{DISTRICT_ID}D{i:04d}"

        # Check if already exists
        existing = BallotPen.query.filter_by(username=username).first()
        if existing:
            print(f"⚠️ Skipping existing: {username}")
            skipped += 1
            continue

        ballot = BallotPen(
            username=username,
            password=generate_password_hash(username),  # password = username
            district_id=DISTRICT_ID,
            serial_number=serial_number
        )

        # Attach tenant
        ballot.tenants.append(tenant)

        db.session.add(ballot)
        created += 1

    db.session.commit()

    print(f"\n🎉 Done.")
    print(f"Created: {created}")
    print(f"Skipped (already existed): {skipped}")


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        generate_ballots()