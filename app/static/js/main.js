document.addEventListener('DOMContentLoaded', function() {
    console.log('News Scraper App loaded');
    
    // Check if we're on the home page and need to load data
    const newsTableBody = document.getElementById('news-table-body');
    const userProfileCard = document.getElementById('facebook-user-profile');
    
    // Only try to fetch data if elements exist (for homepage)
    if (newsTableBody) {
        loadNewsData();
    }
    
    if (userProfileCard) {
        loadFacebookData();
    }
    
    function loadNewsData() {
        fetch('/api/news')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Loaded news data:', data);
                
                if (newsTableBody && Array.isArray(data)) {
                    newsTableBody.innerHTML = ''; // Clear existing content
                    
                    // Show all articles on homepage
                    data.forEach(article => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td><strong>${escapeHtml(article.title || 'No title')}</strong></td>
                            <td>${escapeHtml((article.summary || '').substring(0, 100))}${article.summary && article.summary.length > 100 ? '...' : ''}</td>
                            <td>
                                <span class="source-badge source-${(article.source || '').toLowerCase()}">${escapeHtml(article.source || 'Unknown')}</span>
                            </td>
                            <td>${article.link && article.link !== '#' ? 
                                `<a href="${escapeHtml(article.link)}" target="_blank" class="btn btn-small">Read more</a>` : 
                                '<span class="btn btn-small disabled">No link</span>'
                            }</td>
                            <td>${article.timestamp ? new Date(article.timestamp).toLocaleString() : 'N/A'}</td>
                        `;
                        newsTableBody.appendChild(row);
                    });
                    
                    if (data.length === 0) {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td colspan="5" style="text-align: center; padding: 20px; color: #666;">
                                No articles found. The scrapers should start collecting data automatically.
                            </td>
                        `;
                        newsTableBody.appendChild(row);
                    }
                } else {
                    console.error('Invalid data format:', data);
                }
            })
            .catch(error => {
                console.error('Error fetching news:', error);
                if (newsTableBody) {
                    newsTableBody.innerHTML = `
                        <tr>
                            <td colspan="5" style="text-align: center; padding: 20px; color: #d32f2f;">
                                Error loading news data: ${error.message}
                            </td>
                        </tr>
                    `;
                }
            });
    }
    
    function loadFacebookData() {
        fetch('/api/facebook-users')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Loaded Facebook data:', data);
                
                if (userProfileCard && Array.isArray(data) && data.length > 0) {
                    const profile = data[0]; // Show first profile
                    userProfileCard.innerHTML = `
                        <h3>${escapeHtml(profile.name || 'Unknown User')}</h3>
                        <p>${escapeHtml(profile.bio || 'No bio available')}</p>
                        <p><strong>Connected Accounts:</strong> ${Array.isArray(profile.connected_accounts) ? 
                            profile.connected_accounts.map(acc => escapeHtml(acc)).join(', ') : 
                            'None'}</p>
                        ${profile.profile_url && profile.profile_url !== '#' ? 
                            `<a href="${escapeHtml(profile.profile_url)}" target="_blank" class="btn">View Profile</a>` : 
                            ''
                        }
                    `;
                } else if (userProfileCard) {
                    userProfileCard.innerHTML = `
                        <h3>No Facebook Profiles</h3>
                        <p>No Facebook profiles have been scraped yet.</p>
                    `;
                }
            })
            .catch(error => {
                console.error('Error fetching Facebook user data:', error);
                if (userProfileCard) {
                    userProfileCard.innerHTML = `
                        <h3>Error Loading Profile</h3>
                        <p>Could not load Facebook profile data: ${error.message}</p>
                    `;
                }
            });
    }
    
    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});