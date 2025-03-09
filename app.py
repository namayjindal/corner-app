import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template
import logging
from generate_embeddings import EmbeddingGenerator
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration - Get from environment variables or use defaults
db_config = {
    "dbname": os.environ.get("DB_NAME", "corner_db"),
    "user": os.environ.get("DB_USER", "namayjindal"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "host": os.environ.get("DB_HOST", "localhost")
}

# Initialize the embedding generator
embedding_generator = EmbeddingGenerator(db_config)

@app.route('/')
def index():
    """Render the main search page"""
    return render_template('index.html')

@app.route('/api/search', methods=['GET'])
def search():
    """API endpoint for enhanced search functionality with optional similarity breakdown"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    # debug = request.args.get('debug', 'false').lower() == 'true'

    debug = True

    print(f"DEBUG FLAG: {debug}")
    
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    try:
        # Use the debug version or regular version based on flag
        if debug:
            results = embedding_generator.search_places_with_meaningful_breakdown(query, limit=limit)
        else:
            results = embedding_generator.search_places_with_enhanced_query(query, limit=limit)
        
        # Convert results to a more frontend-friendly format
        formatted_results = []
        for result in results:
            # Updated to handle both result formats (from both search functions)
            if len(result) >= 7:  # For search_places_with_meaningful_breakdown
                place_id, name, neighborhood, tags, price_range, description, similarity = result
            else:  # For search_places_with_enhanced_query
                place_id, name, neighborhood, tags, price_range, description, similarity = result
            
            # Parse tags if they're in string format
            if tags and isinstance(tags, str):
                if tags.startswith('{') and tags.endswith('}'):
                    tags = tags.strip('{}').split(',')
                    tags = [tag.strip('"\'') for tag in tags]
            
            # Fetch Google ID for this place
            google_id = get_place_google_id(place_id)
            
            formatted_results.append({
                "id": place_id,
                "name": name,
                "neighborhood": neighborhood,
                "tags": tags,
                "price_range": price_range,
                "description": description[:200] + "..." if description and len(description) > 200 else description,
                "similarity": round(similarity * 100, 2),  # Convert to percentage for frontend
                "google_id": google_id  # Add Google ID to results
            })
        
        # Log the search query for future analysis
        try:
            with open('corner_recent_queries.csv', 'a') as f:
                timestamp = datetime.now().isoformat()
                f.write(f'"{query}",{timestamp}\n')
        except Exception as e:
            logger.warning(f"Failed to log search query: {e}")
        
        return jsonify({"results": formatted_results})
    
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return jsonify({"error": "An error occurred during search", "details": str(e)}), 500

def get_place_google_id(place_id):
    """Get Google ID for a place from the database"""
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            cur.execute("SELECT google_id FROM places WHERE id = %s", (place_id,))
            result = cur.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error fetching Google ID: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

@app.route('/api/place/<int:place_id>', methods=['GET'])
def get_place(place_id):
    """Get detailed information about a place"""
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get place details
            cur.execute("""
                SELECT 
                    p.id, p.name, p.neighborhood, p.website, p.instagram_handle,
                    p.price_range, p.combined_description, p.tags, p.address, p.hours,
                    p.google_id
                FROM places p 
                WHERE p.id = %s
            """, (place_id,))
            place = cur.fetchone()
            
            if not place:
                return jsonify({"error": "Place not found"}), 404
            
            # Get reviews
            cur.execute("""
                SELECT source, review_text
                FROM reviews
                WHERE place_id = %s
                LIMIT 5
            """, (place_id,))
            reviews = cur.fetchall()
            
            place['reviews'] = [dict(review) for review in reviews]
            
            return jsonify(place)
    
    except Exception as e:
        logger.error(f"Error getting place details: {str(e)}")
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/recent_queries', methods=['GET'])
def get_recent_queries():
    """Get recent popular search queries"""
    try:
        # Read from the CSV file
        with open('corner_recent_queries.csv', 'r') as f:
            # Skip header and read first 20 lines
            lines = f.readlines()[1:21]
            
        # Extract just the query part
        queries = [line.split(',')[0].strip('"') for line in lines]
        
        return jsonify({"queries": queries})
    except Exception as e:
        logger.error(f"Error getting recent queries: {str(e)}")
        return jsonify({"queries": []})  # Return empty list on error

@app.route('/api/import_google_ids', methods=['POST'])
def import_google_ids():
    """Import Google IDs from the places.csv file"""
    try:
        # Check if user is authorized (simple password protection)
        password = request.form.get('password')
        if password != os.environ.get("ADMIN_PASSWORD", "corner_admin"):
            return jsonify({"error": "Unauthorized"}), 401
        
        # Read the places.csv file
        import csv
        google_ids = {}
        with open('places.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                corner_place_id = row.get('corner_place_id')
                google_id = row.get('google_id')
                if corner_place_id and google_id:
                    google_ids[corner_place_id] = google_id
        
        # Connect to database and update Google IDs
        conn = psycopg2.connect(**db_config)
        updated_count = 0
        try:
            with conn.cursor() as cur:
                # Add google_id column if it doesn't exist
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'places' AND column_name = 'google_id'
                """)
                if not cur.fetchone():
                    cur.execute("ALTER TABLE places ADD COLUMN google_id TEXT")
                
                # Update places with their Google IDs
                for corner_id, google_id in google_ids.items():
                    cur.execute("""
                        UPDATE places 
                        SET google_id = %s
                        WHERE corner_place_id = %s
                    """, (google_id, corner_id))
                    updated_count += cur.rowcount
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating Google IDs: {str(e)}")
            return jsonify({"error": "Database error", "details": str(e)}), 500
        finally:
            conn.close()
        
        return jsonify({
            "success": True,
            "message": f"Updated {updated_count} places with Google IDs",
            "total_google_ids": len(google_ids)
        })
    
    except Exception as e:
        logger.error(f"Error importing Google IDs: {str(e)}")
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get("DEBUG", "False").lower() == "true")