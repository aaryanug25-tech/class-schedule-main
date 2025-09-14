// Chart.js Integration

async function loadTeacherClassDistribution() {
    try {
        const response = await fetch('/api/teacher-class-counts');
        const data = await response.json();
        
        const ctx = document.getElementById('teacherClassChart');
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.counts,
                    backgroundColor: [
                        '#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981',
                        '#3B82F6', '#8B5CF6', '#F472B6', '#F97316', '#34D399',
                        '#6366F1', '#A855F7', '#FB7185', '#FBBF24', '#2DD4BF'
                    ],
                    borderColor: 'rgba(255, 255, 255, 0.5)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text')
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.raw} classes`;
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Teacher Class Distribution',
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text'),
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading teacher class distribution:', error);
    }
}

async function loadRoomUsage() {
    try {
        const response = await fetch('/api/room-usage');
        const data = await response.json();
        
        const ctx = document.getElementById('roomUsageChart');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Classes per Room',
                    data: data.counts,
                    backgroundColor: 'rgba(79, 70, 229, 0.6)',
                    borderColor: 'rgba(79, 70, 229, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text')
                        },
                        grid: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--border')
                        }
                    },
                    x: {
                        ticks: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text')
                        },
                        grid: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--border')
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text')
                        }
                    },
                    title: {
                        display: true,
                        text: 'Room Usage Analysis',
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text'),
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading room usage:', error);
    }
}

async function loadCourseDistribution() {
    try {
        const response = await fetch('/api/course-distribution');
        const data = await response.json();
        
        const ctx = document.getElementById('courseDistributionChart');
        
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.counts,
                    backgroundColor: [
                        '#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981',
                        '#3B82F6', '#8B5CF6', '#F472B6', '#F97316', '#34D399',
                        '#6366F1', '#A855F7', '#FB7185', '#FBBF24', '#2DD4BF'
                    ],
                    borderColor: 'rgba(255, 255, 255, 0.5)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text')
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.raw} classes`;
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Course Distribution',
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text'),
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading course distribution:', error);
    }
}

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    const teacherChartElement = document.getElementById('teacherClassChart');
    const roomChartElement = document.getElementById('roomUsageChart');
    const courseChartElement = document.getElementById('courseDistributionChart');
    
    if (teacherChartElement) {
        loadTeacherClassDistribution();
    }
    
    if (roomChartElement) {
        loadRoomUsage();
    }
    
    if (courseChartElement) {
        loadCourseDistribution();
    }
});
