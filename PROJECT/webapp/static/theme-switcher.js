document.addEventListener('DOMContentLoaded', function() {
    // Check if dark mode is stored in localStorage
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    const themeSelect = document.getElementById('theme-select');
    const themeToggle = document.getElementById('theme-toggle');
    
    // Apply dark mode if it was previously selected
    if (isDarkMode) {
        document.documentElement.classList.add('dark-theme');
        if (themeSelect) {
            themeSelect.value = 'dark';
        }
        if (themeToggle) {
            themeToggle.classList.add('active');
        }
    }

    // Theme toggle button functionality
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            // Toggle the class
            document.documentElement.classList.toggle('dark-theme');
            
            // Store the preference
            const isDarkMode = document.documentElement.classList.contains('dark-theme');
            localStorage.setItem('darkMode', isDarkMode);
            
            // Toggle the animation state
            this.classList.toggle('active');
            
            // Update the dropdown if it exists
            if (themeSelect) {
                themeSelect.value = isDarkMode ? 'dark' : 'light';
            }
        });
    }
    
    // Theme dropdown functionality
    if (themeSelect) {
        themeSelect.addEventListener('change', function() {
            const isDarkMode = this.value === 'dark';
            
            if (isDarkMode) {
                document.documentElement.classList.add('dark-theme');
            } else {
                document.documentElement.classList.remove('dark-theme');
            }
            
            // Store the preference
            localStorage.setItem('darkMode', isDarkMode);
            
            // Update toggle button if it exists
            if (themeToggle) {
                if (isDarkMode) {
                    themeToggle.classList.add('active');
                } else {
                    themeToggle.classList.remove('active');
                }
            }
        });
    }
});
