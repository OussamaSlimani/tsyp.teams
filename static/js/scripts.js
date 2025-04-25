document.addEventListener('DOMContentLoaded', function () {
    
    // sidebar toggle
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const menuToggle = document.getElementById('menuToggle');
    const menuIcon = document.getElementById('menuIcon');

    window.addEventListener('DOMContentLoaded', function () {
        if (window.innerWidth < 992) {
            sidebar.classList.add('collapsed');
            menuIcon.classList.remove('rotated');
        }
    });

    // Toggle sidebar
    menuToggle.addEventListener('click', function () {
        sidebar.classList.toggle('collapsed');
        menuIcon.classList.toggle('rotated');
    });

    // Get current team from URL
    const pathArray = window.location.pathname.split('/');
    const currentTeam = pathArray[pathArray.length - 1];

    // Task modal elements
    const taskModal = document.getElementById('taskModal');
    const taskModalLabel = document.getElementById('taskModalLabel');
    const taskForm = document.getElementById('taskForm');
    const taskIdInput = document.getElementById('taskId');
    const saveTaskBtn = document.getElementById('saveTask');
    const taskNameInput = document.getElementById('taskName');
    const taskStatusInput = document.getElementById('taskStatus');

    // Function to check if required fields are filled
    function checkRequiredFields() {
        const nameFilled = taskNameInput.value.trim() !== '';
        const statusFilled = taskStatusInput.value !== '';
        saveTaskBtn.disabled = !(nameFilled && statusFilled);
    }

    // Add event listeners to required fields
    taskNameInput.addEventListener('input', checkRequiredFields);
    taskStatusInput.addEventListener('change', checkRequiredFields);

    // Edit task buttons
    const editButtons = document.querySelectorAll('.edit-task');
    editButtons.forEach(button => {
        button.addEventListener('click', function () {
            const taskId = this.getAttribute('data-task-id');
            const taskName = this.getAttribute('data-task-name');
            const taskDescription = this.getAttribute('data-task-description');
            const taskDueDate = this.getAttribute('data-task-due-date');
            const taskStatus = this.getAttribute('data-task-status');
            const taskAssignees = this.getAttribute('data-task-assignees').split(',');

            // Convert timestamp to date string
            let dueDate = '';
            if (taskDueDate) {
                const date = new Date(parseInt(taskDueDate));
                dueDate = date.toISOString().split('T')[0];
            }

            // Populate form
            taskModalLabel.textContent = 'Edit Task';
            taskIdInput.value = taskId;
            document.getElementById('taskName').value = taskName;
            document.getElementById('taskDescription').value = taskDescription;
            document.getElementById('taskDueDate').value = dueDate;
            document.getElementById('taskStatus').value = taskStatus;

            // Clear all checkboxes first
            document.querySelectorAll('.assignee-checkboxes input[type="checkbox"]').forEach(checkbox => {
                checkbox.checked = false;
            });

            // Check the assigned members
            taskAssignees.forEach(assignee => {
                const checkbox = document.querySelector(`.assignee-checkboxes input[value="${assignee}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });

            // Enable save button since we're editing an existing task
            saveTaskBtn.disabled = false;

            // Show modal
            const modal = new bootstrap.Modal(taskModal);
            modal.show();
        });
    });

    // Delete task buttons
    const deleteButtons = document.querySelectorAll('.delete-task');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function () {
            const taskId = this.getAttribute('data-task-id');

            Swal.fire({
                title: 'Are you sure?',
                text: "You won't be able to revert this!",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Yes, delete it!',
                cancelButtonText: 'Cancel',
                customClass: {
                    popup: 'swal-sm',
                    title: 'swal-title-sm',
                    htmlContainer: 'swal-text-sm',
                    confirmButton: 'btn btn-sm btn-danger m-2',
                    cancelButton: 'btn btn-sm btn-primary m-2'
                },
                buttonsStyling: false
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch(`/api/tasks/${currentTeam}/${taskId}`, {
                        method: 'DELETE',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            window.location.reload();
                        } else {
                            Swal.fire(
                                'Oops!',
                                'Something went wrong while deleting.',
                                'error'
                            );
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        Swal.fire(
                            'Error!',
                            'Failed to delete the task.',
                            'error'
                        );
                    });
                }
            });
        });
    });

    // Save task button
    saveTaskBtn.addEventListener('click', function () {
        const formData = new FormData(taskForm);
        const taskData = {
            name: formData.get('name'),
            description: formData.get('description'),
            due_date: new Date(formData.get('due_date')).getTime().toString(),
            status: formData.get('status'),
            assignees: Array.from(document.querySelectorAll('.assignee-checkboxes input[type="checkbox"]:checked'))
                .map(checkbox => checkbox.value)
        };

        const taskId = taskIdInput.value;
        const method = taskId ? 'PUT' : 'POST';
        const url = taskId ? `/api/tasks/${currentTeam}/${taskId}` : `/api/tasks/${currentTeam}`;

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });

    // Reset form when modal is closed
    taskModal.addEventListener('hidden.bs.modal', function () {
        taskForm.reset();
        taskIdInput.value = '';
        taskModalLabel.textContent = 'Add New Task';
        saveTaskBtn.disabled = true; // Disable save button when modal is closed
    });

    // Handle resource form submission
    document.getElementById('resourceForm').addEventListener('submit', function (e) {
        e.preventDefault();

        const team = document.querySelector('.sidebar .nav-link.active').textContent.trim().toLowerCase();
        const resourceId = document.getElementById('resourceId').value;
        const name = document.getElementById('resourceName').value;
        const url = document.getElementById('resourceUrl').value;

        const method = resourceId ? 'PUT' : 'POST';
        const urlPath = resourceId ?
            `/api/resources/${team}/${resourceId}` :
            `/api/resources/${team}`;

        fetch(urlPath, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                url: url
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            })
            .catch(error => console.error('Error:', error));
    });

    // Handle edit resource button clicks
    document.querySelectorAll('.edit-resource').forEach(button => {
        button.addEventListener('click', function () {
            const resourceId = this.getAttribute('data-id');
            const name = this.getAttribute('data-name');
            const url = this.getAttribute('data-url');

            document.getElementById('resourceId').value = resourceId;
            document.getElementById('resourceName').value = name;
            document.getElementById('resourceUrl').value = url;

            // Change modal title
            document.getElementById('addResourceModalLabel').textContent = 'Edit Resource';

            // Show the modal
            var addResourceModal = new bootstrap.Modal(document.getElementById('addResourceModal'));
            addResourceModal.show();
        });
    });

    // Handle delete resource button clicks
    document.querySelectorAll('.delete-resource').forEach(button => {
        button.addEventListener('click', function () {
            if (confirm('Are you sure you want to delete this resource?')) {
                const team = document.querySelector('.sidebar .nav-link.active').textContent.trim().toLowerCase();
                const resourceId = this.getAttribute('data-id');

                fetch(`/api/resources/${team}/${resourceId}`, {
                    method: 'DELETE'
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
        });
    });

    // Reset add resource form when modal is hidden
    document.getElementById('addResourceModal').addEventListener('hidden.bs.modal', function () {
        document.getElementById('resourceForm').reset();
        document.getElementById('resourceId').value = '';
        document.getElementById('addResourceModalLabel').textContent = 'Add New Resource';
    });
});

function applyFilters() {
    const status = document.getElementById('statusFilter').value;
    const assignee = document.getElementById('assigneeFilter').value;
    const dateFilter = document.getElementById('dateFilter').value;

    const validStatuses = ['ideas', 'to do', 'in progress', 'on stand by', 'to validate', 'done'];

    const queryParams = new URLSearchParams();
    if (status) queryParams.append('status', status);
    if (assignee) queryParams.append('assignee', assignee);
    if (dateFilter) queryParams.append('date_filter', dateFilter);

    window.location.search = queryParams.toString();
}