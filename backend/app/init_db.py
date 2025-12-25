import os
import time
from sqlalchemy import create_engine, text

time.sleep(3)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rockhound:minerals@localhost:5432/rockhound_db")

def init_db():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("🔌 Connecting to Database...")
        conn.execute(text("COMMIT"))
        
        print("🌍 Enabling PostGIS...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
        
        print("🔨 Creating Table 'formations'...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS formations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                age VARCHAR(50),
                lithology TEXT,
                geom GEOMETRY(POLYGON, 4326)
            );
        """))
        conn.commit()
        
        print("🌱 Seeding Geological Data...")
        result = conn.execute(text("SELECT count(*) FROM formations WHERE name = 'Warsaw Formation'"))
        if result.scalar() == 0:
            insert_query = text("""
                INSERT INTO formations (name, age, lithology, geom)
                VALUES (
                    'Warsaw Formation',
                    'Mississippian (340 MYA)',
                    'Shale, Limestone, Geodes (Quartz/Calcite)',
                    ST_GeomFromText('POLYGON((-91.5 40.3, -89.5 40.3, -89.5 40.8, -91.5 40.8, -91.5 40.3))', 4326)
                );
            """)
            conn.execute(insert_query)
            conn.commit()
            print("✅ Seeded 'Warsaw Formation' (Covers Bartonville/Peoria area)")
        else:
            print("⏩ Data already exists. Skipping seed.")

if __name__ == "__main__":
    init_db()
