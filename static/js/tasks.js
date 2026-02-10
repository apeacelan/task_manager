// tasks.js - Enhanced version
document.addEventListener('DOMContentLoaded', () => {
    // Initialize task actions
    initTaskActions();
    
    // Initialize form enhancements
    initFormEnhancements();
    
    // Initialize date pickers
    initDatePickers();
    
    // Initialize priority indicators
    initPriorityIndicators();
});

function initTaskActions() {
    // Toggle task completion
    document.querySelectorAll('.toggle-task-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const taskId = btn.dataset.taskId;
            const form = btn.closest('form');
            
            if (!form) return;
            
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams(new FormData(form))
                });
                
                if (response.ok) {
                    // Update button state immediately for better UX
                    if (btn.textContent.includes('Complete')) {
                        btn.textContent = 'Mark Incomplete';
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-secondary');
                    } else {
                        btn.textContent = 'Mark Complete';
                        btn.classList.remove('btn-secondary');
                        btn.classList.add('btn-success');
                    }
                    
                    // Optional: Reload after a short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 500);
                }
            } catch (err) {
                console.error('Error toggling task:', err);
                alert('Error updating task. Please try again.');
            }
        });
    });

    // Delete task with confirmation
    document.querySelectorAll('.delete-task-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const taskId = btn.dataset.taskId;
            const form = btn.closest('form');
            
            if (!form) return;
            
            if (confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: new URLSearchParams(new FormData(form))
                    });
                    
                    if (response.ok) {
                        // Remove the task row immediately for better UX
                        const taskRow = btn.closest('tr');
                        if (taskRow) {
                            taskRow.style.opacity = '0.5';
                            taskRow.style.transition = 'opacity 0.3s';
                            setTimeout(() => {
                                taskRow.remove();
                                
                                // Show message if no tasks left
                                const tbody = document.querySelector('tbody');
                                if (tbody && tbody.children.length === 0) {
                                    const table = document.querySelector('table');
                                    const container = table.closest('.task-table-container');
                                    container.innerHTML = '<p>No tasks found. Add your first task!</p>';
                                }
                            }, 300);
                        }
                    }
                } catch (err) {
                    console.error('Error deleting task:', err);
                    alert('Error deleting task. Please try again.');
                }
            }
        });
    });
}

function initFormEnhancements() {
    // Auto-focus first input in forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const firstInput = form.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => {
                firstInput.focus();
            }, 100);
        }
        
        // Add real-time validation
        form.querySelectorAll('input[required]').forEach(input => {
            input.addEventListener('blur', () => {
                validateField(input);
            });
            
            input.addEventListener('input', () => {
                if (input.classList.contains('error')) {
                    validateField(input);
                }
            });
        });
    });
}

function initDatePickers() {
    // Set min date to today for deadline inputs
    const today = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"][name="deadline"]').forEach(input => {
        if (!input.value) {
            input.value = today;
        }
        input.min = today;
    });
}

function initPriorityIndicators() {
    // Add visual indicators for priority
    document.querySelectorAll('.priority-high, .priority-medium, .priority-low').forEach(el => {
        const priority = el.textContent.trim();
        let icon = '';
        
        switch(priority) {
            case 'High':
                icon = '🔥';
                break;
            case 'Medium':
                icon = '⚠️';
                break;
            case 'Low':
                icon = '✅';
                break;
        }
        
        if (icon) {
            el.innerHTML = `${icon} ${priority}`;
        }
    });
}

function validateField(input) {
    if (input.hasAttribute('required') && !input.value.trim()) {
        input.classList.add('error');
        input.style.borderColor = '#f72585';
        return false;
    } else {
        input.classList.remove('error');
        input.style.borderColor = '';
        return true;
    }
}

// Utility function to show notifications
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    if (type === 'success') {
        notification.style.background = '#4cc9f0';
    } else if (type === 'error') {
        notification.style.background = '#f72585';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .error {
        border-color: #f72585 !important;
    }
    
    .notification {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
`;
document.head.appendChild(style);