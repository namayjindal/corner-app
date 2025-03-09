// Add this to the top of your app.js file or replace the existing DOMContentLoaded block
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const searchSuggestions = document.getElementById('search-suggestions');
    const resultsContainer = document.getElementById('results-container');
    const searchResults = document.getElementById('search-results');
    const searchTerm = document.getElementById('search-term');
    const noResults = document.getElementById('no-results');
    const popularSearches = document.getElementById('popular-searches');
    const placeModal = document.getElementById('place-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalContent = document.getElementById('modal-content');
    const closeModal = document.getElementById('close-modal');
    const mapContainer = document.getElementById('map-container');
    const mapToggle = document.getElementById('map-toggle');
    let map;
    let markers = [];
    let currentLocation = null;
    let locationFilter = null;

    // Enhanced map initialization
function initMap() {
    if (!mapContainer) return;
    
    // Default to NYC coordinates
    const defaultLocation = { lat: 40.7128, lng: -74.0060 };
    
    map = new google.maps.Map(document.getElementById('map'), {
        center: defaultLocation,
        zoom: 12,
        styles: [
            {
                "featureType": "poi",
                "stylers": [
                    { "visibility": "off" }
                ]
            }
        ],
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        zoomControlOptions: {
            position: google.maps.ControlPosition.RIGHT_TOP
        }
    });
    
    // Add class to body when map is visible
    document.body.classList.add('map-visible');
    
    // Show the map container
    mapContainer.classList.remove('hidden');
    
    // Try to get user's location if they allow it
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                
                // Check if user is in NYC area (roughly)
                const nycBounds = {
                    north: 40.92,
                    south: 40.48,
                    east: -73.70,
                    west: -74.26
                };
                
                if (userLocation.lat >= nycBounds.south && 
                    userLocation.lat <= nycBounds.north && 
                    userLocation.lng >= nycBounds.west && 
                    userLocation.lng <= nycBounds.east) {
                    
                    map.setCenter(userLocation);
                    map.setZoom(14);
                    
                    // Add a marker for user's location
                    new google.maps.Marker({
                        position: userLocation,
                        map: map,
                        title: "Your Location",
                        icon: {
                            path: google.maps.SymbolPath.CIRCLE,
                            scale: 10,
                            fillColor: "#4285F4",
                            fillOpacity: 0.6,
                            strokeColor: "#ffffff",
                            strokeWeight: 2
                        }
                    });
                }
            },
            () => {
                // User denied geolocation or it failed
                console.log("Geolocation permission denied or failed");
            }
        );
    }
    
    // Create a search box within the map
    const mapSearchInput = document.createElement('input');
    mapSearchInput.id = 'map-search-input';
    mapSearchInput.type = 'text';
    mapSearchInput.placeholder = 'Search locations';
    mapSearchInput.className = 'map-search-control';
    
    const mapSearchBox = new google.maps.places.SearchBox(mapSearchInput);
    map.controls[google.maps.ControlPosition.TOP_LEFT].push(mapSearchInput);
    
    // Bias the SearchBox results towards current map's viewport
    map.addListener('bounds_changed', () => {
        mapSearchBox.setBounds(map.getBounds());
    });
    
    // Listen for the event fired when the user selects a prediction
    mapSearchBox.addListener('places_changed', () => {
        const places = mapSearchBox.getPlaces();
        
        if (places.length === 0) {
            return;
        }
        
        // For each place, get the location
        const bounds = new google.maps.LatLngBounds();
        places.forEach(place => {
            if (!place.geometry || !place.geometry.location) {
                console.log("Returned place contains no geometry");
                return;
            }
            
            if (place.geometry.viewport) {
                // Only geocodes have viewport
                bounds.union(place.geometry.viewport);
            } else {
                bounds.extend(place.geometry.location);
            }
        });
        
        map.fitBounds(bounds);
    });
}

    // Toggle map visibility
    if (mapToggle) {
        mapToggle.addEventListener('click', function() {
            mapContainer.classList.toggle('map-expanded');
            document.body.classList.toggle('map-expanded-body');
            
            if (mapContainer.classList.contains('map-expanded')) {
                mapToggle.innerHTML = '<i class="fas fa-compress-alt"></i>';
                if (map) {
                    google.maps.event.trigger(map, 'resize');
                    if (markers.length > 0) {
                        fitMapToMarkers();
                    }
                }
            } else {
                mapToggle.innerHTML = '<i class="fas fa-expand-alt"></i>';
            }
        });
    }

    // Load popular searches
    fetch('/api/recent_queries')
        .then(response => response.json())
        .then(data => {
            const queries = data.queries || [];
            popularSearches.innerHTML = '<span class="font-medium">Popular searches:</span>';
            
            queries.slice(0, 6).forEach(query => {
                const pill = document.createElement('span');
                pill.className = 'inline-block bg-gray-200 hover:bg-gray-300 rounded-full px-3 py-1 text-sm text-gray-700 cursor-pointer mr-2';
                pill.textContent = query;
                pill.addEventListener('click', () => {
                    searchInput.value = query;
                    performSearch(query);
                });
                popularSearches.appendChild(pill);
            });
        })
        .catch(error => console.error('Error loading popular searches:', error));

    // Search functionality
    searchButton.addEventListener('click', () => {
        const query = searchInput.value.trim();
        if (query) {
            performSearch(query);
        }
    });

    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            const query = searchInput.value.trim();
            if (query) {
                performSearch(query);
            }
        }
    });

    // Close modal when clicking the close button
    closeModal.addEventListener('click', () => {
        placeModal.classList.add('hidden');
        document.body.style.overflow = 'auto';
    });

    // Close modal when clicking outside the modal content
    placeModal.addEventListener('click', (e) => {
        if (e.target === placeModal) {
            placeModal.classList.add('hidden');
            document.body.style.overflow = 'auto';
        }
    });

    // Extract location from query
    function extractLocationFromQuery(query) {
        // Define location patterns
        const locationPatterns = [
            /in\s+([a-zA-Z\s\']+)(?:\s|$|\.)/i,
            /near\s+([a-zA-Z\s\']+)(?:\s|$|\.)/i,
            /around\s+([a-zA-Z\s\']+)(?:\s|$|\.)/i,
        ];
        
        // Check each pattern
        for (const pattern of locationPatterns) {
            const match = query.match(pattern);
            if (match && match[1]) {
                return match[1].trim();
            }
        }
        
        // Additional check for common NYC neighborhoods
        const neighborhoods = [
            "Brooklyn", "Manhattan", "Queens", "Bronx", "Staten Island",
            "SoHo", "Tribeca", "Williamsburg", "East Village", "West Village",
            "Upper East Side", "Upper West Side", "Chelsea", "Harlem", "Midtown",
            "Lower East Side", "Greenpoint", "Bushwick", "Astoria", "Chinatown"
        ];
        
        for (const hood of neighborhoods) {
            if (query.toLowerCase().includes(hood.toLowerCase())) {
                return hood;
            }
        }
        
        return null;
    }

    function performSearch(query) {
        // Show loading state
        searchResults.innerHTML = getLoadingHTML();
        resultsContainer.classList.remove('hidden');
        searchTerm.textContent = query;
        noResults.classList.add('hidden');
        
        // Extract location from query
        locationFilter = extractLocationFromQuery(query);
        if (locationFilter) {
            document.getElementById('location-filter').textContent = locationFilter;
            document.getElementById('location-filter-container').classList.remove('hidden');
        } else {
            document.getElementById('location-filter-container').classList.add('hidden');
        }

        // Perform search
        fetch(`/api/search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                // Clear loading state
                searchResults.innerHTML = '';
                
                // Clear existing markers
                clearMarkers();
                
                if (data.results && data.results.length > 0) {
                    const places = data.results;
                    
                    // Display the results
                    places.forEach((place, index) => {
                        const card = createPlaceCard(place);
                        card.style.animation = `fadeIn 0.3s ease-in-out ${index * 0.05}s both`;
                        searchResults.appendChild(card);
                        
                        // Add marker to map
                        addMarker(place);
                    });
                    
                    // Center map on results
                    if (markers.length > 0 && map) {
                        fitMapToMarkers();
                    }
                } else {
                    noResults.classList.remove('hidden');
                }
            })
            .catch(error => {
                console.error('Error performing search:', error);
                searchResults.innerHTML = `<div class="col-span-2 text-center py-4 text-red-500">
                    <p>An error occurred while searching. Please try again.</p>
                </div>`;
            });
    }

    // Replace the createPlaceCard function with this updated version
function createPlaceCard(place) {
    const div = document.createElement('div');
    div.className = 'place-card';
    div.dataset.id = place.id;
    
    // Format tags
    let tagsHTML = '';
    if (place.tags && Array.isArray(place.tags)) {
        tagsHTML = place.tags.slice(0, 3).map(tag => 
            `<span class="tag-pill">${tag}</span>`
        ).join('');
    } else if (place.tags && typeof place.tags === 'string') {
        try {
            const parsedTags = JSON.parse(place.tags.replace(/'/g, '"'));
            if (Array.isArray(parsedTags)) {
                tagsHTML = parsedTags.slice(0, 3).map(tag => 
                    `<span class="tag-pill">${tag}</span>`
                ).join('');
            }
        } catch (e) {
            tagsHTML = `<span class="tag-pill">${place.tags}</span>`;
        }
    }
    
    // Format location badge
    let locationBadge = '';
    if (locationFilter && place.neighborhood) {
        let badgeClass = 'bg-gray-100 text-gray-700';
        let status = 'Different area';
        
        if (place.neighborhood.toLowerCase().includes(locationFilter.toLowerCase())) {
            badgeClass = 'bg-green-100 text-green-700';
            status = 'In area';
        }
        
        locationBadge = `<span class="ml-2 px-2 py-1 text-xs rounded-full ${badgeClass}">${status}</span>`;
    }
    
    // Fix similarity percentage display
    let similarityDisplay = '';
    if (place.similarity !== undefined) {
        // Ensure value is between 0 and 1 for display
        let similarityValue = place.similarity;
        
        // If similarity is already scaled to 100, convert back to 0-1 scale
        if (similarityValue > 1) {
            similarityValue = similarityValue / 100;
        }
        
        // Format to percentage with 1 decimal place
        const percentage = Math.round(similarityValue * 1000) / 10;
        similarityDisplay = `<div class="text-xs text-indigo-600 font-medium">${percentage}% match</div>`;
    }
    
    div.innerHTML = `
        <h3>${place.name}</h3>
        <div class="neighborhood">
            <i class="fas fa-map-marker-alt text-indigo-500"></i> ${place.neighborhood || 'New York'} ${locationBadge}
        </div>
        <div class="flex justify-between items-center">
            <div class="price">${place.price_range || ''}</div>
            ${similarityDisplay}
        </div>
        <div class="tags mt-2">${tagsHTML}</div>
        <div class="description">${place.description || 'No description available'}</div>
    `;
    
    // Add click event to show details
    div.addEventListener('click', () => {
        showPlaceDetails(place.id);
    });
    
    return div;
}

    // Replace the current addMarker and related functions with these improved versions:

function addMarker(place) {
    if (!map || !place.id) return;
    
    // First priority: Use Google Places API with place.google_id
    if (place.google_id) {
        const placesService = new google.maps.places.PlacesService(map);
        placesService.getDetails({
            placeId: place.google_id,
            fields: ['geometry', 'name', 'formatted_address', 'place_id']
        }, (result, status) => {
            if (status === google.maps.places.PlacesServiceStatus.OK && result.geometry) {
                // We got exact coordinates from Google Places
                createMarker(place, result.geometry.location, result.formatted_address);
                return;
            }
            
            // If Google Places API failed, try other methods
            tryAlternateGeocoding(place);
        });
    } else {
        // No Google ID, try alternate geocoding methods
        tryAlternateGeocoding(place);
    }
}

function tryAlternateGeocoding(place) {
    // Second priority: Use the address if available
    if (place.address) {
        const geocoder = new google.maps.Geocoder();
        geocoder.geocode({
            'address': place.address + ', New York, NY'
        }, (results, status) => {
            if (status === google.maps.GeocoderStatus.OK && results[0]) {
                createMarker(place, results[0].geometry.location, place.address);
                return;
            }
            
            // If address geocoding failed, fall back to neighborhood
            geocodeNeighborhood(place);
        });
    } else {
        // No address, fall back to neighborhood
        geocodeNeighborhood(place);
    }
}

function geocodeNeighborhood(place) {
    if (!place.neighborhood) {
        console.warn(`No location data available for place ${place.id}`);
        return;
    }
    
    // Get more specific by adding NYC context
    const geocoder = new google.maps.Geocoder();
    
    // Try different formats to improve accuracy
    const geocodeOptions = [
        `${place.name}, ${place.neighborhood}, New York, NY`,
        `${place.neighborhood}, New York, NY`
    ];
    
    // Try first option
    geocoder.geocode({
        'address': geocodeOptions[0]
    }, (results, status) => {
        if (status === google.maps.GeocoderStatus.OK && results[0]) {
            createMarker(place, results[0].geometry.location, place.neighborhood);
        } else {
            // Try second option
            geocoder.geocode({
                'address': geocodeOptions[1]
            }, (results, status) => {
                if (status === google.maps.GeocoderStatus.OK && results[0]) {
                    createMarker(place, results[0].geometry.location, place.neighborhood);
                } else {
                    console.warn(`Geocoding failed for ${place.name} in ${place.neighborhood}`);
                }
            });
        }
    });
}

function createMarker(place, position, address) {
    const marker = new google.maps.Marker({
        position: position,
        map: map,
        title: place.name,
        animation: google.maps.Animation.DROP
    });
    
    const infoWindow = new google.maps.InfoWindow({
        content: `
            <div class="p-2">
                <h3 class="font-semibold">${place.name}</h3>
                <p class="text-sm">${address || place.neighborhood || 'New York'}</p>
                <p class="text-xs mt-1">
                    <a href="#" class="text-indigo-600" onclick="viewPlaceDetails(${place.id}); return false;">
                        View details
                    </a>
                </p>
            </div>
        `
    });
    
    marker.addListener('click', () => {
        // Close all other info windows first
        markers.forEach(m => m.infoWindow.close());
        
        // Open this info window
        infoWindow.open(map, marker);
    });
    
    markers.push({
        marker: marker,
        infoWindow: infoWindow,
        placeId: place.id
    });
    
    // Update map view after adding markers
    if (markers.length === 1) {
        // First marker, center on it
        map.setCenter(position);
        map.setZoom(15);
    } else if (markers.length > 1) {
        // Multiple markers, fit bounds
        fitMapToMarkers();
    }
}

    function highlightMarker(placeId) {
        if (!map) return;
        
        // Reset all markers first
        markers.forEach(m => {
            m.marker.setAnimation(null);
            m.infoWindow.close();
        });
        
        // Find and highlight the selected marker
        const marker = markers.find(m => m.placeId == placeId);
        if (marker) {
            map.panTo(marker.marker.getPosition());
            marker.marker.setAnimation(google.maps.Animation.BOUNCE);
            setTimeout(() => {
                marker.marker.setAnimation(null);
                marker.infoWindow.open(map, marker.marker);
            }, 1500);
        }
    }

    function clearMarkers() {
        markers.forEach(m => {
            m.marker.setMap(null);
        });
        markers = [];
    }

    function fitMapToMarkers() {
        if (!map || markers.length === 0) return;
        
        const bounds = new google.maps.LatLngBounds();
        markers.forEach(m => {
            bounds.extend(m.marker.getPosition());
        });
        
        map.fitBounds(bounds);
        
        // If we have just one marker, zoom out a bit
        if (markers.length === 1) {
            setTimeout(() => {
                map.setZoom(15);
            }, 100);
        }
    }

    function showPlaceDetails(placeId) {
        // Show loading state
        modalTitle.textContent = 'Loading...';
        modalContent.innerHTML = getLoadingHTML();
        placeModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
        
        // Highlight the corresponding marker
        highlightMarker(placeId);
        
        // Fetch place details
        fetch(`/api/place/${placeId}`)
            .then(response => response.json())
            .then(place => {
                modalTitle.textContent = place.name;
                
                // Format hours if available
                let hoursHTML = '';
                if (place.hours) {
                    try {
                        const hours = typeof place.hours === 'string' ? JSON.parse(place.hours.replace(/'/g, '"')) : place.hours;
                        if (typeof hours === 'object') {
                            hoursHTML = '<div class="grid grid-cols-2 gap-2 text-sm">';
                            for (const [day, time] of Object.entries(hours)) {
                                hoursHTML += `<div class="font-medium">${day}</div><div>${time}</div>`;
                            }
                            hoursHTML += '</div>';
                        } else {
                            hoursHTML = `<p class="text-sm">${hours}</p>`;
                        }
                    } catch (e) {
                        hoursHTML = `<p class="text-sm">${place.hours}</p>`;
                    }
                }
                
                // Format tags
                let tagsHTML = '';
                if (place.tags && Array.isArray(place.tags)) {
                    tagsHTML = place.tags.map(tag => 
                        `<span class="tag-pill">${tag}</span>`
                    ).join('');
                }
                
                // Format reviews
                let reviewsHTML = '';
                if (place.reviews && place.reviews.length > 0) {
                    reviewsHTML = place.reviews.map(review => `
                        <div class="review-card">
                            <div class="review-source">${review.source}</div>
                            <p class="text-sm text-gray-700">${review.review_text}</p>
                        </div>
                    `).join('');
                } else {
                    reviewsHTML = '<p class="text-gray-500">No reviews available</p>';
                }
                
                // Create photo gallery section
                let photoGalleryHTML = '';
                if (place.google_id) {
                    photoGalleryHTML = `
                        <div class="modal-section">
                            <h4 class="modal-section-title">Photos</h4>
                            <div id="place-photos" class="grid grid-cols-3 gap-2 h-48 overflow-hidden rounded-lg mb-3">
                                <div class="skeleton-loader bg-gray-200 col-span-2 row-span-2 rounded-lg animate-pulse"></div>
                                <div class="skeleton-loader bg-gray-200 rounded-lg animate-pulse"></div>
                                <div class="skeleton-loader bg-gray-200 rounded-lg animate-pulse"></div>
                            </div>
                        </div>
                    `;
                }
                
                modalContent.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="md:col-span-2">
                            ${photoGalleryHTML}
                            
                            <div class="modal-section">
                                <h4 class="modal-section-title">About</h4>
                                <p class="text-gray-700">${place.combined_description || 'No description available'}</p>
                            </div>
                            
                            <div class="modal-section">
                                <h4 class="modal-section-title">Location</h4>
                                <div id="modal-map" class="h-48 rounded-lg mb-3"></div>
                                <p class="text-sm text-gray-600 flex items-center">
                                    <i class="fas fa-map-marker-alt text-indigo-500 mr-2"></i>
                                    ${place.address || place.neighborhood || 'New York'}
                                </p>
                            </div>
                            
                            <div class="modal-section">
                                <h4 class="modal-section-title">Reviews</h4>
                                ${reviewsHTML}
                            </div>
                        </div>
                        
                        <div>
                            <div class="sticky top-4">
                                <div class="bg-gray-50 p-4 rounded-lg">
                                    <div class="modal-section">
                                        <h4 class="modal-section-title">Info</h4>
                                        <div class="text-sm">
                                            <p class="mb-2"><i class="fas fa-map-marker-alt text-indigo-500 mr-2"></i>${place.neighborhood || 'New York'}</p>
                                            ${place.price_range ? `<p class="mb-2"><i class="fas fa-dollar-sign text-indigo-500 mr-2"></i>${place.price_range}</p>` : ''}
                                        </div>
                                    </div>
                                    
                                    ${place.website ? `
                                    <div class="modal-section">
                                        <h4 class="modal-section-title">Links</h4>
                                        <div class="text-sm">
                                            <p class="mb-2">
                                                <i class="fas fa-globe text-indigo-500 mr-2"></i>
                                                <a href="${place.website}" target="_blank" class="text-indigo-600 hover:underline">Website</a>
                                            </p>
                                            ${place.instagram_handle ? `
                                            <p>
                                                <i class="fab fa-instagram text-indigo-500 mr-2"></i>
                                                <a href="https://instagram.com/${place.instagram_handle}" target="_blank" class="text-indigo-600 hover:underline">@${place.instagram_handle}</a>
                                            </p>
                                            ` : ''}
                                        </div>
                                    </div>
                                    ` : ''}
                                    
                                    ${hoursHTML ? `
                                    <div class="modal-section">
                                        <h4 class="modal-section-title">Hours</h4>
                                        ${hoursHTML}
                                    </div>
                                    ` : ''}
                                    
                                    ${tagsHTML ? `
                                    <div class="modal-section">
                                        <h4 class="modal-section-title">Tags</h4>
                                        <div class="flex flex-wrap">${tagsHTML}</div>
                                    </div>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Initialize mini map in modal if Google ID exists
                if (place.google_id) {
                    // Initialize map
                    initializeModalMap(place);
                    
                    // Load place photos
                    loadPlacePhotos(place.google_id);
                }
            })
            .catch(error => {
                console.error('Error fetching place details:', error);
                modalContent.innerHTML = `
                    <div class="text-center py-4 text-red-500">
                        <p>An error occurred while fetching place details. Please try again.</p>
                    </div>
                `;
            });
    }

    // Helper function to initialize the modal map
    function initializeModalMap(place) {
        setTimeout(() => {
            const modalMap = new google.maps.Map(document.getElementById('modal-map'), {
                zoom: 15,
                center: { lat: 40.7128, lng: -74.0060 }, // Default NYC coordinates
                mapTypeControl: false,
                streetViewControl: false,
                fullscreenControl: false
            });
            
            const placesService = new google.maps.places.PlacesService(modalMap);
            placesService.getDetails({
                placeId: place.google_id,
                fields: ['geometry', 'name', 'formatted_address']
            }, (result, status) => {
                if (status === google.maps.places.PlacesServiceStatus.OK && result.geometry) {
                    modalMap.setCenter(result.geometry.location);
                    
                    new google.maps.Marker({
                        map: modalMap,
                        position: result.geometry.location,
                        title: place.name
                    });
                }
            });
        }, 300);
    }

    // Helper function to load place photos
    function loadPlacePhotos(googlePlaceId) {
        const placesService = new google.maps.places.PlacesService(document.createElement('div'));
        
        placesService.getDetails({
            placeId: googlePlaceId,
            fields: ['photos']
        }, (place, status) => {
            if (status === google.maps.places.PlacesServiceStatus.OK && place.photos && place.photos.length > 0) {
                const photosContainer = document.getElementById('place-photos');
                photosContainer.innerHTML = '';
                
                // Get up to 5 photos
                const photos = place.photos.slice(0, 5);
                
                // Create photo grid
                photos.forEach((photo, index) => {
                    const img = document.createElement('img');
                    img.src = photo.getUrl({ maxWidth: 500, maxHeight: 500 });
                    img.alt = 'Place photo';
                    img.className = 'w-full h-full object-cover rounded-lg';
                    
                    // Make the first photo larger
                    if (index === 0) {
                        img.className += ' col-span-2 row-span-2';
                    }
                    
                    photosContainer.appendChild(img);
                });
            } else {
                // If no photos, hide the photos section
                const photosSection = document.getElementById('place-photos').closest('.modal-section');
                if (photosSection) {
                    photosSection.classList.add('hidden');
                }
            }
        });
    }

    function getLoadingHTML() {
        return `
            <div class="flex justify-center items-center py-12">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
            </div>
        `;
    }
    
    // Initialize the map if Google Maps API is loaded
    if (typeof google !== 'undefined' && google.maps) {
        initMap();
    } else {
        // If Google Maps API isn't loaded yet, wait for the load event
        window.initMap = initMap;
    }
});