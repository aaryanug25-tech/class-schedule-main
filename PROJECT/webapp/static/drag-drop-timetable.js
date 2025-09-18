/**
 * Drag and Drop Functionality for Timetable
 * Allows admin to rearrange classes and automatically detects conflicts
 */

document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on the generate_timetable page
    if (document.querySelector('.timetable-container')) {
        initializeDragAndDrop();
    }
});

function initializeDragAndDrop() {
    const subjectBlocks = document.querySelectorAll('.subject-block');
    const timetableCells = document.querySelectorAll('.schedule-cell');
    
    // Track conflicts
    let conflicts = [];
    
    // Make subject blocks draggable
    subjectBlocks.forEach(block => {
        block.setAttribute('draggable', true);
        
        // Store original position and data
        block.dataset.originalCell = block.parentElement.id;
        block.dataset.originalDay = block.parentElement.dataset.day;
        block.dataset.originalTime = block.parentElement.dataset.time;
        block.dataset.classGroup = block.querySelector('.class-badge')?.textContent || '';
        block.dataset.subject = block.querySelector('.subject-name')?.textContent || '';
        block.dataset.teacher = block.querySelector('.teacher-name')?.textContent || '';
        block.dataset.room = block.querySelector('.room-badge')?.textContent.replace('Room: ', '') || '';
        
        // Add drag events
        block.addEventListener('dragstart', handleDragStart);
    });
    
    // Make cells droppable
    timetableCells.forEach(cell => {
        cell.addEventListener('dragover', handleDragOver);
        cell.addEventListener('dragleave', handleDragLeave);
        cell.addEventListener('drop', handleDrop);
    });
    
    // Drag event handlers
    function handleDragStart(e) {
        e.dataTransfer.setData('text/plain', e.target.id);
        e.dataTransfer.effectAllowed = 'move';
        this.classList.add('dragging');
        
        // Highlight valid drop targets
        highlightValidDropTargets(e.target);
    }
    
    function handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        this.classList.add('dragover');
    }
    
    function handleDragLeave(e) {
        this.classList.remove('dragover');
    }
    
    function handleDrop(e) {
        e.preventDefault();
        
        // Remove highlight classes
        document.querySelectorAll('.dragover').forEach(el => el.classList.remove('dragover'));
        document.querySelectorAll('.valid-target').forEach(el => el.classList.remove('valid-target'));
        
        const blockId = e.dataTransfer.getData('text/plain');
        const draggedBlock = document.getElementById(blockId);
        
        // If nothing was dragged or this cell already has content (except for the dragged element itself)
        if (!draggedBlock || (this.querySelector('.subject-block') && this.querySelector('.subject-block') !== draggedBlock)) {
            // Check for conflicts
            if (this.querySelector('.subject-block')) {
                showConflict(draggedBlock, this.querySelector('.subject-block'));
            }
            return;
        }
        
        // Remove from old position and add to new
        if (draggedBlock.parentElement) {
            draggedBlock.parentElement.classList.remove('has-subject');
        }
        
        this.appendChild(draggedBlock);
        this.classList.add('has-subject');
        draggedBlock.classList.remove('dragging');
        
        // Check for conflicts after drop
        checkForConflicts();
        
        // Save the changes to the server
        saveChanges(draggedBlock, this);
    }
    
    function highlightValidDropTargets(draggedBlock) {
        // All cells are valid for admin, just highlight empty ones more prominently
        timetableCells.forEach(cell => {
            if (!cell.querySelector('.subject-block') || cell.querySelector('.subject-block') === draggedBlock) {
                cell.classList.add('valid-target');
            }
        });
    }
    
    function checkForConflicts() {
        conflicts = [];
        const timeSlots = {};
        
        // Group all classes by time slot and check for conflicts
        subjectBlocks.forEach(block => {
            const day = block.parentElement.dataset.day;
            const time = block.parentElement.dataset.time;
            const key = `${day}-${time}`;
            const teacher = block.dataset.teacher;
            const room = block.dataset.room;
            const classGroup = block.dataset.classGroup;
            
            if (!timeSlots[key]) {
                timeSlots[key] = [];
            }
            
            // Check for existing blocks in this time slot
            timeSlots[key].forEach(existingBlock => {
                // Teacher conflict - same teacher, same time, different class
                if (existingBlock.teacher === teacher && existingBlock.classGroup !== classGroup) {
                    conflicts.push({
                        type: 'teacher',
                        teacher: teacher,
                        day: day,
                        time: time,
                        blocks: [existingBlock.block, block]
                    });
                }
                
                // Room conflict - same room, same time, different class
                if (existingBlock.room === room && existingBlock.classGroup !== classGroup) {
                    conflicts.push({
                        type: 'room',
                        room: room,
                        day: day,
                        time: time,
                        blocks: [existingBlock.block, block]
                    });
                }
                
                // Class conflict - same class, same time, different subject
                if (existingBlock.classGroup === classGroup) {
                    conflicts.push({
                        type: 'class',
                        classGroup: classGroup,
                        day: day,
                        time: time,
                        blocks: [existingBlock.block, block]
                    });
                }
            });
            
            timeSlots[key].push({
                block: block,
                teacher: teacher,
                room: room,
                classGroup: classGroup
            });
        });
        
        // Display conflicts if any
        if (conflicts.length > 0) {
            displayConflicts(conflicts);
        } else {
            hideConflicts();
        }
    }
    
    function displayConflicts(conflictsList) {
        let conflictContainer = document.getElementById('conflict-container');
        
        if (!conflictContainer) {
            conflictContainer = document.createElement('div');
            conflictContainer.id = 'conflict-container';
            conflictContainer.className = 'conflict-container';
            document.querySelector('.timetable-container').prepend(conflictContainer);
        }
        
        let conflictHTML = '<h3><i class="fas fa-exclamation-triangle"></i> Timetable Conflicts Detected</h3><ul>';
        
        conflictsList.forEach((conflict, index) => {
            let message = '';
            switch(conflict.type) {
                case 'teacher':
                    message = `<span class="conflict-icon teacher-conflict">👨‍🏫</span> <strong>Teacher conflict:</strong> ${conflict.teacher} is scheduled in multiple classes at ${conflict.day}, ${conflict.time}`;
                    break;
                case 'room':
                    message = `<span class="conflict-icon room-conflict">🚪</span> <strong>Room conflict:</strong> ${conflict.room} is double-booked at ${conflict.day}, ${conflict.time}`;
                    break;
                case 'class':
                    message = `<span class="conflict-icon class-conflict">👥</span> <strong>Class conflict:</strong> ${conflict.classGroup} has multiple subjects at ${conflict.day}, ${conflict.time}`;
                    break;
            }
            
            // Add buttons to highlight conflicting blocks
            conflictHTML += `<li class="conflict-item">
                ${message}
                <button class="btn highlight-conflict" data-conflict-index="${index}">Highlight</button>
                <button class="btn resolve-conflict" data-conflict-index="${index}">Resolve</button>
            </li>`;
            
            // Highlight conflicting blocks
            conflict.blocks.forEach(block => {
                block.classList.add('conflict');
                block.classList.add(`conflict-type-${conflict.type}`);
            });
        });
        
        conflictHTML += '</ul>';
        conflictContainer.innerHTML = conflictHTML;
        
        // Add event listeners for the highlight and resolve buttons
        document.querySelectorAll('.highlight-conflict').forEach(button => {
            button.addEventListener('click', function() {
                const index = this.dataset.conflictIndex;
                highlightConflict(conflicts[index]);
            });
        });
        
        document.querySelectorAll('.resolve-conflict').forEach(button => {
            button.addEventListener('click', function() {
                const index = this.dataset.conflictIndex;
                showResolutionModal(conflicts[index]);
            });
        });
    }
    
    function hideConflicts() {
        const conflictContainer = document.getElementById('conflict-container');
        if (conflictContainer) {
            conflictContainer.innerHTML = '';
            conflictContainer.style.display = 'none';
        }
        
        // Remove conflict highlighting
        document.querySelectorAll('.conflict').forEach(el => {
            el.classList.remove('conflict');
            el.classList.remove('conflict-type-teacher');
            el.classList.remove('conflict-type-room');
            el.classList.remove('conflict-type-class');
        });
    }
    
    function highlightConflict(conflict) {
        // First remove any previous highlighting
        document.querySelectorAll('.highlighted-conflict').forEach(el => {
            el.classList.remove('highlighted-conflict');
        });
        
        // Then highlight the current conflict
        conflict.blocks.forEach(block => {
            block.classList.add('highlighted-conflict');
            
            // Smooth scroll to the first conflicting block
            if (block === conflict.blocks[0]) {
                block.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }
    
    function showResolutionModal(conflict) {
        // Create modal for resolving the conflict
        let modal = document.getElementById('conflict-resolution-modal');
        
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'conflict-resolution-modal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }
        
        // Create modal content based on conflict type
        let modalHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h2>Resolve ${conflict.type.charAt(0).toUpperCase() + conflict.type.slice(1)} Conflict</h2>
                <p>Select which item to move:</p>
                <div class="resolution-options">
        `;
        
        // Add options for each conflicting block
        conflict.blocks.forEach((block, index) => {
            const subject = block.dataset.subject;
            const teacher = block.dataset.teacher;
            const classGroup = block.dataset.classGroup;
            const room = block.dataset.room;
            
            modalHTML += `
                <div class="resolution-option">
                    <input type="radio" name="conflict-resolve" id="resolve-option-${index}" value="${index}" ${index === 0 ? 'checked' : ''}>
                    <label for="resolve-option-${index}">
                        <div class="option-details">
                            <div class="subject">${subject}</div>
                            <div class="details">
                                <span class="teacher">${teacher}</span> | 
                                <span class="class">${classGroup}</span> | 
                                <span class="room">Room ${room}</span>
                            </div>
                        </div>
                    </label>
                </div>
            `;
        });
        
        // Add available time slots
        modalHTML += `
                </div>
                <div class="move-to-section">
                    <h3>Move to:</h3>
                    <div class="available-slots">
                        <select id="available-days">
                            <option value="Monday">Monday</option>
                            <option value="Tuesday">Tuesday</option>
                            <option value="Wednesday">Wednesday</option>
                            <option value="Thursday">Thursday</option>
                            <option value="Friday">Friday</option>
                        </select>
                        <select id="available-times">
        `;
        
        // Get all time slots from the timetable
        const timeSlots = new Set();
        timetableCells.forEach(cell => {
            if (cell.dataset.time) {
                timeSlots.add(cell.dataset.time);
            }
        });
        
        // Add time options
        Array.from(timeSlots).sort().forEach(time => {
            modalHTML += `<option value="${time}">${time}</option>`;
        });
        
        modalHTML += `
                        </select>
                    </div>
                </div>
                <div class="modal-actions">
                    <button id="cancel-resolution" class="btn secondary-btn">Cancel</button>
                    <button id="apply-resolution" class="btn primary-btn">Apply Change</button>
                </div>
            </div>
        `;
        
        modal.innerHTML = modalHTML;
        modal.style.display = 'block';
        
        // Add event listeners
        modal.querySelector('.close').addEventListener('click', () => {
            modal.style.display = 'none';
        });
        
        modal.querySelector('#cancel-resolution').addEventListener('click', () => {
            modal.style.display = 'none';
        });
        
        modal.querySelector('#apply-resolution').addEventListener('click', () => {
            const selectedBlockIndex = parseInt(document.querySelector('input[name="conflict-resolve"]:checked').value);
            const selectedBlock = conflict.blocks[selectedBlockIndex];
            const newDay = document.getElementById('available-days').value;
            const newTime = document.getElementById('available-times').value;
            
            // Find the target cell
            const targetCell = findCellByDayAndTime(newDay, newTime);
            if (targetCell) {
                // If target cell already has content, we need to handle that
                if (targetCell.querySelector('.subject-block') && targetCell.querySelector('.subject-block') !== selectedBlock) {
                    if (confirm('Target slot already has a class. Do you want to swap them?')) {
                        // Swap the blocks
                        const targetBlock = targetCell.querySelector('.subject-block');
                        const sourceCell = selectedBlock.parentElement;
                        
                        targetCell.appendChild(selectedBlock);
                        sourceCell.appendChild(targetBlock);
                    }
                } else {
                    // Just move the block
                    targetCell.appendChild(selectedBlock);
                }
                
                // Check for new conflicts
                checkForConflicts();
                
                // Save changes
                saveChanges(selectedBlock, targetCell);
            }
            
            modal.style.display = 'none';
        });
    }
    
    function findCellByDayAndTime(day, time) {
        return Array.from(timetableCells).find(cell => 
            cell.dataset.day === day && cell.dataset.time === time
        );
    }
    
    function saveChanges(block, cell) {
        // Get the data
        const classGroup = block.dataset.classGroup;
        const subject = block.dataset.subject;
        const teacher = block.dataset.teacher;
        const room = block.dataset.room;
        const day = cell.dataset.day;
        const timeSlot = cell.dataset.time;
        
        // Create the data to send
        const data = {
            class_group: classGroup,
            subject: subject,
            teacher: teacher,
            room: room,
            day: day,
            time_slot: timeSlot,
            original_day: block.dataset.originalDay,
            original_time: block.dataset.originalTime
        };
        
        // Update the original position data
        block.dataset.originalDay = day;
        block.dataset.originalTime = timeSlot;
        
        // Send to server
        fetch('/update_timetable_slot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Show success notification
                showNotification('Changes saved successfully', 'success');
            } else {
                // Show error notification
                showNotification('Error saving changes: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error saving changes', 'error');
        });
    }
    
    function getCsrfToken() {
        // Get CSRF token from meta tag
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }
    
    function showConflict(block1, block2) {
        // Show visual indication of conflict during drag
        block1.classList.add('conflict-during-drag');
        block2.classList.add('conflict-during-drag');
        
        // Remove after animation
        setTimeout(() => {
            block1.classList.remove('conflict-during-drag');
            block2.classList.remove('conflict-during-drag');
        }, 1000);
    }
    
    function showNotification(message, type) {
        let notification = document.getElementById('notification');
        
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'notification';
            document.body.appendChild(notification);
        }
        
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.display = 'block';
        
        // Auto hide after 3 seconds
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }
}
