import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template
import logging
from generate_embeddings import EmbeddingGenerator

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
    """API endpoint for search functionality"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    try:
        # Use your existing vector search functionality
        results = embedding_generator.search_places_with_location(query, limit=limit)
        
        # Convert results to a more frontend-friendly format
        formatted_results = []
        for result in results:
            place_id, name, neighborhood, tags, price_range, description, similarity = result
            
            # Parse tags if they're in string format
            if tags and isinstance(tags, str):
                if tags.startswith('{') and tags.endswith('}'):
                    tags = tags.strip('{}').split(',')
                    tags = [tag.strip('"\'') for tag in tags]
            
            formatted_results.append({
                "id": place_id,
                "name": name,
                "neighborhood": neighborhood,
                "tags": tags,
                "price_range": price_range,
                "description": description[:200] + "..." if description and len(description) > 200 else description,
                "similarity": round(similarity * 100, 2)  # Convert to percentage for frontend
            })
        
        return jsonify({"results": formatted_results})
    
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return jsonify({"error": "An error occurred during search", "details": str(e)}), 500

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
                    p.price_range, p.combined_description, p.tags, p.address, p.hours
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get("DEBUG", "False").lower() == "true")