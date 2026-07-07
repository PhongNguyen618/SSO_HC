
    // Lightbox handlers
    const galleryImages = "jinja_var";
    let currentLightboxIndex = 0;

    function openLightbox(index) {
        currentLightboxIndex = index;
        updateLightboxImage();
        
        const lightbox = document.getElementById('imageLightbox');
        if (lightbox) {
            lightbox.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    function updateLightboxImage() {
        const lightboxImg = document.getElementById('lightboxImage');
        if (lightboxImg && galleryImages[currentLightboxIndex]) {
            lightboxImg.src = galleryImages[currentLightboxIndex];
        }
    }

    function changeLightboxImage(direction, event) {
        if (event) {
            event.stopPropagation();
        }
        currentLightboxIndex += direction;
        if (currentLightboxIndex >= galleryImages.length) {
            currentLightboxIndex = 0;
        } else if (currentLightboxIndex < 0) {
            currentLightboxIndex = galleryImages.length - 1;
        }
        updateLightboxImage();
    }

    function closeLightbox() {
        const lightbox = document.getElementById('imageLightbox');
        if (lightbox) {
            lightbox.style.display = 'none';
            document.body.style.overflow = '';
        }
    }
    
    // Đóng bằng phím ESC và chuyển ảnh bằng phím mũi tên
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLightbox();
        } else if (e.key === 'ArrowRight') {
            const lightbox = document.getElementById('imageLightbox');
            if (lightbox && lightbox.style.display === 'flex') {
                changeLightboxImage(1);
            }
        } else if (e.key === 'ArrowLeft') {
            const lightbox = document.getElementById('imageLightbox');
            if (lightbox && lightbox.style.display === 'flex') {
                changeLightboxImage(-1);
            }
        }
    });
    
    // --- GALLERY SLIDER LOGIC ---
    let currentSlideIndex = 0;
    let sliderInterval = null;
    let isMouseOverSlider = false;
    const slides = document.querySelectorAll('.gallery-slide');
    const dots = document.querySelectorAll('.slider-dot');
    
    function showSlide(index) {
        if (slides.length === 0) return;
        
        if (index >= slides.length) {
            currentSlideIndex = 0;
        } else if (index < 0) {
            currentSlideIndex = slides.length - 1;
        } else {
            currentSlideIndex = index;
        }
        
        slides.forEach(slide => slide.classList.remove('active'));
        dots.forEach(dot => dot.classList.remove('active'));
        
        if (slides[currentSlideIndex]) {
            slides[currentSlideIndex].classList.add('active');
        }
        if (dots[currentSlideIndex]) {
            dots[currentSlideIndex].classList.add('active');
        }
    }
    
    function moveSlide(direction) {
        showSlide(currentSlideIndex + direction);
        resetSliderTimer();
    }
    
    function currentSlide(index) {
        showSlide(index);
        resetSliderTimer();
    }
    
    function startSliderAutoPlay() {
        stopSliderAutoPlay();
        if (slides.length > 1) {
            sliderInterval = setInterval(() => {
                if (!isMouseOverSlider) {
                    showSlide(currentSlideIndex + 1);
                }
            }, 3500); // Tự trôi sau mỗi 3.5 giây
        }
    }
    
    function stopSliderAutoPlay() {
        if (sliderInterval) {
            clearInterval(sliderInterval);
            sliderInterval = null;
        }
    }
    
    function resetSliderTimer() {
        startSliderAutoPlay();
    }
    
    window.addEventListener('DOMContentLoaded', () => {
        const sliderWrapper = document.querySelector('.gallery-slider-wrapper');
        if (sliderWrapper) {
            sliderWrapper.addEventListener('mouseenter', () => {
                isMouseOverSlider = true;
            });
            sliderWrapper.addEventListener('mouseleave', () => {
                isMouseOverSlider = false;
            });
            
            startSliderAutoPlay();
        }
    });
