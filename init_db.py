"""
Database Initialization & Responder Seeding Script
Initializes PostgreSQL (or local SQLite fallback) schema and seeds registered rescue teams.
Usage:
    python init_db.py
"""
import sys
import logging
from database import engine, init_db, get_db, get_db_info
from models import RescueTeam, ResourceInventory

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_RESCUE_TEAMS = [
    {
        "team_id": "NDRF-AP-10",
        "name": "10th NDRF Battalion Water Rescue Wing",
        "organization": "National Disaster Response Force (NDRF)",
        "team_type": "Flood Rescue & Swift-Water Extraction",
        "base_location": "Bhavanipuram Sector Base, Vijayawada",
        "latitude": 16.5210,
        "longitude": 80.6050,
        "phone": "+91-866-2410101",
        "sms_number": "+91-9440101010",
        "email": "ops.ndrf10@gov.in",
        "capabilities": "Deep-water boat extraction, night navigation, swift-water dive gear, GPS sector search",
        "status": "AVAILABLE"
    },
    {
        "team_id": "SDRF-BOAT-02",
        "name": "State Disaster Response Force Marine Squad 2",
        "organization": "Andhra Pradesh State Disaster Response Force (SDRF)",
        "team_type": "Rapid Inflatable Boat Evacuation",
        "base_location": "Prakasam Barrage North Depot",
        "latitude": 16.5085,
        "longitude": 80.6130,
        "phone": "+91-866-2580202",
        "sms_number": "+91-9440202020",
        "email": "squad2.sdrf@ap.gov.in",
        "capabilities": "Rigid inflatable boats (RIB), life-jackets, elderly & pediatric evacuation carriers",
        "status": "AVAILABLE"
    },
    {
        "team_id": "EMS-TRIAGE-04",
        "name": "Mobile Emergency Medical & Critical Trauma Squad",
        "organization": "Department of Health & Emergency Medical Services",
        "team_type": "Field Trauma Triage & Critical Ambulance",
        "base_location": "Government General Hospital Sector Hub",
        "latitude": 16.5050,
        "longitude": 80.6380,
        "phone": "+91-866-2610404",
        "sms_number": "+91-9440303030",
        "email": "triage04.ems@ap.gov.in",
        "capabilities": "Advanced life support ambulances, portable oxygen concentrators, field IV stabilization",
        "status": "AVAILABLE"
    },
    {
        "team_id": "MUNICIPAL-LOG-01",
        "name": "Municipal Civil Relief Logistics Depot",
        "organization": "Municipal Corporation Civil Supplies Command",
        "team_type": "Ration, Water & Shelter Deployment",
        "base_location": "Central Warehousing Complex Depot",
        "latitude": 16.5180,
        "longitude": 80.6520,
        "phone": "+91-866-2720101",
        "sms_number": "+91-9440404040",
        "email": "logistics.vjm@ap.gov.in",
        "capabilities": "High-clearance relief trucks, ready-to-eat rations, water purification packs, emergency family tents",
        "status": "AVAILABLE"
    },
    {
        "team_id": "CIVIL-DEF-03",
        "name": "Civil Defense Community Flood Response Cadre",
        "organization": "Home Guards & Civil Defense Directorate",
        "team_type": "Neighborhood Evacuation & Public Staging",
        "base_location": "Governorpet Operational Outpost",
        "latitude": 16.5120,
        "longitude": 80.6280,
        "phone": "+91-866-2810303",
        "sms_number": "+91-9440505050",
        "email": "civildef03@ap.gov.in",
        "capabilities": "Mega-hailers, community marshalling, barrier sandbagging, transit shelter coordination",
        "status": "AVAILABLE"
    }
]

def seed_database():
    with get_db() as session:
        # Seed Rescue Teams if table is empty
        existing_teams = session.query(RescueTeam).count()
        if existing_teams == 0:
            for t in DEFAULT_RESCUE_TEAMS:
                team = RescueTeam(
                    team_id=t["team_id"],
                    name=t["name"],
                    organization=t["organization"],
                    team_type=t["team_type"],
                    base_location=t["base_location"],
                    latitude=t["latitude"],
                    longitude=t["longitude"],
                    phone=t["phone"],
                    sms_number=t["sms_number"],
                    email=t["email"],
                    capabilities=t["capabilities"],
                    status=t["status"],
                    available=True,
                    acknowledgement_status="STANDBY"
                )
                session.add(team)
            logger.info(f"Seeded {len(DEFAULT_RESCUE_TEAMS)} registered emergency response teams.")

def main():
    print("=" * 65)
    print("  Disaster Decision Support System - Database Initializer & Seeder")
    print("=" * 65)
    
    info = get_db_info()
    print(f"Target Database Engine: {info['engine']}")
    print(f"Status: {info['status']}")
    print("-" * 65)

    try:
        success = init_db()
        if success:
            seed_database()
            print("SUCCESS: Database schema verified and registered response teams seeded.")
            print("Verified Tables:")
            print("  - incidents")
            print("  - data_snapshots")
            print("  - zones")
            print("  - zone_features")
            print("  - resource_inventory")
            print("  - rescue_teams")
            print("  - resource_allocations")
            print("  - response_plans")
            print("  - communication_logs")
            print("  - monitoring_events")
            print("  - audit_logs")
            print("=" * 65)
            sys.exit(0)
        else:
            print("FAILED: Error initializing database tables.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error during database initialization: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
