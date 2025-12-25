"""
Database module for Rockhound-GO
Handles PostgreSQL/PostGIS initialization and geospatial query functions
"""

import os
from typing import List, Dict, Tuple, Optional, Any
from contextlib import contextmanager
import logging

import psycopg2
from psycopg2 import sql, extras
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DatabaseConfig:
    """Configuration class for database connection parameters"""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME', 'rockhound_go')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'password')
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '2'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))


class DatabaseManager:
    """Manages database connections and PostGIS initialization"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize DatabaseManager with connection pool
        
        Args:
            config: DatabaseConfig instance (creates default if None)
        """
        self.config = config or DatabaseConfig()
        self.connection_pool: Optional[SimpleConnectionPool] = None
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize connection pool"""
        try:
            self.connection_pool = SimpleConnectionPool(
                self.config.min_connections,
                self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for getting database connections from pool
        
        Yields:
            psycopg2 connection object
        """
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def initialize_postgis(self) -> bool:
        """
        Initialize PostGIS extension and create necessary spatial tables/indexes
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Enable PostGIS extension
                    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")
                    
                    logger.info("PostGIS extensions enabled")
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostGIS: {e}")
            return False
    
    def create_spatial_tables(self) -> bool:
        """
        Create spatial tables for rock formations and geosites
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create rock formations table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS rock_formations (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            location GEOMETRY(POINT, 4326) NOT NULL,
                            rock_type VARCHAR(100),
                            age_period VARCHAR(100),
                            coordinates GEOMETRY(POINT, 4326) GENERATED ALWAYS AS (location) STORED,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Create geosites table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS geosites (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            location GEOMETRY(POINT, 4326) NOT NULL,
                            area GEOMETRY(POLYGON, 4326),
                            significance_level VARCHAR(50),
                            accessibility VARCHAR(50),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Create user locations tracking table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_locations (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            location GEOMETRY(POINT, 4326) NOT NULL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            accuracy FLOAT
                        );
                    """)
                    
                    # Create spatial indexes
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_rock_formations_location 
                        ON rock_formations USING GIST(location);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_geosites_location 
                        ON geosites USING GIST(location);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_geosites_area 
                        ON geosites USING GIST(area);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_locations_location 
                        ON user_locations USING GIST(location);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_locations_timestamp 
                        ON user_locations(timestamp);
                    """)
                    
                    logger.info("Spatial tables and indexes created successfully")
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to create spatial tables: {e}")
            return False
    
    def close_pool(self) -> None:
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Connection pool closed")


class GeospatialQueryManager:
    """Manages geospatial queries for rock formations and geosites"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize with DatabaseManager instance
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
    
    def find_nearby_formations(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000
    ) -> List[Dict[str, Any]]:
        """
        Find rock formations within a specified radius of a location
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius_meters: Search radius in meters (default: 5km)
        
        Returns:
            List of rock formations with distance information
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            name,
                            description,
                            rock_type,
                            age_period,
                            ST_AsGeoJSON(location) as location_geojson,
                            ST_Distance(location, ST_SetSRID(ST_Point(%s, %s), 4326)) as distance_meters
                        FROM rock_formations
                        WHERE ST_DWithin(
                            location,
                            ST_SetSRID(ST_Point(%s, %s), 4326),
                            %s
                        )
                        ORDER BY distance_meters ASC;
                    """, (longitude, latitude, longitude, latitude, radius_meters))
                    
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error finding nearby formations: {e}")
            return []
    
    def find_geosites_in_area(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float
    ) -> List[Dict[str, Any]]:
        """
        Find geosites within a bounding box
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude
        
        Returns:
            List of geosites within the bounding box
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            name,
                            description,
                            significance_level,
                            accessibility,
                            ST_AsGeoJSON(location) as location_geojson,
                            ST_AsGeoJSON(area) as area_geojson
                        FROM geosites
                        WHERE ST_Intersects(
                            location,
                            ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                        )
                        ORDER BY significance_level DESC;
                    """, (min_lon, min_lat, max_lon, max_lat))
                    
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error finding geosites in area: {e}")
            return []
    
    def find_formations_by_rock_type(
        self,
        rock_type: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: float = 10000
    ) -> List[Dict[str, Any]]:
        """
        Find rock formations by type, optionally filtered by proximity
        
        Args:
            rock_type: Type of rock (e.g., 'granite', 'basalt')
            latitude: Optional latitude for proximity filter
            longitude: Optional longitude for proximity filter
            radius_meters: Search radius if location provided
        
        Returns:
            List of matching rock formations
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    if latitude and longitude:
                        cur.execute("""
                            SELECT 
                                id,
                                name,
                                description,
                                rock_type,
                                age_period,
                                ST_AsGeoJSON(location) as location_geojson,
                                ST_Distance(location, ST_SetSRID(ST_Point(%s, %s), 4326)) as distance_meters
                            FROM rock_formations
                            WHERE LOWER(rock_type) = LOWER(%s)
                            AND ST_DWithin(
                                location,
                                ST_SetSRID(ST_Point(%s, %s), 4326),
                                %s
                            )
                            ORDER BY distance_meters ASC;
                        """, (longitude, latitude, rock_type, longitude, latitude, radius_meters))
                    else:
                        cur.execute("""
                            SELECT 
                                id,
                                name,
                                description,
                                rock_type,
                                age_period,
                                ST_AsGeoJSON(location) as location_geojson
                            FROM rock_formations
                            WHERE LOWER(rock_type) = LOWER(%s)
                            ORDER BY name ASC;
                        """, (rock_type,))
                    
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error finding formations by rock type: {e}")
            return []
    
    def get_distance_between_points(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> Optional[float]:
        """
        Calculate distance between two geographic points
        
        Args:
            lat1: First point latitude
            lon1: First point longitude
            lat2: Second point latitude
            lon2: Second point longitude
        
        Returns:
            Distance in meters, or None if calculation fails
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT ST_Distance(
                            ST_SetSRID(ST_Point(%s, %s), 4326),
                            ST_SetSRID(ST_Point(%s, %s), 4326)
                        ) as distance;
                    """, (lon1, lat1, lon2, lat2))
                    
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return None
    
    def add_rock_formation(
        self,
        name: str,
        latitude: float,
        longitude: float,
        rock_type: str,
        age_period: str,
        description: Optional[str] = None
    ) -> Optional[int]:
        """
        Add a new rock formation to the database
        
        Args:
            name: Formation name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            rock_type: Type of rock
            age_period: Geological age period
            description: Optional description
        
        Returns:
            ID of inserted formation, or None if failed
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO rock_formations 
                        (name, location, rock_type, age_period, description)
                        VALUES (%s, ST_SetSRID(ST_Point(%s, %s), 4326), %s, %s, %s)
                        RETURNING id;
                    """, (name, longitude, latitude, rock_type, age_period, description))
                    
                    result = cur.fetchone()
                    conn.commit()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding rock formation: {e}")
            return None
    
    def add_geosite(
        self,
        name: str,
        latitude: float,
        longitude: float,
        significance_level: str,
        accessibility: str,
        description: Optional[str] = None,
        area_coords: Optional[List[Tuple[float, float]]] = None
    ) -> Optional[int]:
        """
        Add a new geosite to the database
        
        Args:
            name: Geosite name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            significance_level: Level of significance
            accessibility: Accessibility level
            description: Optional description
            area_coords: Optional list of (lat, lon) tuples for polygon area
        
        Returns:
            ID of inserted geosite, or None if failed
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    if area_coords:
                        # Convert coordinates to WKT polygon format
                        coords_str = ", ".join([f"{lon} {lat}" for lat, lon in area_coords])
                        area_geom = f"ST_SetSRID(ST_GeomFromText('POLYGON(({coords_str})'), 4326)"
                        
                        cur.execute(f"""
                            INSERT INTO geosites 
                            (name, location, area, significance_level, accessibility, description)
                            VALUES (%s, ST_SetSRID(ST_Point(%s, %s), 4326), {area_geom}, %s, %s, %s)
                            RETURNING id;
                        """, (name, longitude, latitude, significance_level, accessibility, description))
                    else:
                        cur.execute("""
                            INSERT INTO geosites 
                            (name, location, significance_level, accessibility, description)
                            VALUES (%s, ST_SetSRID(ST_Point(%s, %s), 4326), %s, %s, %s)
                            RETURNING id;
                        """, (name, longitude, latitude, significance_level, accessibility, description))
                    
                    result = cur.fetchone()
                    conn.commit()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding geosite: {e}")
            return None
    
    def track_user_location(
        self,
        user_id: int,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None
    ) -> bool:
        """
        Track user location for geospatial analytics
        
        Args:
            user_id: User ID
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            accuracy: Optional accuracy in meters
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_locations 
                        (user_id, location, accuracy)
                        VALUES (%s, ST_SetSRID(ST_Point(%s, %s), 4326), %s);
                    """, (user_id, longitude, latitude, accuracy))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error tracking user location: {e}")
            return False
    
    def get_user_location_history(
        self,
        user_id: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get user location history
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
        
        Returns:
            List of user location records
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            user_id,
                            ST_AsGeoJSON(location) as location_geojson,
                            timestamp,
                            accuracy
                        FROM user_locations
                        WHERE user_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s;
                    """, (user_id, limit))
                    
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving user location history: {e}")
            return []


# Module-level database instance (singleton pattern)
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get or create the global DatabaseManager instance
    
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_geospatial_query_manager() -> GeospatialQueryManager:
    """
    Get a GeospatialQueryManager instance
    
    Returns:
        GeospatialQueryManager instance
    """
    return GeospatialQueryManager(get_database_manager())


def initialize_database() -> bool:
    """
    Initialize the database with PostGIS and spatial tables
    
    Returns:
        True if successful, False otherwise
    """
    db_manager = get_database_manager()
    
    if not db_manager.initialize_postgis():
        return False
    
    if not db_manager.create_spatial_tables():
        return False
    
    logger.info("Database initialized successfully")
    return True
