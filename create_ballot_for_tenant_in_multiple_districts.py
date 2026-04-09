from electionsmaten import create_app, db
from electionsmaten.models import BallotPen, Tenant
from werkzeug.security import generate_password_hash

TENANT_ID = 3

# Districts + number of ballots
DISTRICTS = {
    12: 377,  # 3C12D0001 → 3C12D0377
    14: 313   # 3C14D0001 → 3C14D0313
}


def get_tenant_letter(tenant_id):
    return chr(64 + tenant_id)  # 3 → C


def generate_ballot_username(tenant_id, district_id, serial):
    letter = get_tenant_letter(tenant_id)
    return f"{tenant_id}{letter}{district_id}D{serial:04d}"


def generate_ballots():
    tenant = Tenant.query.get(TENANT_ID)

    if tenant is None:
        print("❌ Tenant not found")
        return

    total_created = 0
    total_skipped = 0

    for district_id, total_ballots in DISTRICTS.items():

        print(f"\n📍 District {district_id} → Generating {total_ballots} ballots")

        created = 0
        skipped = 0

        for i in range(1, total_ballots + 1):

            username = generate_ballot_username(TENANT_ID, district_id, i)
            serial_number = f"{district_id}D{i:04d}"

            existing = BallotPen.query.filter_by(username=username).first()

            if existing:
                print(f"⚠️ Skipping existing: {username}")
                skipped += 1
                continue

            ballot = BallotPen(
                username=username,
                password=generate_password_hash(username),  # password = username
                district_id=district_id,
                serial_number=serial_number
            )

            ballot.tenants.append(tenant)

            db.session.add(ballot)
            created += 1

        print(f"✅ District {district_id} → Created: {created}, Skipped: {skipped}")

        total_created += created
        total_skipped += skipped

    db.session.commit()

    print("\n🎉 ALL DONE")
    print(f"Total Created: {total_created}")
    print(f"Total Skipped: {total_skipped}")


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        generate_ballots()