// ClipGenius - Frontend Logic

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const form = document.getElementById('extract-form');
    const extractorCard = document.querySelector('.extractor-card');
    const processingState = document.getElementById('processing-state');
    const resultsState = document.getElementById('results-state');
    const newExtractionBtn = document.getElementById('new-extraction-btn');
    const submitBtn = document.getElementById('submit-btn');
    
    // Status elements
    const statusHeading = document.getElementById('status-heading');
    const statusText = document.getElementById('status-text');
    const progressFill = document.getElementById('progress-fill');
    const steps = document.querySelectorAll('.step');
    
    // Toast
    const toast = document.getElementById('error-toast');
    const toastMessage = document.getElementById('error-message');
    
    let currentJobId = null;
    let pollInterval = null;

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const urlInput = document.getElementById('youtube-url').value;
        const durationInput = parseInt(document.getElementById('clip-duration').value);
        const clipsInput = parseInt(document.getElementById('max-clips').value);
        const formatInput = document.getElementById('video-format').value;
        
        if (!urlInput) return showError("Please enter a valid YouTube URL");
        
        try {
            // Disable button and show loading state
            submitBtn.disabled = true;
            submitBtn.querySelector('.btn-text').textContent = 'Starting...';
            
            // Start the extraction job
            const response = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: urlInput,
                    duration: durationInput,
                    clips: clipsInput,
                    format: formatInput
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to start extraction');
            }
            
            currentJobId = data.job_id;
            
            // Transition UI
            extractorCard.classList.add('hidden');
            processingState.classList.remove('hidden');
            
            // Start polling for status
            startPolling();
            
        } catch (error) {
            showError(error.message);
            submitBtn.disabled = false;
            submitBtn.querySelector('.btn-text').textContent = 'Extract Viral Clips';
        }
    });
    
    // Handle "Extract Another" button
    newExtractionBtn.addEventListener('click', () => {
        resultsState.classList.add('hidden');
        extractorCard.classList.remove('hidden');
        form.reset();
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').textContent = 'Extract Viral Clips';
        currentJobId = null;
        
        // Reset progress UI
        progressFill.style.width = '0%';
        steps.forEach(step => {
            step.classList.remove('active', 'completed');
        });
    });

    // Poll the backend for job status
    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        
        // Poll every 1.5 seconds
        pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${currentJobId}`);
                if (!response.ok) throw new Error('Failed to get status');
                
                const data = await response.json();
                updateProgressUI(data);
                
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    setTimeout(() => showResults(data.results), 1000);
                } else if (data.status === 'error') {
                    clearInterval(pollInterval);
                    showError(data.error || 'An error occurred during processing');
                    resetToStart();
                }
                
            } catch (error) {
                console.error("Polling error:", error);
                // Don't stop polling on single network error, but log it
            }
        }, 1500);
    }
    
    // Update progress bar and steps based on backend message
    function updateProgressUI(data) {
        statusText.textContent = data.progress;
        
        const progress = data.progress.toLowerCase();
        let stepIndex = 0;
        let percentage = 5;
        
        if (progress.includes('download')) {
            stepIndex = 1;
            percentage = 25;
            statusHeading.textContent = 'Downloading Video';
        } else if (progress.includes('extracting audio')) {
            stepIndex = 1;
            percentage = 40;
            statusHeading.textContent = 'Processing Media';
        } else if (progress.includes('analysing')) {
            stepIndex = 2;
            percentage = 60;
            statusHeading.textContent = 'Running AI Analysis';
        } else if (progress.includes('viral')) {
            stepIndex = 3;
            percentage = 80;
            statusHeading.textContent = 'Scoring Moments';
        } else if (progress.includes('generating')) {
            stepIndex = 4;
            percentage = 90;
            statusHeading.textContent = 'Rendering Clips';
        } else if (data.status === 'completed') {
            stepIndex = 4;
            percentage = 100;
            statusHeading.textContent = 'Complete!';
        }
        
        progressFill.style.width = `${percentage}%`;
        
        // Update step indicators
        steps.forEach((step, index) => {
            const stepNum = parseInt(step.dataset.step);
            
            if (stepNum < stepIndex) {
                step.classList.add('completed');
                step.classList.remove('active');
            } else if (stepNum === stepIndex) {
                step.classList.add('active');
                step.classList.remove('completed');
            } else {
                step.classList.remove('completed', 'active');
            }
        });
    }
    
    // Display the generated clips
    function showResults(clips) {
        processingState.classList.add('hidden');
        resultsState.classList.remove('hidden');
        
        const grid = document.getElementById('clips-grid');
        grid.innerHTML = '';
        
        if (!clips || clips.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 3rem; background: var(--bg-surface); border-radius: var(--radius-md);">
                    <i data-lucide="frown" style="width: 48px; height: 48px; color: var(--text-muted); margin-bottom: 1rem;"></i>
                    <h3>No viral moments detected</h3>
                    <p style="color: var(--text-muted);">Try a different video or adjust the settings.</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }
        
        clips.forEach((clip, index) => {
            const delay = index * 0.15; // Staggered animation delay
            
            // Format score as percentage
            const scorePercent = (clip.score * 100).toFixed(1) + '%';
            
            const card = document.createElement('div');
            card.className = 'clip-card';
            card.style.animationDelay = `${delay}s`;
            
            card.innerHTML = `
                <div class="clip-video-container">
                    <video controls preload="metadata">
                        <source src="${clip.url}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                </div>
                <div class="clip-details">
                    <div class="clip-header">
                        <span class="clip-rank">Clip #${clip.rank}</span>
                        <span class="clip-score"><i data-lucide="flame" style="width: 14px; height: 14px;"></i> ${scorePercent}</span>
                    </div>
                    
                    <div class="clip-info">
                        <p>Timestamp: <span>${clip.start} - ${clip.end}</span></p>
                        <p>Duration: <span>${clip.duration}s</span></p>
                        <p>Size: <span>${clip.size_mb} MB</span></p>
                    </div>
                    
                    <div class="clip-reason">
                        ${clip.reason || 'High engagement signals detected'}
                    </div>
                    
                    <a href="${clip.url}" download="clipgenius_clip_${clip.rank}.mp4" class="download-clip-btn">
                        <i data-lucide="download" style="width: 18px; height: 18px;"></i> Download Clip
                    </a>
                </div>
            `;
            
            grid.appendChild(card);
        });
        
        // Re-initialize icons for dynamically added content
        lucide.createIcons();
    }
    
    function resetToStart() {
        processingState.classList.add('hidden');
        extractorCard.classList.remove('hidden');
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').textContent = 'Extract Viral Clips';
    }
    
    function showError(message) {
        toastMessage.textContent = message;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 5000);
    }
});
