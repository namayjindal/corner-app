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
    
    function addDebugToggle() {
        // Target a more specific location for the toggle
        const popularSearchesSection = document.getElementById('popular-searches').parentElement;
        
        const debugToggle = document.createElement('div');
        debugToggle.className = 'mt-3 text-center';
        debugToggle.innerHTML = `
            <label class="inline-flex items-center cursor-pointer">
                <input type="checkbox" id="debug-toggle" class="form-checkbox h-4 w-4 text-indigo-600">
                <span class="ml-2 text-sm text-gray-500">Show search debug info</span>
            </label>
        `;
        
        // Insert the toggle right before the popular searches section
        popularSearchesSection.insertBefore(debugToggle, document.getElementById('popular-searches'));
    }

    addDebugToggle();

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

    function performSearch(query) {
    // Show loading state
        searchResults.innerHTML = getLoadingHTML();
        resultsContainer.classList.remove('hidden');
        searchTerm.textContent = query;
        noResults.classList.add('hidden');

        // Check if debug mode is enabled
        const debugMode = document.getElementById('debug-toggle')?.checked || false;
        
        // Perform search
        fetch(`/api/search?q=${encodeURIComponent(query)}${debugMode ? '&debug=true' : ''}`)
            .then(response => response.json())
            .then(data => {
                // Clear loading state
                searchResults.innerHTML = '';
                
                if (data.results && data.results.length > 0) {
                    // Show debug panel if debug info exists
                    if (data.debug_info) {
                        const debugPanel = document.createElement('div');
                        debugPanel.className = 'col-span-2 bg-gray-50 p-4 rounded-lg mb-6 overflow-auto';
                        debugPanel.style.maxHeight = '400px';
                        debugPanel.innerHTML = `
                            <h3 class="text-lg font-medium mb-2 lowercase">Search Debug Information</h3>
                            <pre class="text-xs whitespace-pre-wrap">${JSON.stringify(data.debug_info, null, 2)}</pre>
                        `;
                        searchResults.appendChild(debugPanel);
                    }
                    
                    data.results.forEach((place, index) => {
                        const card = createPlaceCard(place, data.debug_info ? data.debug_info[index] : null);
                        // Add fade-in animation with delay based on index
                        card.style.animation = `fadeIn 0.3s ease-in-out ${index * 0.05}s both`;
                        searchResults.appendChild(card);
                    });
                } else {
                    noResults.classList.remove('hidden');
                }
            })
            .catch(error => {
                console.error('Error performing search:', error);
                searchResults.innerHTML = `<div class="col-span-2 text-center py-4 text-red-500">
                    <p>an error occurred while searching. please try again.</p>
                </div>`;
            });
    }

    function createPlaceCard(place, debugInfo) {
        const div = document.createElement('div');
        div.className = 'place-card';
        div.dataset.id = place.id;
        
        // Format price range
        let priceHTML = '';
        if (place.price_range) {
            priceHTML = `<div class="price-indicator">${place.price_range}</div>`;
        }
        
        // Format tags
        let tagsHTML = '';
        if (place.tags && Array.isArray(place.tags)) {
            tagsHTML = place.tags.slice(0, 3).map(tag => 
                `<span class="tag-pill">${tag}</span>`
            ).join('');
        }
        
        // Format similarity (cap at 100%)
        let similarity = Math.min(place.similarity, 100).toFixed(1);
        
        let cardHTML = `
            <div class="flex justify-between items-start mb-2">
                <h3 class="text-lg font-medium text-gray-800">${place.name.toLowerCase()}</h3>
                <div class="similarity-badge">${similarity}% match</div>
            </div>
            <div class="text-sm text-gray-500 mb-3">
                <i class="fas fa-map-marker-alt location-icon"></i>${(place.neighborhood || 'new york').toLowerCase()}
            </div>
            <div class="flex justify-between items-center mb-3">
                ${priceHTML}
            </div>
            ${tagsHTML ? `<div class="mb-3">${tagsHTML}</div>` : ''}
            <div class="description-text">${place.description || 'no description available'}</div>
        `;
        
        // Add debug info if available
        if (debugInfo) {
            cardHTML += `
                <div class="mt-4 pt-3 border-t border-gray-200">
                    <div class="text-xs font-medium text-gray-700 mb-2">similarity factors:</div>
                    <div class="text-xs text-gray-600 space-y-1">
            `;
            
            // Add name match
            if (debugInfo.factors.name_match) {
                cardHTML += `
                    <div>
                        <span class="font-medium">name match:</span> 
                        ${debugInfo.factors.name_match.score}%
                        ${debugInfo.factors.name_match.matching_terms.length > 0 ? 
                          `(${debugInfo.factors.name_match.matching_terms.join(', ')})` : ''}
                    </div>
                `;
            }
            
            // Add tag match
            if (debugInfo.factors.tag_match) {
                cardHTML += `
                    <div>
                        <span class="font-medium">tag match:</span> 
                        ${debugInfo.factors.tag_match.score}%
                        ${debugInfo.factors.tag_match.matching_terms.length > 0 ? 
                          `(${debugInfo.factors.tag_match.matching_terms.join(', ')})` : ''}
                    </div>
                `;
            }
            
            // Add location match if present
            if (debugInfo.factors.location_match) {
                cardHTML += `
                    <div>
                        <span class="font-medium">location match:</span> 
                        ${debugInfo.factors.location_match.is_match ? 'Yes' : 'No'}
                    </div>
                `;
            }
            
            // Close debug section
            cardHTML += `
                    </div>
                </div>
            `;
        }
        
        div.innerHTML = cardHTML;
        
        // Add click event to show details
        div.addEventListener('click', () => {
            showPlaceDetails(place.id);
        });
        
        return div;
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
                
                modalContent.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="md:col-span-2">
                            <div class="modal-section">
                                <h4 class="modal-section-title">About</h4>
                                <p class="text-gray-700">${place.combined_description || 'No description available'}</p>
                            </div>
                            
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
});