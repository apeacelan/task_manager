// charts.js - FIXED version
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on statistics page
    if (!document.getElementById('priorityChart') && 
        !document.getElementById('weeklyChart') && 
        !document.getElementById('completionChart')) {
        return;
    }

    // Priority Chart
    fetch('/api/stats/priority')
        .then(res => {
            if (!res.ok) throw new Error('Failed to load priority data');
            return res.json();
        })
        .then(data => {
            const ctx = document.getElementById('priorityChart');
            if (!ctx) return;
            
            new Chart(ctx.getContext('2d'), {
                type: 'pie',
                data: {
                    labels: Object.keys(data),
                    datasets: [{
                        data: Object.values(data),
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56'],
                    }]
                },
                options: { 
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading priority chart:', error);
            showChartError('priorityChart', 'Priority data unavailable');
        });

    // Weekly Completion Chart
    fetch('/api/stats/weekly')
        .then(res => {
            if (!res.ok) throw new Error('Failed to load weekly data');
            return res.json();
        })
        .then(data => {
            const ctx = document.getElementById('weeklyChart');
            if (!ctx) return;
            
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const chartData = days.map(day => data[day] || 0);
            
            new Chart(ctx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: days,
                    datasets: [{
                        label: 'Tasks Completed',
                        data: chartData,
                        backgroundColor: '#36A2EB'
                    }]
                },
                options: { 
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { 
                        y: { 
                            beginAtZero: true,
                            ticks: { stepSize: 1 }
                        } 
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading weekly chart:', error);
            showChartError('weeklyChart', 'Weekly data unavailable');
        });

    // Monthly Completion Chart
    fetch('/api/stats/completion')
        .then(res => {
            if (!res.ok) throw new Error('Failed to load completion data');
            return res.json();
        })
        .then(data => {
            const ctx = document.getElementById('completionChart');
            if (!ctx) return;
            
            const labels = data.map(d => d.month);
            const total = data.map(d => d.total);
            const completed = data.map(d => d.completed);

            new Chart(ctx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Total Tasks',
                            data: total,
                            borderColor: '#FF6384',
                            backgroundColor: 'rgba(255, 99, 132, 0.1)',
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Completed Tasks',
                            data: completed,
                            borderColor: '#36A2EB',
                            backgroundColor: 'rgba(54, 162, 235, 0.1)',
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: { 
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { 
                        y: { 
                            beginAtZero: true,
                            ticks: { stepSize: 1 }
                        } 
                    },
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        })
        .catch(error => {
            console.error('Error loading completion chart:', error);
            showChartError('completionChart', 'Completion data unavailable');
        });
});

function showChartError(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (canvas) {
        canvas.parentElement.innerHTML = `<div class="alert alert-warning">${message}</div>`;
    }
}