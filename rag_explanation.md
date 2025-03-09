# Corner NYC - Search Enhancement Overview

## Approach: Category-Based Query Processing

After analyzing hundreds of recent user queries from our search logs, we identified clear patterns in how users search for places. This led us to implement a "bucketing" approach that categorizes search terms and enhances results through query expansion and intelligent filtering.

## Why We Chose This Approach

### Data-Driven Decision Making

Analysis of our search logs revealed that users primarily search using combinations of these categories:

1. **Vibe/Atmosphere** (most frequent): "cozy", "chill", "aesthetic"
2. **Location**: "Brooklyn", "East Village", "Chelsea"
3. **Establishment Type**: "cafe", "bar", "restaurant"
4. **Cuisine**: "thai", "italian", "chinese"
5. **Price**: "cheap", "affordable", "expensive"
6. **Activity Purpose**: "to work from", "date night", "to read"
7. **Time-Related**: "breakfast", "open late", "brunch"
8. **Amenities**: "wifi", "outdoor seating", "dog friendly"

### Limitations of Pure Vector Search

While vector search is powerful for semantic understanding, it has limitations:

- **Location Bias**: Including location in embeddings can overwhelm other search aspects
- **Exact Feature Matching**: Hard to capture binary attributes like "has wifi" or "dog friendly"
- **Vocabulary Limitations**: Users might search for "cozy" when a description uses "warm" or "snug"

## How It Works

### 1. Query Categorization

When a user searches, we break down their query into specific buckets:

```
"cozy cafe with wifi in Brooklyn for working"
↓
{
  "vibe": ["cozy"],
  "establishment": ["cafe"],
  "amenities": ["wifi"],
  "location": "Brooklyn",
  "activity": ["work"]
}
```

### 2. Query Expansion

We expand each category with related terms to improve matching:

- "cozy" → adds "warm", "intimate", "homey"
- "cafe" → adds "coffee shop", "espresso bar"
- "work" → adds "workspace", "productive", "laptop friendly"

### 3. Location Handling

We handle location separately from the semantic search:
- Extract and remove location terms from vector matching
- Apply a 10% relevance boost to places in the target neighborhood
- Apply a 5% boost to places in adjacent neighborhoods
- Enable filtering by specific neighborhoods

### 4. Amenity Filtering

For binary attributes like "wifi" or "outdoor seating":
- Store these as structured JSONB data
- Apply precise filtering for these attributes
- Extract amenities automatically from descriptions and tags

### 5. Enhanced Google Maps Integration

For improved location awareness:
- Match Corner place IDs with Google Place IDs
- Display places on an interactive map
- Enable users to explore nearby locations visually
- Provide real-time geocoding of search results

### 6. Combined Ranking

Results are ranked using a combination of:
- Semantic similarity to the expanded query
- Location-based boosting
- Amenity filtering
- Neighborhood matching precision

## Implementation Details

### Vector Search Implementation

We use OpenAI's text-embedding-ada-002 model to generate embeddings for:
- Place descriptions, names, and relevant attributes
- User queries (after removing location terms)

These embeddings are stored in PostgreSQL using the pgvector extension, enabling efficient vector similarity search.

### Query Preprocessing

1. Extract and separate location terms
2. Categorize remaining terms by type (vibe, cuisine, etc.)
3. Expand query with related terms
4. Generate embedding for the expanded query

### Search Process

1. Perform vector similarity search with the expanded query
2. Apply location-based boosting to relevant results
3. Filter by exact amenities if specified
4. Combine scores for final ranking
5. Return results with helpful metadata

## Results

This enhanced approach delivers several benefits:

1. **More Relevant Results**: Better understanding of what users are looking for
2. **Consistent Handling of Features**: Reliable filtering for amenities
3. **Neighborhood Intelligence**: Results that respect location without being dominated by it
4. **Broader Matching**: Finding places even when they use different vocabulary
5. **Improved Filtering**: More precise filtering for binary attributes
6. **Visual Context**: Map integration provides spatial awareness
7. **Better User Experience**: More intuitive and responsive interface

By analyzing how our users actually search and implementing this categorized approach, we've created a search experience that better understands and responds to the nuanced ways people look for places in New York City.

## Future Directions

While the current implementation significantly improves search quality, several opportunities exist for further enhancement:

1. **Dynamic Query Expansion**: Adjust expansion based on query context
2. **Personalized Ranking**: Factor in user preferences and history
3. **Temporal Awareness**: Better handling of time-based queries
4. **Enhanced Coordinate-Based Ranking**: Incorporate actual distances
5. **Hybrid Neural Search**: Combine embeddings with traditional search techniques

These improvements will continue to refine our understanding of user intent and deliver increasingly relevant results.