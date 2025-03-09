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

    // Initialize Google Map
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
            ]
        });
        
        // Show the map container initially hidden
        mapContainer.classList.remove('hidden');
    }

    // Toggle map visibility
    if (mapToggle) {
        mapToggle.addEventListener('click', function() {
            mapContainer.classList.toggle('map-expanded');
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
                pill.className = 'inline-block bg-gray-200 hover:bg-gray-300 rounded-full px-3 py-1 text-sm text-gray-700 cursor-pointer';
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
                    
                    // Filter results if location is specified
                    let filteredPlaces = places;
                    if (locationFilter) {
                        filteredPlaces = places.filter(place => {
                            return place.neighborhood && 
                                place.neighborhood.toLowerCase().includes(locationFilter.toLowerCase());
                        });
                        
                        // If no places in the exact location, use original results but mark them
                        if (filteredPlaces.length === 0) {
                            filteredPlaces = places;
                        }
                    }
                    
                    // Display the results
                    filteredPlaces.forEach((place, index) => {
                        const card = createPlaceCard(place, locationFilter);
                        card.style.animation = `fadeIn 0.3s ease-in-out ${index * 0.05}s both`;
                        searchResults.appendChild(card);
                        
                        // Add marker to map if Google ID is available
                        if (place.google_id && map) {
                            addMarker(place);
                        }
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

    function createPlaceCard(place, locationFilter) {
        const div = document.createElement('div');
        div.className = 'place-card';
        div.dataset.id = place.id;
        
        // Check if place is in the requested location
        const isInRequestedLocation = locationFilter && place.neighborhood && 
            place.neighborhood.toLowerCase().includes(locationFilter.toLowerCase());
        
        // Format tags
        let tagsHTML = '';
        if (place.tags && Array.isArray(place.tags)) {
            tagsHTML = place.tags.slice(0, 3).map(tag => 
                `<span class="tag-pill">${tag}</span>`
            ).join('');
        }
        
        div.innerHTML = `
            <h3>${place.name}</h3>
            <div class="neighborhood">
                <i class="fas fa-map-marker-alt text-indigo-500"></i> ${place.neighborhood || 'New York'}
                ${locationFilter && !isInRequestedLocation ? 
                  '<span class="ml-2 text-amber-500 text-xs font-medium">Different location</span>' : ''}
            </div>
            <div class="flex justify-between items-center">
                <div class="price">${place.price_range || ''}</div>
                <div class="text-xs text-indigo-600 font-medium">${place.similarity}% match</div>
            </div>
            <div class="tags mt-2">${tagsHTML}</div>
            <div class="description">${place.description || 'No description available'}</div>
        `;
        
        // Add click event to show details
        div.addEventListener('click', () => {
            showPlaceDetails(place.id);
            
            // Highlight the marker on the map
            if (place.google_id && map) {
                highlightMarker(place.id);
            }
        });
        
        return div;
    }

    function addMarker(place) {
        if (!map || !place.google_id) return;
        
        // Use the Places API to get location details
        const placesService = new google.maps.places.PlacesService(map);
        placesService.getDetails({
            placeId: place.google_id,
            fields: ['geometry', 'name', 'formatted_address']
        }, (result, status) => {
            if (status === google.maps.places.PlacesServiceStatus.OK && result.geometry) {
                const marker = new google.maps.Marker({
                    position: result.geometry.location,
                    map: map,
                    title: place.name,
                    animation: google.maps.Animation.DROP,
                    placeId: place.id
                });
                
                const infoWindow = new google.maps.InfoWindow({
                    content: `
                        <div class="p-2">
                            <h3 class="font-semibold">${place.name}</h3>
                            <p class="text-sm">${result.formatted_address || place.neighborhood || ''}</p>
                            <p class="text-xs mt-1">
                                <a href="#" class="text-indigo-600" onclick="document.querySelector('[data-id=\\'${place.id}\\']').click(); return false;">
                                    View details
                                </a>
                            </p>
                        </div>
                    `
                });
                
                marker.addListener('click', () => {
                    infoWindow.open(map, marker);
                });
                
                markers.push({
                    marker: marker,
                    infoWindow: infoWindow,
                    placeId: place.id
                });
            }
        });
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
        
        // Fetch place details
        fetch(`/api/place/${placeId}`)
            .then(response => response.json())
            .then(place => {
                modalTitle.textContent = place.name;
                
                // Format hours if available
                let hoursHTML = '';
                if (place.hours) {
                    try {
                        const hours = typeof place.hours === 'string' ? JSON.parse(place.hours) : place.hours;
                        if (typeof hours === 'object') {
                            hoursHTML = '<ul class="text-sm">';
                            for (const [day, time] of Object.entries(hours)) {
                                hoursHTML += `<li><span class="font-medium">${day}:</span> ${time}</li>`;
                            }
                            hoursHTML += '</ul>';
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
                
                // Create mini map for the modal if we have Google ID
                let modalMapHTML = '';
                if (place.google_id) {
                    modalMapHTML = `
                        <div class="modal-section">
                            <h4 class="modal-section-title">Location</h4>
                            <div id="modal-map" class="h-48 rounded-lg mb-3"></div>
                            <p class="text-sm text-gray-600">${place.address || place.neighborhood || 'New York'}</p>
                        </div>
                    `;
                }
                
                modalContent.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="md:col-span-2">
                            <div class="modal-section">
                                <h4 class="modal-section-title">About</h4>
                                <p class="text-gray-700">${place.combined_description || 'No description available'}</p>
                            </div>
                            
                            ${modalMapHTML}
                            
                            <div class="modal-section">
                                <h4 class="modal-section-title">Reviews</h4>
                                ${reviewsHTML}
                            </div>
                        </div>
                        
                        <div>
                            <div class="bg-gray-50 p-4 rounded-lg">
                                <div class="modal-section">
                                    <h4 class="modal-section-title">Info</h4>
                                    <div class="text-sm">
                                        <p class="mb-2"><i class="fas fa-map-marker-alt text-indigo-500 mr-2"></i>${place.neighborhood || 'New York'}</p>
                                        ${place.price_range ? `<p class="mb-2"><i class="fas fa-dollar-sign text-indigo-500 mr-2"></i>${place.price_range}</p>` : ''}
                                        ${place.address ? `<p class="mb-2"><i class="fas fa-location-dot text-indigo-500 mr-2"></i>${place.address}</p>` : ''}
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
                `;
                
                // Initialize mini map in modal if Google ID exists
                if (place.google_id) {
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