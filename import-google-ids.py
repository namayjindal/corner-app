import os
import csv
import psycopg2
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
db_config = {
    "dbname": os.environ.get("DB_NAME", "corner_db"),
    "user": os.environ.get("DB_USER", "namayjindal"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "host": os.environ.get("DB_HOST", "localhost")
}

def ensure_google_id_column():
    """Ensure the Google ID column exists in the places table"""
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            # Check if the column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'places' AND column_name = 'google_id'
            """)
            
            if not cur.fetchone():
                # Add the column if it doesn't exist
                logger.info("Adding google_id column to places table")
                cur.execute("ALTER TABLE places ADD COLUMN google_id TEXT")
                conn.commit()
                logger.info("google_id column added successfully")
            else:
                logger.info("google_id column already exists")
                
    except Exception as e:
        logger.error(f"Error ensuring google_id column: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def import_google_ids_from_csv(csv_file='places.csv'):
    """Import Google IDs from CSV file into database"""
    conn = None
    try:
        # Read the CSV file
        google_ids = {}
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                corner_place_id = row.get('corner_place_id')
                google_id = row.get('google_id')
                if corner_place_id and google_id:
                    google_ids[corner_place_id] = google_id
        
        logger.info(f"Read {len(google_ids)} Google IDs from CSV file")
        
        # Connect to database and update Google IDs
        conn = psycopg2.connect(**db_config)
        updated_count = 0
        
        with conn.cursor() as cur:
            # Update places with their Google IDs
            for corner_id, google_id in google_ids.items():
                cur.execute("""
                    UPDATE places 
                    SET google_id = %s
                    WHERE corner_place_id = %s
                """, (google_id, corner_id))
                updated_count += cur.rowcount
            
            conn.commit()
            
        logger.info(f"Updated {updated_count} places with Google IDs")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error importing Google IDs: {str(e)}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

def main():
    """Main function to run the script"""
    logger.info("Starting Google ID import process")
    
    # Ensure the google_id column exists
    ensure_google_id_column()
    
    # Import Google IDs from CSV
    count = import_google_ids_from_csv()
    
    logger.info(f"Import process complete. Updated {count} places.")

if __name__ == "__main__":
    main()