# Corner - NYC Place Search

A simple web application to search for places in New York City using vector search.

## Quick Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Make sure you have the following environment variables set:
   ```
   DB_NAME=corner_db
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_HOST=localhost
   OPENAI_KEY=your_openai_api_key
   GOOGLE_API_KEY=your_google_api_key
   ```

3. Run the Flask app:
   ```
   python app.py
   ```

4. Visit http://localhost:5000 in your browser

## Deployment to Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Add environment variables in the Render dashboard
5. Deploy!

## Project Structure

- `app.py`: Main Flask application that handles routes and API endpoints
- `generate_embeddings.py`: Core vector search functionality and semantic query processing
- `location_extraction.py`: Helper module for extracting locations from queries
- `import-google-ids.py`: Script to import Google Place IDs for map integration
- `templates/`: HTML templates
- `static/`: CSS and JavaScript files

## Setup Process

To set up this project from scratch, follow these steps:

1. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

2. Set up a PostgreSQL database with the pgvector extension
   ```sql
   CREATE EXTENSION vector;
   ```

3. Create the necessary tables (places, embeddings, reviews)
   ```sql
   CREATE TABLE places (
     id SERIAL PRIMARY KEY,
     name TEXT NOT NULL,
     neighborhood TEXT,
     website TEXT,
     instagram_handle TEXT,
     price_range TEXT,
     combined_description TEXT,
     tags TEXT[],
     address TEXT,
     hours JSONB,
     amenities JSONB DEFAULT '{}'::jsonb,
     google_id TEXT,
     corner_place_id TEXT,
     metadata JSONB,
     updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE embeddings (
     id SERIAL PRIMARY KEY,
     place_id INTEGER REFERENCES places(id),
     embedding vector(1536),
     content_type TEXT DEFAULT 'combined',
     last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE reviews (
     id SERIAL PRIMARY KEY,
     place_id INTEGER REFERENCES places(id),
     source TEXT,
     review_text TEXT
   );
   ```

4. Import Google Place IDs for map integration:
   ```
   python import-google-ids.py
   ```

5. Generate vector embeddings for places:
   ```
   python generate_embeddings.py
   ```

6. Run the Flask app:
   ```
   python app.py
   ```

## Data Flow

1. The web scraping pipeline (separate repository) generates the initial data in `combined_data.json`
2. The `places.csv` file maps Corner's place IDs to Google Place IDs
3. `import-google-ids.py` imports these mappings into the database
4. `generate_embeddings.py` processes place data to create vector embeddings
5. The Flask app serves the frontend and provides API endpoints for search

## Features

- Search for places by keyword, neighborhood, or type
- Category-based query processing with semantic understanding
- Location-aware search with neighborhood filtering
- View detailed information about each place
- Interactive map integration with Google Maps
- Mobile-responsive design

## Potential Improvements and Drawbacks

### Current Limitations

1. **Price and Timing Matching**: The current implementation doesn't account well enough for price ranges and operating hours. When users search for "cheap dinner" or "open late", the results may not be optimal.

2. **Location Matching**: While the app extracts neighborhoods from queries, it doesn't use coordinate-based proximity ranking, which limits accuracy for location-specific searches.

3. **Limited Data Pool**: The current database has a limited number of places, which affects the range and quality of search results.

4. **Basic Ranking Algorithm**: The ranking relies heavily on embedding similarity without incorporating popularity metrics or quality indicators.

### Proposed Improvements

1. **Enhanced Price Processing**:
   - Add more semantic meaning to price ranges during embedding creation
   - Expand price-related vocabulary in query expansion
   - Create structured price level attributes for more precise filtering

2. **Coordinate-Based Location Ranking**:
   - Implement geospatial indexing in the database
   - Calculate and rank by actual distance between places and search locations
   - Support radius-based searches (e.g., "within 1 mile of Union Square")

3. **Data Expansion**:
   - Integrate with additional data sources
   - Implement a periodic data refresh pipeline
   - Add user-generated content/corrections

4. **Advanced Ranking Algorithm**:
   - Incorporate Google ratings and review counts
   - Add recency factors to prioritize newer, trending places
   - Implement a hybrid ranking model that balances relevance and popularity

5. **User Experience Enhancements**:
   - Add filters for specific attributes (price, open now, amenities)
   - Implement personalized recommendations based on past searches
   - Add user accounts to save favorite places

6. **Performance Optimization**:
   - Implement caching for common searches
   - Optimize database queries and indexing
   - Add pagination for large result sets

7. **Additional Features**:
   - Support for advanced filtering options
   - Integration with reservation systems
   - Social sharing capabilities

Implementing these improvements would significantly enhance the search experience and make the application more useful for real-world scenarios.