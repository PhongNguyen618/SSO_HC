
        document.getElementById('mobileMenuBtn').addEventListener('click', function() {
            const navLinks = document.querySelector('.navbar-links');
            navLinks.classList.toggle('show');
            const icon = this.querySelector('i');
            if (navLinks.classList.contains('show')) {
                icon.className = 'fa-solid fa-xmark';
            } else {
                icon.className = 'fa-solid fa-bars';
            }
        });
    