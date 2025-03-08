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

- `app.py`: Main Flask application
- `generate_embeddings.py`: Vector search functionality
- `templates/`: HTML templates
- `static/`: CSS and JavaScript files

## Features

- Search for places by keyword, neighborhood, or type
- View detailed information about each place
- See reviews, hours, and more