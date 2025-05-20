// Common JavaScript functions for the Exam Management System

// Auto-save form data to localStorage
function autoSaveForm(formId, saveKey, intervalMs = 30000) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    // Check for saved data and restore it
    const savedData = localStorage.getItem(saveKey);
    if (savedData) {
        const formData = JSON.parse(savedData);
        Object.keys(formData).forEach(name => {
            const input = form.elements[name];
            if (input) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    input.checked = formData[name];
                } else {
                    input.value = formData[name];
                }
            }
        });
    }
    
    // Set up auto-save at interval
    setInterval(() => {
        const data = {};
        Array.from(form.elements).forEach(input => {
            if (input.name) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    data[input.name] = input.checked;
                } else {
                    data[input.name] = input.value;
                }
            }
        });
        localStorage.setItem(saveKey, JSON.stringify(data));
    }, intervalMs);
    
    // Clear saved data on form submission
    form.addEventListener('submit', () => {
        localStorage.removeItem(saveKey);
    });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap tooltips 
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Format exam timer
function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    return [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        secs.toString().padStart(2, '0')
    ].join(':');
}

// Toggle password visibility
function togglePasswordVisibility(inputId, toggleBtnId) {
    const passwordInput = document.getElementById(inputId);
    const toggleBtn = document.getElementById(toggleBtnId);
    
    if (passwordInput && toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Update button text
            toggleBtn.textContent = type === 'password' ? 'Show' : 'Hide';
        });
    }
}

// Confirm action with custom modal
function confirmAction(title, message, confirmBtnText, cancelBtnText, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'confirmModal';
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-labelledby', 'confirmModalLabel');
    modal.setAttribute('aria-hidden', 'true');
    
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="confirmModalLabel">${title}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    ${message}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelBtnText || 'Cancel'}</button>
                    <button type="button" class="btn btn-primary" id="confirmActionBtn">${confirmBtnText || 'Confirm'}</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const modalElement = new bootstrap.Modal(modal);
    modalElement.show();
    
    document.getElementById('confirmActionBtn').addEventListener('click', () => {
        onConfirm();
        modalElement.hide();
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    });
    
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
}
