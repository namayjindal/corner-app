import os
import json
import logging
import psycopg2
import pandas as pd
import time
import re
import hashlib
from psycopg2.extras import execute_batch
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
import traceback

# Import the location extraction functionality
from location_extraction import extract_location_from_query, get_adjacent_neighborhoods

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("embeddings.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define dictionaries for query expansion
VIBE_TERMS = {
    'cozy': ['warm', 'intimate', 'homey', 'comfortable', 'snug', 'hygge'],
    'chill': ['relaxed', 'laid-back', 'casual', 'low-key', 'easygoing', 'mellow'],
    'aesthetic': ['stylish', 'beautiful', 'instagrammable', 'pretty', 'photogenic', 'designed', 'trendy'],
    'vibey': ['atmospheric', 'cool', 'trendy', 'hip', 'fun', 'good vibes', 'ambiance'],
    'romantic': ['intimate', 'date night', 'candlelit', 'quiet', 'cozy', 'dimly lit'],
    'cool': ['hip', 'trendy', 'edgy', 'stylish', 'interesting', 'unique'],
    'fancy': ['upscale', 'elegant', 'sophisticated', 'high-end', 'luxurious'],
    'casual': ['relaxed', 'laid-back', 'informal', 'easygoing', 'unpretentious']
}

ESTABLISHMENT_TERMS = {
    'cafe': ['coffee shop', 'bakery', 'pastry shop', 'espresso bar', 'tea house'],
    'bar': ['pub', 'cocktail bar', 'lounge', 'tavern', 'speakeasy', 'dive bar'],
    'restaurant': ['eatery', 'bistro', 'dining', 'diner', 'trattoria', 'brasserie'],
    'bakery': ['patisserie', 'bread shop', 'cake shop', 'pastry shop'],
    'diner': ['breakfast place', 'brunch spot', 'greasy spoon', 'all-day breakfast']
}

CUISINE_TERMS = {
    'italian': ['pasta', 'pizza', 'risotto', 'italian cuisine', 'trattoria', 'italian restaurant'],
    'asian': ['chinese', 'japanese', 'korean', 'thai', 'vietnamese', 'asian cuisine', 'asian fusion'],
    'mexican': ['tacos', 'burritos', 'tex-mex', 'mexican cuisine', 'mexican food'],
    'american': ['burgers', 'sandwiches', 'american cuisine', 'american food', 'new american'],
    'chinese': ['dim sum', 'dumpling', 'noodles', 'chinese cuisine', 'chinese food'],
    'japanese': ['sushi', 'ramen', 'japanese cuisine', 'japanese food', 'izakaya'],
}

PRICE_TERMS = {
    'cheap': ['affordable', 'budget-friendly', 'inexpensive', 'good value', 'low price'],
    'moderate': ['mid-range', 'reasonable', 'moderately priced', 'fair price'],
    'expensive': ['high-end', 'upscale', 'pricey', 'fine dining', 'luxury', 'splurge']
}

ACTIVITY_TERMS = {
    'work': ['wifi', 'laptop friendly', 'outlets', 'coworking', 'study', 'productive'],
    'date': ['romantic', 'date night', 'intimate', 'couples', 'special occasion'],
    'group': ['group dining', 'large parties', 'group friendly', 'communal seating'],
    'party': ['celebration', 'birthday', 'special occasion', 'event', 'gathering'],
    'quiet': ['peaceful', 'calm', 'serene', 'tranquil', 'not crowded']
}

TIME_TERMS = {
    'breakfast': ['morning', 'early', 'brunch', 'breakfast food', 'eggs', 'pastry'],
    'lunch': ['midday', 'noon', 'lunch menu', 'lunch special'],
    'dinner': ['evening', 'night', 'dinner menu', 'supper'],
    'late night': ['open late', 'after hours', 'late', 'midnight', 'night owl']
}

AMENITY_TERMS = {
    'wifi': ['internet', 'wi-fi', 'free wifi', 'internet access'],
    'outdoor seating': ['patio', 'terrace', 'outdoor space', 'alfresco', 'sidewalk seating'],
    'pet friendly': ['dog friendly', 'allows dogs', 'brings dogs', 'canine friendly'],
    'view': ['scenic view', 'overlook', 'vista', 'skyline view', 'waterfront'],
    'live music': ['music venue', 'band', 'performer', 'music performance', 'dj'],
    'reservations': ['takes reservations', 'reservation required', 'reserve ahead'],
    'takeout': ['to go', 'takeaway', 'carryout', 'pickup', 'delivery']
}

class EmbeddingGenerator:
    def __init__(self, db_config):
        """Initialize database configuration and OpenAI client"""
        self.db_config = db_config
        
        # Set up OpenAI client
        openai_api_key = os.getenv("OPENAI_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_KEY environment variable not set")
        
        self.client = OpenAI(api_key=openai_api_key)
        self.model = "text-embedding-ada-002"  # Default embedding model
        
        # Keep track of tokens used for cost estimation
        self.total_tokens = 0
        self.has_pgvector = self._check_pgvector()
    
    def _connect_db(self):
        """Create and return a new database connection and cursor"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        return conn, cur
    
    def _check_pgvector(self):
        """Check if pgvector extension is installed"""
        conn, cur = self._connect_db()
        try:
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            has_pgvector = bool(cur.fetchone())
            if not has_pgvector:
                logger.warning("pgvector extension not installed. Embeddings will not be stored.")
            return has_pgvector
        except Exception as e:
            logger.error(f"Error checking pgvector: {str(e)}")
            return False
        finally:
            cur.close()
            conn.close()

    def clean_price_range(self, price_range):
        """Clean and standardize price range format"""
        if not price_range:
            return None
            
        # If already a string, clean it
        if isinstance(price_range, str):
            # Remove Unicode characters
            price = price_range.replace('\u2013', '-')  # en dash
            price = price.replace('\u2014', '-')  # em dash
            price = price.replace('\u201c', '"')  # left double quote
            price = price.replace('\u201d', '"')  # right double quote
            price = price.replace('\u2018', "'")  # left single quote
            price = price.replace('\u2019', "'")  # right single quote
            
            # Standardize format
            price = re.sub(r'\s+', ' ', price).strip()  # Remove extra spaces
            
            return price
        
        # If it's a number, format it
        if isinstance(price_range, (int, float)):
            return f"${price_range}"
        
        return None

    def process_price_range(self, price_range):
        """Process and add semantic meaning to price range indicators"""
        if not price_range:
            return None
            
        # Clean the price range
        price = self.clean_price_range(price_range)
        if not price:
            return None
        
        # Extract dollar signs if present
        dollar_count = price.count('$')
        if dollar_count > 0:
            price_level = dollar_count
        else:
            # Try to extract numerical ranges (e.g. $10-20, $30-50)
            match = re.search(r'\$?(\d+)(?:[^\d]+)(\d+)', price)
            if match:
                low, high = int(match.group(1)), int(match.group(2))
                avg_price = (low + high) / 2
                if avg_price < 15:
                    price_level = 1
                elif avg_price < 30:
                    price_level = 2
                elif avg_price < 60:
                    price_level = 3
                else:
                    price_level = 4
            else:
                # Try to extract single values
                match = re.search(r'\$?(\d+)', price)
                if match:
                    value = int(match.group(1))
                    if value < 15:
                        price_level = 1
                    elif value < 30:
                        price_level = 2
                    elif value < 60:
                        price_level = 3
                    else:
                        price_level = 4
                else:
                    # If we can't determine, assume mid-range
                    price_level = 2
        
        # Map price levels to descriptive text
        price_descriptions = {
            1: "Budget-friendly, inexpensive, affordable",
            2: "Moderately priced, mid-range",
            3: "Higher-end, upscale, expensive",
            4: "Fine dining, premium, luxury, high-end"
        }
        
        return {
            "original": price,
            "level": price_level,
            "description": price_descriptions.get(price_level, "")
        }

    def process_business_hours(self, hours_data):
        """Process business hours to extract meaningful patterns"""
        if not hours_data:
            return None
            
        parsed_hours = self.parse_hours(hours_data)
        if not parsed_hours:
            return None
        
        hour_patterns = {
            "open_late": False,
            "open_early": False,
            "open_weekends": False,
            "open_breakfast": False,
            "open_lunch": False,
            "open_dinner": False,
            "open_24h": False,
            "closed_mondays": False,
            "days_open": []
        }
        
        # Convert hours to a standardized format for analysis
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_abbrevs = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", 
                    "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
        
        if isinstance(parsed_hours, dict):
            for day, hours_str in parsed_hours.items():
                if hours_str == "Closed":
                    continue
                    
                # Standardize day name
                day_name = day
                for abbrev, full_name in day_abbrevs.items():
                    if abbrev in day or abbrev.lower() in day.lower():
                        day_name = full_name
                        break
                
                hour_patterns["days_open"].append(day_name)
                
                # Check for specific patterns in hours
                if "24" in hours_str:
                    hour_patterns["open_24h"] = True
                    continue
                    
                # Parse actual opening and closing times
                time_patterns = [
                    # 12-hour format: 10 AM to 10 PM
                    r'(\d+(?::\d+)?)\s*([aApP][mM])\s*(?:to|[-–—])\s*(\d+(?::\d+)?)\s*([aApP][mM])',
                    # 24-hour format: 10:00-22:00
                    r'(\d+):(\d+)\s*(?:to|[-–—])\s*(\d+):(\d+)',
                    # Simple format: 10-22
                    r'(\d+)\s*(?:to|[-–—])\s*(\d+)'
                ]
                
                for pattern in time_patterns:
                    match = re.search(pattern, hours_str)
                    if match:
                        # 12-hour format
                        if len(match.groups()) == 4 and match.group(2) and match.group(4):
                            open_hour = int(match.group(1).split(':')[0])
                            close_hour = int(match.group(3).split(':')[0])
                            
                            # Adjust for PM
                            if match.group(2).lower() == 'pm' and open_hour < 12:
                                open_hour += 12
                            if match.group(4).lower() == 'pm' and close_hour < 12:
                                close_hour += 12
                            
                        # 24-hour format
                        elif len(match.groups()) == 4:
                            open_hour = int(match.group(1))
                            close_hour = int(match.group(3))
                            
                        # Simple format
                        else:
                            open_hour = int(match.group(1))
                            close_hour = int(match.group(2))
                        
                        # Check time patterns
                        if open_hour <= 8:
                            hour_patterns["open_early"] = True
                        if open_hour <= 10:
                            hour_patterns["open_breakfast"] = True
                        if open_hour <= 12 and close_hour >= 14:
                            hour_patterns["open_lunch"] = True
                        if close_hour >= 17:
                            hour_patterns["open_dinner"] = True
                        if close_hour >= 22 or close_hour <= 4:  # Late night or early morning closing
                            hour_patterns["open_late"] = True
                        break
        
        # Check weekend operation
        if "Saturday" in hour_patterns["days_open"] or "Sunday" in hour_patterns["days_open"]:
            hour_patterns["open_weekends"] = True
        
        # Check if closed Mondays
        hour_patterns["closed_mondays"] = "Monday" not in hour_patterns["days_open"]
        
        # Generate descriptive text
        descriptions = []
        if hour_patterns["open_early"]:
            descriptions.append("Opens early")
        if hour_patterns["open_late"]:
            descriptions.append("Open late")
        if hour_patterns["open_breakfast"]:
            descriptions.append("Serves breakfast")
        if hour_patterns["open_lunch"]:
            descriptions.append("Open for lunch")
        if hour_patterns["open_dinner"]:
            descriptions.append("Open for dinner")
        if hour_patterns["open_24h"]:
            descriptions.append("Open 24 hours")
        if hour_patterns["open_weekends"]:
            descriptions.append("Open on weekends")
        if hour_patterns["closed_mondays"]:
            descriptions.append("Closed on Mondays")
        
        return {
            "original": parsed_hours,
            "patterns": hour_patterns,
            "description": ", ".join(descriptions)
        }
        
    def fetch_places_needing_embeddings(self):
        """Fetch places that need embeddings generated or updated"""
        logger.info("Fetching places that need embeddings...")
        
        conn, cur = self._connect_db()
        try:
            # First, check for places that have no embeddings at all
            query = """
            SELECT 
                p.id, 
                p.name, 
                p.combined_description, 
                p.tags, 
                p.corner_place_id,
                p.neighborhood,
                p.price_range,
                p.address,
                p.hours,
                p.amenities
            FROM places p
            LEFT JOIN embeddings e ON p.id = e.place_id
            WHERE e.id IS NULL
            """
            cur.execute(query)
            places = cur.fetchall()
            
            # For places with existing embeddings, check if content has changed
            query = """
            SELECT 
                p.id, 
                p.name, 
                p.combined_description, 
                p.tags, 
                p.corner_place_id,
                p.neighborhood,
                p.price_range,
                p.address,
                p.hours,
                p.amenities,
                e.id as embedding_id, 
                e.last_updated
            FROM places p
            JOIN embeddings e ON p.id = e.place_id
            WHERE p.updated_at > e.last_updated
            """
            cur.execute(query)
            updated_places = cur.fetchall()
            
            # Fetch reviews for all places that need embeddings
            all_place_ids = [place[0] for place in places] + [place[0] for place in updated_places]
            
            place_reviews = {}
            if all_place_ids:
                placeholders = ','.join(['%s'] * len(all_place_ids))
                review_query = f"""
                SELECT place_id, review_text
                FROM reviews
                WHERE place_id IN ({placeholders})
                """
                cur.execute(review_query, all_place_ids)
                review_results = cur.fetchall()
                
                # Group reviews by place_id
                for place_id, review_text in review_results:
                    if place_id not in place_reviews:
                        place_reviews[place_id] = []
                    place_reviews[place_id].append(review_text)
            
            logger.info(f"Found {len(places)} places without embeddings and {len(updated_places)} places with outdated embeddings")
            
            return places, updated_places, place_reviews
        
        except Exception as e:
            logger.error(f"Error fetching places: {str(e)}")
            conn.rollback()
            return [], [], {}
        finally:
            cur.close()
            conn.close()
    
    def fetch_resy_data(self, corner_place_id):
        """Fetch Resy data for a place from the combined_data.json file"""
        try:
            with open('combined_data.json', 'r') as f:
                combined_data = json.load(f)
                
            for place in combined_data:
                if str(place.get('corner_place_id')) == str(corner_place_id):
                    return place.get('resy_data', {})
            
            return {}
        except Exception as e:
            logger.warning(f"Error fetching Resy data: {str(e)}")
            return {}
    
    def validate_text(self, text):
        """Validate text before generating embeddings"""
        if not text:
            return False, "Text is empty"
        
        if not isinstance(text, str):
            return False, f"Text is not a string (got {type(text)})"
        
        if len(text) < 10:
            return False, "Text is too short"
        
        # Check for common meaningless text patterns
        low_info_patterns = [
            "not available", "n/a", "none", "unknown", "null", 
            "undefined", "to be added", "coming soon"
        ]
        
        text_lower = text.lower()
        for pattern in low_info_patterns:
            if pattern in text_lower and len(text) < 100:
                return False, f"Text contains low-information pattern: {pattern}"
        
        return True, "Text is valid"
    
    def parse_tags(self, tags_data):
        """Parse tags from various formats"""
        if not tags_data:
            return []
        
        # If already a list, just return it
        if isinstance(tags_data, list):
            return [str(tag).strip() for tag in tags_data if tag]
        
        # If it's a string, try different formats
        if isinstance(tags_data, str):
            # Check if it's a JSON array string
            if tags_data.startswith('[') and tags_data.endswith(']'):
                try:
                    return [str(tag).strip() for tag in json.loads(tags_data) if tag]
                except:
                    pass
            
            # Check if it's a PostgreSQL array format like {tag1,tag2}
            if tags_data.startswith('{') and tags_data.endswith('}'):
                tags = tags_data.strip('{}').split(',')
                return [tag.strip(' "\'') for tag in tags if tag.strip()]
            
            # Check if it's a comma-separated string
            if ',' in tags_data:
                return [tag.strip() for tag in tags_data.split(',') if tag.strip()]
            
            # Just return as a single tag
            return [tags_data.strip()]
        
        return []
    
    def parse_hours(self, hours_data):
        """Parse hours data from various formats"""
        if not hours_data:
            return None
        
        # If it's already a dictionary, return it
        if isinstance(hours_data, dict):
            return hours_data
        
        # If it's a JSON string, parse it
        if isinstance(hours_data, str):
            try:
                return json.loads(hours_data.replace("'", '"'))
            except:
                # Just return as is
                return hours_data
        
        return None
    
    def parse_amenities(self, amenities_data):
        """Parse amenities data into a structured format"""
        if not amenities_data:
            return {}
        
        # If it's already a dictionary, return it
        if isinstance(amenities_data, dict):
            return amenities_data
        
        # If it's a JSON string, parse it
        if isinstance(amenities_data, str):
            try:
                return json.loads(amenities_data.replace("'", '"'))
            except:
                # Try to parse from comma-separated list
                if ',' in amenities_data:
                    amenities = {}
                    for item in amenities_data.split(','):
                        item = item.strip()
                        if item:
                            amenities[item] = True
                    return amenities
                else:
                    # Single amenity
                    return {amenities_data.strip(): True}
        
        return {}
    
    def extract_resy_details(self, resy_data):
        """Extract useful information from Resy data"""
        if not resy_data or not isinstance(resy_data, dict):
            return ""
        
        resy_text = ""
        
        if resy_data.get('why_we_like_it'):
            resy_text += f"Why Resy likes it: {resy_data['why_we_like_it']}\n\n"
        
        if resy_data.get('about'):
            resy_text += f"About: {resy_data['about']}\n\n"
        
        if resy_data.get('need_to_know'):
            resy_text += f"Need to know: {resy_data['need_to_know']}"
            
        return resy_text.strip()
    
    def prepare_text_for_embedding(self, place, reviews):
        """Prepare and validate text for embedding generation including all data sources"""
        # Extract relevant place data
        place_id, name, description = place[0], place[1], place[2]
        tags_data, corner_id = place[3], place[4]
        neighborhood = place[5] if len(place) > 5 else None
        price_range = place[6] if len(place) > 6 else None
        address, hours = place[7] if len(place) > 7 else None, place[8] if len(place) > 8 else None
        amenities = place[9] if len(place) > 9 else None
        
        # Start with the basic info - explicitly exclude location/neighborhood for embedding
        content_parts = [f"Name: {name}"]
        
        # Process price range
        processed_price = self.process_price_range(price_range)
        if processed_price:
            content_parts.append(f"Price Range: {processed_price['original']}")
            content_parts.append(f"Price Category: {processed_price['description']}")
        
        if address:
            # Remove specific address numbers to focus on street names
            generalized_address = re.sub(r'^\d+\s+', '', address)
            content_parts.append(f"Address: {generalized_address}")
        
        # Process hours
        processed_hours = self.process_business_hours(hours)
        if processed_hours:
            if processed_hours['description']:
                content_parts.append(f"Hours Info: {processed_hours['description']}")
        
        # Process amenities
        parsed_amenities = self.parse_amenities(amenities)
        if parsed_amenities:
            amenities_list = [k for k, v in parsed_amenities.items() if v]
            if amenities_list:
                content_parts.append(f"Amenities: {', '.join(amenities_list)}")
        
        # Add description if available
        if description:
            is_valid, msg = self.validate_text(description)
            if is_valid:
                content_parts.append(f"Description: {description}")
        
        # Add tags if available
        tags = self.parse_tags(tags_data)
        if tags:
            content_parts.append(f"Tags: {', '.join(tags)}")
        
        # Fetch and add Resy data
        resy_data = self.fetch_resy_data(corner_id)
        resy_text = self.extract_resy_details(resy_data)
        if resy_text:
            content_parts.append(f"From Resy: {resy_text}")
        
        # Add reviews
        place_reviews = reviews.get(place_id, [])
        if place_reviews:
            # Limit the number of reviews to avoid token limits
            max_reviews = min(5, len(place_reviews))
            selected_reviews = place_reviews[:max_reviews]
            reviews_text = "\n".join([f"- {review[:300]}" for review in selected_reviews])
            content_parts.append(f"Reviews:\n{reviews_text}")
        
        # Join all content parts
        content = "\n\n".join(content_parts)
        
        # Check if we have enough valid content
        if not content or len(content) < 50:
            logger.warning(f"Not enough valid content for place {name} (ID: {place_id})")
            return None, None
        
        # Calculate content hash for detecting changes
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Store the neighborhood separately - it won't be included in the embedding
        # but will be used for filtering
        neighborhood_info = neighborhood
        
        return content, content_hash, neighborhood_info
    
    def generate_embedding(self, text):
        """Generate embedding using OpenAI API"""
        max_retries = 3
        retry_delay = 2
        
        # Safeguard against overly long texts (token limit is around 8191 for text-embedding-ada-002)
        max_chars = 25000  # Approximate character limit for safety
        if len(text) > max_chars:
            logger.warning(f"Text too long ({len(text)} chars), truncating to {max_chars} chars")
            text = text[:max_chars] + "..."
        
        for attempt in range(max_retries):
            try:
                # Generate embedding
                response = self.client.embeddings.create(
                    input=text,
                    model=self.model
                )
                
                # Extract embedding vector
                embedding = response.data[0].embedding
                
                # Track token usage
                tokens_used = response.usage.total_tokens
                self.total_tokens += tokens_used
                
                logger.info(f"Generated embedding successfully. Used {tokens_used} tokens.")
                return embedding, tokens_used
                
            except Exception as e:
                # Implement exponential backoff
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(f"Error generating embedding (attempt {attempt+1}/{max_retries}): {str(e)}")
                logger.warning(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
        
        # If we get here, all retries failed
        logger.error(f"Failed to generate embedding after {max_retries} attempts")
        return None, 0
    
    def store_embedding(self, place_id, embedding, content_type="combined"):
        """Store embedding in the database"""
        if not self.has_pgvector:
            logger.warning("pgvector extension not available, skipping embedding storage")
            return False
        
        conn, cur = self._connect_db()
        try:
            # Check if embedding already exists for this place
            cur.execute(
                "SELECT id FROM embeddings WHERE place_id = %s AND content_type = %s",
                (place_id, content_type)
            )
            
            result = cur.fetchone()
            if result:
                # Update existing embedding
                embedding_id = result[0]
                cur.execute(
                    """
                    UPDATE embeddings 
                    SET embedding = %s::vector, last_updated = CURRENT_TIMESTAMP 
                    WHERE id = %s
                    """,
                    (embedding, embedding_id)
                )
                logger.info(f"Updated embedding {embedding_id} for place {place_id}")
            else:
                # Insert new embedding
                cur.execute(
                    """
                    INSERT INTO embeddings (place_id, embedding, content_type, last_updated)
                    VALUES (%s, %s::vector, %s, CURRENT_TIMESTAMP)
                    """,
                    (place_id, embedding, content_type)
                )
                logger.info(f"Created new embedding for place {place_id}")
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing embedding for place {place_id}: {str(e)}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def update_embedding_status(self, place_id, status, message=None):
        """Update the place with embedding status metadata"""
        conn, cur = self._connect_db()
        try:
            # Add metadata about embedding status
            query = """
            UPDATE places 
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{embedding_status}',
                %s::jsonb
            )
            WHERE id = %s
            """
            
            status_data = json.dumps({
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "message": message
            })
            
            cur.execute(query, (status_data, place_id))
            conn.commit()
            
        except Exception as e:
            logger.warning(f"Failed to update embedding status: {str(e)}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def process_all_places(self):
        """Process all places that need embeddings"""
        try:
            # Fetch places that need embeddings
            new_places, updated_places, place_reviews = self.fetch_places_needing_embeddings()
            
            if not new_places and not updated_places:
                logger.info("No places need embeddings. All up to date!")
                return
            
            # Process new places
            total_places = len(new_places) + len(updated_places)
            processed = 0
            
            for place in new_places:
                place_id, name = place[0], place[1]
                logger.info(f"Processing new place: {name} (ID: {place_id}) - {processed+1}/{total_places}")
                
                # Prepare text and validate
                content, content_hash, neighborhood = self.prepare_text_for_embedding(place, place_reviews)
                
                if not content:
                    self.update_embedding_status(place_id, "failed", "No valid content for embedding")
                    processed += 1
                    continue
                
                # Generate embedding
                embedding, tokens = self.generate_embedding(content)
                
                if embedding:
                    # Store embedding
                    success = self.store_embedding(place_id, embedding)
                    
                    if success:
                        self.update_embedding_status(place_id, "success", f"Used {tokens} tokens")
                    else:
                        self.update_embedding_status(place_id, "failed", "Failed to store embedding")
                else:
                    self.update_embedding_status(place_id, "failed", "Failed to generate embedding")
                
                processed += 1
                
                # Add a small delay between calls to avoid rate limiting
                time.sleep(0.5)
            
            # Process updated places
            for place in updated_places:
                place_id, name = place[0], place[1]
                embedding_id = place[10] if len(place) > 10 else None
                
                logger.info(f"Processing updated place: {name} (ID: {place_id}) - {processed+1}/{total_places}")
                
                # Prepare text and validate
                content, content_hash, neighborhood = self.prepare_text_for_embedding(place, place_reviews)
                
                if not content:
                    self.update_embedding_status(place_id, "failed", "No valid content for embedding")
                    processed += 1
                    continue
                
                # Generate embedding
                embedding, tokens = self.generate_embedding(content)
                
                if embedding:
                    # Store embedding
                    success = self.store_embedding(place_id, embedding)
                    
                    if success:
                        self.update_embedding_status(place_id, "updated", f"Used {tokens} tokens")
                    else:
                        self.update_embedding_status(place_id, "failed", "Failed to update embedding")
                else:
                    self.update_embedding_status(place_id, "failed", "Failed to generate embedding")
                
                processed += 1
                
                # Add a small delay between calls to avoid rate limiting
                time.sleep(0.5)
            
            # Log summary
            logger.info(f"Embedding generation complete.")
            logger.info(f"Processed {total_places} places.")
            logger.info(f"Total tokens used: {self.total_tokens}")
            logger.info(f"Estimated cost: ${(self.total_tokens / 1000) * 0.0001:.4f} (at $0.0001 per 1K tokens)")
            
            return self.total_tokens
            
        except Exception as e:
            logger.error(f"Error processing places: {str(e)}")
            logger.error(traceback.format_exc())
            return 0
    
    def parse_query(self, query):
        """
        Parse a query into categorized tokens
        
        Returns:
            dict: Dictionary with categorized tokens and cleaned query
        """
        result = {
            'location': None,
            'vibe': [],
            'establishment': [],
            'cuisine': [],
            'price': [],
            'activity': [],
            'time': [],
            'amenities': [],
            'group_size': [],
            'cleaned_query': query,
            'original_query': query
        }
        
        # First extract location to remove it from embedding consideration
        cleaned_query, location = extract_location_from_query(query)
        result['location'] = location
        result['cleaned_query'] = cleaned_query
        
        # Process query text to identify various categories
        query_lower = cleaned_query.lower()
        
        # Identify vibe terms
        for term, synonyms in VIBE_TERMS.items():
            if term in query_lower or any(syn in query_lower for syn in synonyms):
                result['vibe'].append(term)
        
        # Identify establishment types
        for est_type, synonyms in ESTABLISHMENT_TERMS.items():
            if est_type in query_lower or any(syn in query_lower for syn in synonyms):
                result['establishment'].append(est_type)
        
        # Identify cuisine types
        for cuisine, synonyms in CUISINE_TERMS.items():
            if cuisine in query_lower or any(syn in query_lower for syn in synonyms):
                result['cuisine'].append(cuisine)
        
        # Identify price terms
        for price, synonyms in PRICE_TERMS.items():
            if price in query_lower or any(syn in query_lower for syn in synonyms):
                result['price'].append(price)
        
        # Identify activity terms
        for activity, synonyms in ACTIVITY_TERMS.items():
            if activity in query_lower or any(syn in query_lower for syn in synonyms):
                result['activity'].append(activity)
        
        # Identify time-related terms
        for time, synonyms in TIME_TERMS.items():
            if time in query_lower or any(syn in query_lower for syn in synonyms):
                result['time'].append(time)
        
        # Identify amenity terms
        for amenity, synonyms in AMENITY_TERMS.items():
            if amenity in query_lower or any(syn in query_lower for syn in synonyms):
                result['amenities'].append(amenity)
        
        # Check for group size indicators
        if any(term in query_lower for term in ['group', 'party', 'gathering', 'crowd']):
            result['group_size'].append('large')
        elif any(term in query_lower for term in ['solo', 'alone', 'by myself', 'single']):
            result['group_size'].append('solo')
        elif any(term in query_lower for term in ['date', 'couple', 'two people']):
            result['group_size'].append('couple')
        
        return result
    
    def expand_query(self, parsed_query):
        """
        Expand a query based on the parsed categories
        
        Args:
            parsed_query: Dictionary from parse_query
            
        Returns:
            str: Expanded query
        """
        original_query = parsed_query['cleaned_query']
        expansions = []
        
        # Add vibe expansions
        for vibe in parsed_query['vibe']:
            if vibe in VIBE_TERMS:
                # Only take top 3 synonyms to avoid diluting the query
                expansions.extend(VIBE_TERMS[vibe][:3])
        
        # Add establishment expansions
        for est in parsed_query['establishment']:
            if est in ESTABLISHMENT_TERMS:
                expansions.extend(ESTABLISHMENT_TERMS[est][:2])
        
        # Add cuisine expansions
        for cuisine in parsed_query['cuisine']:
            if cuisine in CUISINE_TERMS:
                expansions.extend(CUISINE_TERMS[cuisine][:2])
        
        # Add price expansions
        for price in parsed_query['price']:
            if price in PRICE_TERMS:
                expansions.extend(PRICE_TERMS[price][:2])
        
        # Add activity expansions
        for activity in parsed_query['activity']:
            if activity in ACTIVITY_TERMS:
                expansions.extend(ACTIVITY_TERMS[activity][:2])
        
        # Add time expansions
        for time in parsed_query['time']:
            if time in TIME_TERMS:
                expansions.extend(TIME_TERMS[time][:2])
        
        # Create expanded query
        expanded_query = original_query
        
        # Only add expansions if we have them
        if expansions:
            # Remove duplicates while preserving order
            unique_expansions = []
            for item in expansions:
                if item not in unique_expansions and item.lower() not in original_query.lower():
                    unique_expansions.append(item)
            
            # Limit to prevent overly long queries
            if unique_expansions:
                # Add a separator and the expansions
                expanded_query += ". Similar to places that are: " + ", ".join(unique_expansions[:8])
        
        return expanded_query
    
    def search_places_with_meaningful_breakdown(self, query, limit=10, amenity_filter=True):
        """
        Enhanced version of search that provides a more meaningful breakdown
        of why certain places match a query better than others
        """
        if not self.has_pgvector:
            logger.warning("pgvector extension not available, cannot perform search")
            return []
        
        # Parse the query into categories
        parsed_query = self.parse_query(query)
        original_query = query
        
        # Get the original query embedding before expansion
        original_embedding, _ = self.generate_embedding(original_query)
        
        # Expand the query with related terms
        expanded_query = self.expand_query(parsed_query)
        logger.info(f"Expanded query: '{expanded_query}'")
        
        # Get the expanded query embedding
        expanded_embedding, _ = self.generate_embedding(expanded_query)
        
        # Extract location if present
        neighborhood = parsed_query['location']
        
        conn, cur = self._connect_db()
        try:
            # Run search with the expanded embedding
            search_params = [expanded_embedding]
            
            base_query = """
            SELECT 
                p.id, p.name, p.neighborhood, p.tags, p.price_range,
                p.combined_description, p.hours, p.amenities,
                1 - (e.embedding <=> %s::vector) as similarity
            FROM places p
            JOIN embeddings e ON p.id = e.place_id
            """
            
            # Add amenity filtering if needed
            where_clauses = []
            if amenity_filter and parsed_query['amenities']:
                for amenity in parsed_query['amenities']:
                    where_clauses.append("(p.amenities->%s)::boolean IS TRUE")
                    search_params.append(amenity)
            
            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)
            
            base_query += " ORDER BY similarity DESC LIMIT %s"
            search_params.append(limit * 2)  # Get more results initially for neighborhood filtering
            
            # Execute the query
            cur.execute(base_query, search_params)
            results = cur.fetchall()
            
            # Apply neighborhood filtering/boosting if present
            boosted_places = set()
            
            if neighborhood:
                # Track original similarities before boosting for analysis
                original_similarities = {result[0]: result[8] for result in results}
                
                # Boost places in the target neighborhood
                boosted_results = []
                other_results = []
                neighborhood_pattern = neighborhood.lower()
                
                for result in results:
                    place_id, name, result_neighborhood = result[0], result[1], result[2]
                    
                    if result_neighborhood and neighborhood_pattern in result_neighborhood.lower():
                        # Apply boost (20% increase in similarity)
                        boosted_similarity = result[8] * 1.2
                        if boosted_similarity > 1.0:
                            boosted_similarity = 1.0
                        
                        # Create new result tuple with boosted similarity
                        new_result = result[:8] + (boosted_similarity,)
                        boosted_results.append(new_result)
                        boosted_places.add(place_id)
                    else:
                        other_results.append(result)
                
                # Combine boosted and regular results
                results = boosted_results + other_results
                
                # If very few results in target neighborhood, try adjacent neighborhoods
                if len(boosted_results) < 3:
                    adjacent_neighborhoods = get_adjacent_neighborhoods(neighborhood)
                    if adjacent_neighborhoods:
                        for result in other_results:
                            place_id, name, result_neighborhood = result[0], result[1], result[2]
                            if (result_neighborhood and 
                                any(adj.lower() in result_neighborhood.lower() for adj in adjacent_neighborhoods)):
                                # Apply smaller boost (10%)
                                boosted_similarity = result[8] * 1.1
                                if boosted_similarity > 1.0:
                                    boosted_similarity = 1.0
                                
                                # Create new result tuple with boosted similarity
                                new_result = result[:8] + (boosted_similarity,)
                                boosted_results.append(new_result)
                                boosted_places.add(place_id)
                        
                        # Re-combine results
                        results = boosted_results + [r for r in other_results if r[0] not in [br[0] for br in boosted_results]]
            
            # Sort by similarity and get top results
            results.sort(key=lambda x: x[8], reverse=True)
            top_results = results[:limit]
            
            # ======= MEANINGFUL BREAKDOWN ANALYSIS =======
            logger.info("=" * 50)
            logger.info(f"MEANINGFUL BREAKDOWN FOR QUERY: '{query}'")
            logger.info("=" * 50)
            
            if neighborhood:
                logger.info(f"Location filter: {neighborhood}")
            
            # Compare expanded vs. original query
            if expanded_query != original_query:
                logger.info(f"Query was expanded from: '{original_query}'")
                logger.info(f"Expanded to: '{expanded_query}'")
            
            # For each top result, provide a meaningful breakdown
            for i, result in enumerate(top_results[:5], 1):
                place_id, name, result_neighborhood = result[0], result[1], result[2]
                tags, price_range = result[3], result[4]
                description, hours, amenities, similarity = result[5], result[6], result[7], result[8]
                
                logger.info(f"\n{i}. {name} ({result_neighborhood}) - Similarity: {similarity:.4f}")
                
                # Check if neighborhood boosting was applied
                if place_id in boosted_places:
                    original_sim = original_similarities.get(place_id, 0)
                    boost_amount = ((similarity - original_sim) / original_sim) * 100
                    logger.info(f"   ⭐ Location boost applied: +{boost_amount:.1f}% (from {original_sim:.4f} to {similarity:.4f})")
                
                # Get similarity with original query vs expanded query
                if expanded_query != original_query:
                    # Get similarity with just the original query embedding
                    cur.execute(
                        """
                        SELECT 1 - (e.embedding <=> %s::vector) as original_similarity
                        FROM embeddings e 
                        WHERE e.place_id = %s
                        """,
                        (original_embedding, place_id)
                    )
                    original_similarity = cur.fetchone()[0]
                    
                    # Calculate the impact of query expansion
                    expansion_impact = ((similarity - original_similarity) / original_similarity) * 100
                    logger.info(f"   📈 Expansion impact: {expansion_impact:+.1f}% (from {original_similarity:.4f} to {similarity:.4f})")
                
                # Extract key information from the place
                logger.info(f"   📝 Description snippet: {description[:150]}..." if description else "   No description available")
                
                # Check for matching tags
                if tags and isinstance(tags, list):
                    matching_tags = []
                    for tag in tags:
                        for term in query.lower().split():
                            if term in tag.lower():
                                matching_tags.append(tag)
                                break
                    
                    if matching_tags:
                        logger.info(f"   🏷️ Matching tags: {', '.join(matching_tags)}")
                
                # Check for matching amenities
                if amenities and isinstance(amenities, dict):
                    matching_amenities = []
                    for amenity, value in amenities.items():
                        if value and any(term in amenity.lower() for term in query.lower().split()):
                            matching_amenities.append(amenity)
                    
                    if matching_amenities:
                        logger.info(f"   ✅ Matching amenities: {', '.join(matching_amenities)}")
                
                # Show price range if relevant to query
                if price_range and any(term in query.lower() for term in ["cheap", "affordable", "expensive", "price", "cost"]):
                    logger.info(f"   💰 Price: {price_range}")
            
            logger.info("=" * 50)
            
            # Extract just what we need for the frontend
            formatted_results = []
            for result in top_results:
                place_id, name, neighborhood, tags, price, description, _, _, similarity = result
                
                # Format tags
                if tags and isinstance(tags, str):
                    if tags.startswith('{') and tags.endswith('}'):
                        tags = tags.strip('{}').split(',')
                        tags = [tag.strip('"\'') for tag in tags]
                
                formatted_results.append((
                    place_id, name, neighborhood, tags, price, 
                    description[:200] + "..." if description and len(description) > 200 else description, 
                    similarity
                ))
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in search breakdown: {str(e)}")
            logger.error(traceback.format_exc())
            conn.rollback()
            return []
        finally:
            cur.close()
            conn.close()
    
    def search_places_with_enhanced_query(self, query, limit=10, amenity_filter=True):
        """
        Search places with enhanced query parsing, expansion, and filtering
        
        Args:
            query: Original user query
            limit: Maximum number of results
            amenity_filter: Whether to apply amenity filtering
            
        Returns:
            List of matching places
        """
        if not self.has_pgvector:
            logger.warning("pgvector extension not available, cannot perform search")
            return []
        
        # Parse the query into categories
        parsed_query = self.parse_query(query)
        
        # Expand the query with related terms
        expanded_query = self.expand_query(parsed_query)
        logger.info(f"Expanded query: '{expanded_query}'")
        
        # Extract location if present
        neighborhood = parsed_query['location']
        
        conn, cur = self._connect_db()
        try:
            # Generate embedding for expanded query
            query_embedding, _ = self.generate_embedding(expanded_query)
            
            if not query_embedding:
                logger.error("Failed to generate embedding for search query")
                return []
            
            # Prepare parameters for search
            search_params = []
            
            # Start with basic similarity search
            base_query = """
            SELECT 
                p.id, p.name, p.neighborhood, p.tags, p.price_range,
                p.combined_description,
                1 - (e.embedding <=> %s::vector) as similarity
            FROM places p
            JOIN embeddings e ON p.id = e.place_id
            """
            search_params.append(query_embedding)
            
            # Add filters based on parsed query
            where_clauses = []
            
            # Handle amenity filtering
            if amenity_filter and parsed_query['amenities']:
                for amenity in parsed_query['amenities']:
                    where_clauses.append("(p.amenities->%s)::boolean IS TRUE")
                    search_params.append(amenity)
            
            # Add WHERE clause if needed
            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)
            
            # Add ordering and limit
            base_query += " ORDER BY similarity DESC LIMIT %s"
            search_params.append(limit * 2)  # Get more results initially for neighborhood filtering
            
            # Execute the query
            cur.execute(base_query, search_params)
            results = cur.fetchall()
            
            # Apply neighborhood filtering/boosting if present
            if neighborhood:
                # Boost places in the target neighborhood
                boosted_results = []
                other_results = []
                neighborhood_pattern = neighborhood.lower()
                
                for result in results:
                    place_id, name, result_neighborhood, tags, price, desc, similarity = result
                    
                    if result_neighborhood and neighborhood_pattern in result_neighborhood.lower():
                        # Apply boost (20% increase in similarity)
                        boosted_similarity = similarity * 1.2
                        if boosted_similarity > 1.0:
                            boosted_similarity = 1.0
                        boosted_results.append((place_id, name, result_neighborhood, tags, price, desc, boosted_similarity))
                    else:
                        other_results.append(result)
                
                # Combine boosted and regular results
                results = boosted_results + other_results
                
                # If very few results in target neighborhood, try adjacent neighborhoods
                if len(boosted_results) < 3:
                    adjacent_neighborhoods = get_adjacent_neighborhoods(neighborhood)
                    if adjacent_neighborhoods:
                        for result in other_results:
                            place_id, name, result_neighborhood, tags, price, desc, similarity = result
                            if result_neighborhood and any(adj.lower() in result_neighborhood.lower() for adj in adjacent_neighborhoods):
                                # Apply smaller boost (10%)
                                boosted_similarity = similarity * 1.1
                                if boosted_similarity > 1.0:
                                    boosted_similarity = 1.0
                                # Add to boosted results with adjusted similarity
                                boosted_results.append((place_id, name, result_neighborhood, tags, price, desc, boosted_similarity))
                        
                        # Re-combine results
                        results = boosted_results + [r for r in other_results if r[0] not in [br[0] for br in boosted_results]]
            
            # Sort by similarity and limit results
            results.sort(key=lambda x: x[6], reverse=True)
            results = results[:limit]
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching places: {str(e)}")
            logger.error(traceback.format_exc())
            conn.rollback()
            return []
        finally:
            cur.close()
            conn.close()
    
    def ensure_amenities_column(self):
        """Ensure the amenities column exists in the places table"""
        conn, cur = self._connect_db()
        try:
            # Check if amenities column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'places' AND column_name = 'amenities'
            """)
            
            if not cur.fetchone():
                logger.info("Adding amenities column to places table")
                cur.execute("ALTER TABLE places ADD COLUMN amenities JSONB DEFAULT '{}'::jsonb")
                conn.commit()
                logger.info("Added amenities column to places table")
            else:
                logger.info("Amenities column already exists")
                
        except Exception as e:
            logger.error(f"Error adding amenities column: {str(e)}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def extract_amenities_from_descriptions(self):
        """Extract amenities from place descriptions and populate the amenities column"""
        conn, cur = self._connect_db()
        try:
            # Amenity keywords to look for
            amenity_patterns = {
                "wifi": [r'\b(?:wi-?fi|wireless|internet)\b', r'\bwifi\b'],
                "outdoor_seating": [r'\b(?:outdoor|outside|patio|terrace|sidewalk)\s+(?:seating|dining|area)\b', r'\b(?:garden|courtyard)\b'],
                "pet_friendly": [r'\b(?:pet|dog)(?:-|\s+)friendly\b', r'\b(?:pets|dogs)\s+(?:allowed|welcome)\b'],
                "reservations": [r'\breservations?\b', r'\b(?:take|accept)s?\s+reservations?\b'],
                "takeout": [r'\b(?:take-?out|to-?go|pickup|delivery)\b', r'\bcarry-?out\b'],
                "live_music": [r'\blive\s+(?:music|band|dj|performance)\b', r'\b(?:music|band|dj)\s+performance\b'],
                "free_wifi": [r'\bfree\s+(?:wi-?fi|wireless|internet)\b', r'\bfree\s+wifi\b'],
                "full_bar": [r'\bfull\s+bar\b', r'\bcraft\s+(?:cocktails?|beers?)\b'],
                "coffee": [r'\b(?:coffee|espresso|latte)\b'],
                "wheelchair_accessible": [r'\b(?:wheelchair|handicap|ada|accessible)\b'],
                "vegan_options": [r'\bvegan\b', r'\bvegan[\-\s]+friendly\b'],
                "gluten_free": [r'\bgluten[\-\s]+free\b'],
                "vegetarian": [r'\bvegetarian\b', r'\bvegetarian[\-\s]+friendly\b'],
                "quiet": [r'\b(?:quiet|peaceful|tranquil)\b'],
                "workspace": [r'\b(?:workspace|work\s+space|working\s+space)\b', r'\b(?:laptops?|work\s+from)\b'],
                "plug_outlets": [r'\b(?:outlets?|plugs?|sockets?)\b'],
                "private_room": [r'\bprivate\s+(?:room|dining|event)\b', r'\b(?:event|party)\s+space\b'],
                "romantic": [r'\bromantic\b', r'\bdate\s+night\b', r'\bintimate\s+setting\b']
            }
            
            # Fetch places without amenities data
            cur.execute("""
                SELECT id, name, combined_description, tags 
                FROM places 
                WHERE amenities IS NULL OR amenities = '{}'::jsonb
            """)
            
            places = cur.fetchall()
            logger.info(f"Processing amenities for {len(places)} places")
            
            updated_count = 0
            for place_id, name, description, tags in places:
                # Skip if no description
                if not description:
                    continue
                
                amenities = {}
                
                # Check for amenity patterns in description
                for amenity, patterns in amenity_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, description.lower()):
                            amenities[amenity] = True
                            break
                
                # Also check tags for amenity clues
                if tags:
                    parsed_tags = self.parse_tags(tags)
                    tag_text = " ".join(parsed_tags).lower()
                    for amenity, patterns in amenity_patterns.items():
                        if amenity not in amenities:  # Only check if not already found
                            for pattern in patterns:
                                if re.search(pattern, tag_text):
                                    amenities[amenity] = True
                                    break
                
                # Update the place with amenities data if found
                if amenities:
                    cur.execute(
                        "UPDATE places SET amenities = %s::jsonb WHERE id = %s",
                        (json.dumps(amenities), place_id)
                    )
                    updated_count += 1
            
            conn.commit()
            logger.info(f"Updated amenities for {updated_count} places")
            
        except Exception as e:
            logger.error(f"Error extracting amenities: {str(e)}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def add_missing_metadata_column(self):
        """Add metadata JSONB column if it doesn't exist"""
        conn, cur = self._connect_db()
        try:
            # Check if metadata column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'places' AND column_name = 'metadata'
            """)
            
            if not cur.fetchone():
                logger.info("Adding metadata column to places table")
                cur.execute("ALTER TABLE places ADD COLUMN metadata JSONB")
                conn.commit()
                logger.info("Added metadata column to places table")
            else:
                logger.info("Metadata column already exists")
                
        except Exception as e:
            logger.error(f"Error adding metadata column: {str(e)}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def test_enhanced_search(self, query, limit=5):
        """Test the enhanced search functionality"""
        logger.info(f"Testing enhanced search with query: '{query}'")
        
        # Run search with enhanced query
        results = self.search_places_with_enhanced_query(query, limit=limit)
        
        if not results:
            logger.warning("No results found.")
            return []
            
        logger.info(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            id, name, neighborhood, tags, price, desc, similarity = result
            logger.info(f"{i}. {name} ({neighborhood}) - {similarity:.4f}")
            
        return results
    
def main():
    # Database configuration
    db_config = {
        "dbname": "corner_db",
        "user": os.getenv("DB_USER", "namayjindal"),
        "password": os.getenv("DB_PASSWORD", ""),
        "host": os.getenv("DB_HOST", "localhost")
    }
    
    generator = EmbeddingGenerator(db_config)
    
    # Add metadata column if needed
    generator.add_missing_metadata_column()
    
    # Ensure amenities column exists
    generator.ensure_amenities_column()
    
    # Extract amenities from descriptions
    generator.extract_amenities_from_descriptions()
    
    # Process all places
    tokens_used = generator.process_all_places()
    
    # Test the enhanced search with various query types
    logger.info("\nTesting enhanced search functionality...")
    
    test_queries = [
        # Vibe-focused queries
        "cozy cafe to work from",
        "romantic dinner spot",
        "casual brunch with friends",
        "aesthetic restaurant for Instagram",
        
        # Amenity-focused queries
        "cafes with wifi and outlets",
        "restaurants with outdoor seating",
        "dog friendly bars",
        "places with vegetarian options",
        
        # Price-focused queries
        "cheap eats in Chinatown",
        "affordable dinner spot",
        "high-end dining experience",
        
        # Time-focused queries
        "breakfast place open early",
        "late night food options",
        "weekend brunch spots",
        
        # Combined complex queries
        "cozy cafe with wifi in Brooklyn",
        "affordable Italian restaurant with outdoor seating",
        "quiet workspace with good coffee in Manhattan",
        "romantic date night spot with vegetarian options"
    ]
    
    for query in test_queries:
        generator.test_enhanced_search(query, limit=3)
        print("-" * 40)

if __name__ == "__main__":
    main()