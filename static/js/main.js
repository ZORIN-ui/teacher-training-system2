// Main JavaScript for Teacher Training System

$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);

    // Smooth scrolling for anchor links
    $('a[href^="#"]').on('click', function(event) {
        var target = $(this.getAttribute('href'));
        if( target.length ) {
            event.preventDefault();
            $('html, body').stop().animate({
                scrollTop: target.offset().top - 100
            }, 1000);
        }
    });

    // Loading spinner functions
    window.showSpinner = function() {
        if (!$('.spinner-overlay').length) {
            $('body').append(`
                <div class="spinner-overlay">
                    <div class="spinner-border spinner-border-custom text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `);
        }
    };

    window.hideSpinner = function() {
        $('.spinner-overlay').remove();
    };

    // Form validation enhancement
    $('form').on('submit', function() {
        var form = this;
        if (form.checkValidity() === false) {
            event.preventDefault();
            event.stopPropagation();
        }
        form.classList.add('was-validated');
    });

    // Search functionality
    $('#searchInput').on('keyup', function() {
        var value = $(this).val().toLowerCase();
        $('.searchable').filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
    });

    // Progress tracking
    window.updateProgress = function(lessonId, timeSpent) {
        return $.ajax({
            url: '/complete_lesson/' + lessonId,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                time_spent: timeSpent
            }),
            success: function(response) {
                if (response.success) {
                    showNotification('Lesson completed successfully!', 'success');
                    updateProgressBar();
                }
            },
            error: function() {
                showNotification('Error updating progress. Please try again.', 'error');
            }
        });
    };

    // Notification system
    window.showNotification = function(message, type = 'info') {
        var alertClass = 'alert-' + (type === 'error' ? 'danger' : type);
        var notification = `
            <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
                 style="top: 20px; right: 20px; z-index: 1050; min-width: 300px;" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        $('body').append(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(function() {
            $('.alert').last().fadeOut('slow', function() {
                $(this).remove();
            });
        }, 5000);
    };

    // Course enrollment
    window.enrollCourse = function(courseId) {
        showSpinner();
        
        $.ajax({
            url: '/enroll/' + courseId,
            method: 'POST',
            success: function() {
                hideSpinner();
                showNotification('Successfully enrolled in course!', 'success');
                setTimeout(function() {
                    location.reload();
                }, 1500);
            },
            error: function() {
                hideSpinner();
                showNotification('Error enrolling in course. Please try again.', 'error');
            }
        });
    };

    // Quiz functionality
    window.QuizManager = {
        currentQuestion: 0,
        answers: {},
        timeRemaining: 0,
        timer: null,

        init: function(questions, timeLimit) {
            this.questions = questions;
            this.timeRemaining = timeLimit * 60; // Convert to seconds
            this.startTimer();
            this.showQuestion(0);
        },

        startTimer: function() {
            this.timer = setInterval(() => {
                this.timeRemaining--;
                this.updateTimerDisplay();
                
                if (this.timeRemaining <= 0) {
                    this.submitQuiz();
                }
            }, 1000);
        },

        updateTimerDisplay: function() {
            var minutes = Math.floor(this.timeRemaining / 60);
            var seconds = this.timeRemaining % 60;
            $('#timer').text(minutes + ':' + (seconds < 10 ? '0' : '') + seconds);
        },

        showQuestion: function(index) {
            this.currentQuestion = index;
            var question = this.questions[index];
            
            $('#questionText').text(question.text);
            $('#questionNumber').text((index + 1) + ' of ' + this.questions.length);
            
            var optionsHtml = '';
            question.options.forEach((option, i) => {
                optionsHtml += `
                    <div class="quiz-option" data-value="${i}">
                        <input type="radio" name="answer" value="${i}" id="option${i}">
                        <label for="option${i}" class="ms-2">${option}</label>
                    </div>
                `;
            });
            
            $('#questionOptions').html(optionsHtml);
            
            // Restore previous answer if exists
            if (this.answers[index] !== undefined) {
                $(`input[value="${this.answers[index]}"]`).prop('checked', true);
                $(`.quiz-option[data-value="${this.answers[index]}"]`).addClass('selected');
            }
            
            // Update navigation buttons
            $('#prevBtn').prop('disabled', index === 0);
            $('#nextBtn').text(index === this.questions.length - 1 ? 'Submit' : 'Next');
        },

        saveAnswer: function() {
            var selectedAnswer = $('input[name="answer"]:checked').val();
            if (selectedAnswer !== undefined) {
                this.answers[this.currentQuestion] = parseInt(selectedAnswer);
            }
        },

        nextQuestion: function() {
            this.saveAnswer();
            
            if (this.currentQuestion < this.questions.length - 1) {
                this.showQuestion(this.currentQuestion + 1);
            } else {
                this.submitQuiz();
            }
        },

        prevQuestion: function() {
            this.saveAnswer();
            
            if (this.currentQuestion > 0) {
                this.showQuestion(this.currentQuestion - 1);
            }
        },

        submitQuiz: function() {
            clearInterval(this.timer);
            this.saveAnswer();
            
            showSpinner();
            
            $.ajax({
                url: '/submit_quiz',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    quiz_id: $('#quizId').val(),
                    answers: this.answers
                }),
                success: function(response) {
                    hideSpinner();
                    window.location.href = '/quiz_result/' + response.attempt_id;
                },
                error: function() {
                    hideSpinner();
                    showNotification('Error submitting quiz. Please try again.', 'error');
                }
            });
        }
    };

    // Quiz option selection
    $(document).on('click', '.quiz-option', function() {
        $('.quiz-option').removeClass('selected');
        $(this).addClass('selected');
        $(this).find('input').prop('checked', true);
    });

    // File upload preview
    $('input[type="file"]').on('change', function() {
        var file = this.files[0];
        if (file) {
            var reader = new FileReader();
            reader.onload = function(e) {
                var preview = $(this).siblings('.file-preview');
                if (file.type.startsWith('image/')) {
                    preview.html(`<img src="${e.target.result}" class="img-thumbnail" style="max-width: 200px;">`);
                } else {
                    preview.html(`<p class="text-muted">File selected: ${file.name}</p>`);
                }
            }.bind(this);
            reader.readAsDataURL(file);
        }
    });

    // Discussion forum functionality
    window.DiscussionManager = {
        loadDiscussions: function(courseId) {
            $.get('/api/discussions/' + courseId, function(discussions) {
                var html = '';
                discussions.forEach(discussion => {
                    html += this.renderDiscussion(discussion);
                });
                $('#discussionsList').html(html);
            }.bind(this));
        },

        renderDiscussion: function(discussion) {
            return `
                <div class="discussion-post card mb-3">
                    <div class="card-body">
                        <h6 class="card-title">${discussion.title}</h6>
                        <p class="card-text">${discussion.content}</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">
                                By ${discussion.author.full_name} on ${new Date(discussion.created_at).toLocaleDateString()}
                            </small>
                            <button class="btn btn-sm btn-outline-primary" onclick="DiscussionManager.showReplies(${discussion.id})">
                                Replies (${discussion.replies.length})
                            </button>
                        </div>
                    </div>
                </div>
            `;
        },

        showReplies: function(discussionId) {
            // Implementation for showing replies
            console.log('Show replies for discussion:', discussionId);
        },

        postDiscussion: function(courseId, title, content) {
            $.ajax({
                url: '/api/discussions',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    course_id: courseId,
                    title: title,
                    content: content
                }),
                success: function() {
                    showNotification('Discussion posted successfully!', 'success');
                    this.loadDiscussions(courseId);
                }.bind(this),
                error: function() {
                    showNotification('Error posting discussion. Please try again.', 'error');
                }
            });
        }
    };

    // Video player tracking
    window.VideoTracker = {
        startTime: null,
        totalWatched: 0,

        init: function() {
            this.startTime = Date.now();
        },

        pause: function() {
            if (this.startTime) {
                this.totalWatched += Date.now() - this.startTime;
                this.startTime = null;
            }
        },

        resume: function() {
            this.startTime = Date.now();
        },

        getTotalWatchTime: function() {
            var current = this.startTime ? Date.now() - this.startTime : 0;
            return Math.floor((this.totalWatched + current) / 1000 / 60); // Return minutes
        }
    };

    // Initialize video tracking if video exists
    if ($('video').length) {
        VideoTracker.init();
        
        $('video').on('play', function() {
            VideoTracker.resume();
        });
        
        $('video').on('pause', function() {
            VideoTracker.pause();
        });
        
        $('video').on('ended', function() {
            VideoTracker.pause();
            var timeSpent = VideoTracker.getTotalWatchTime();
            // Auto-complete lesson when video ends
            if (typeof lessonId !== 'undefined') {
                updateProgress(lessonId, timeSpent);
            }
        });
    }

    // Search and filter functionality
    $('#courseSearch').on('keyup', function() {
        var searchTerm = $(this).val().toLowerCase();
        $('.course-card').each(function() {
            var courseTitle = $(this).find('.card-title').text().toLowerCase();
            var courseDescription = $(this).find('.card-text').text().toLowerCase();
            
            if (courseTitle.includes(searchTerm) || courseDescription.includes(searchTerm)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });

    // Category and level filters
    $('#categoryFilter, #levelFilter').on('change', function() {
        var category = $('#categoryFilter').val();
        var level = $('#levelFilter').val();
        
        $('.course-card').each(function() {
            var courseCategory = $(this).data('category');
            var courseLevel = $(this).data('level');
            var show = true;
            
            if (category && courseCategory !== category) {
                show = false;
            }
            
            if (level && courseLevel !== level) {
                show = false;
            }
            
            if (show) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });

    // Progress bar animation
    function animateProgressBars() {
        $('.progress-bar').each(function() {
            var width = $(this).attr('style').match(/width:\s*(\d+(?:\.\d+)?)%/);
            if (width) {
                $(this).css('width', '0%').animate({
                    width: width[1] + '%'
                }, 1000);
            }
        });
    }

    // Animate progress bars when they come into view
    $(window).on('scroll', function() {
        $('.progress').each(function() {
            var elementTop = $(this).offset().top;
            var elementBottom = elementTop + $(this).outerHeight();
            var viewportTop = $(window).scrollTop();
            var viewportBottom = viewportTop + $(window).height();
            
            if (elementBottom > viewportTop && elementTop < viewportBottom) {
                if (!$(this).hasClass('animated')) {
                    $(this).addClass('animated');
                    animateProgressBars();
                }
            }
        });
    });

    // Initialize animations on page load
    setTimeout(animateProgressBars, 500);
});

// Utility functions
function formatDuration(minutes) {
    if (minutes < 60) {
        return minutes + ' minutes';
    } else {
        var hours = Math.floor(minutes / 60);
        var remainingMinutes = minutes % 60;
        if (remainingMinutes === 0) {
            return hours + ' hour' + (hours !== 1 ? 's' : '');
        } else {
            return hours + ' hour' + (hours !== 1 ? 's' : '') + ' ' + remainingMinutes + ' minutes';
        }
    }
}

function formatDate(dateString) {
    var date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function formatDateTime(dateString) {
    var date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Export functions for global use
window.showSpinner = window.showSpinner;
window.hideSpinner = window.hideSpinner;
window.showNotification = window.showNotification;
window.enrollCourse = window.enrollCourse;
window.updateProgress = window.updateProgress;
window.QuizManager = window.QuizManager;
window.DiscussionManager = window.DiscussionManager;
window.VideoTracker = window.VideoTracker;
