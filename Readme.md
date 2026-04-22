## Description
This is a web-based Task Management System built using FastAPI and Firebase. The application allows users to create task boards, manage tasks, assign users, and track progress with role-based access control.

---

## Features Implemented

### Group 1 Tasks (20%)
- Firebase-based authentication (login/logout) implemented as required
- Firestore collections:
  - Users
  - Task Boards
  - Tasks  
- Relationships:
  - A user can have multiple task boards  
  - A task board can have multiple tasks  
  - A task can be assigned to multiple users  
- Users can create task boards (visible only to the creator)
- Users can open and view individual task boards

---

### Group 2 Tasks (40%)
- Board owner can add users to a task board
- Added users gain access to the board
- Users can add tasks with:
  - Title
  - Due date
  - Completion checkbox
- Tasks are incomplete by default
- Task board list includes shared boards
- Task completion:
  - Checkbox marks task complete
  - Completion date and time is stored and displayed

---

### Group 3 Tasks (60%)
- Board members can:
  - Edit tasks
  - Delete tasks
- Board owner can:
  - Rename the board
  - Remove users from the board
- When a user is removed:
  - Their tasks become unassigned
  - Tasks are highlighted in red
  - User loses access to the board
- Board list shows Owner/Shared indicator

---

### Group 4 Tasks (80%)
- Reassigning a task removes red highlight
- Task counters:
  - Active tasks
  - Completed tasks
  - Total tasks
- Board deletion:
  - Only by owner
  - Only if:
    - No tasks exist
    - No shared users exist
- UI is clean, simple, and functional

---

## Bug Prevention
- Duplicate task names prevented
- Non-owners cannot:
  - Rename boards
  - Remove users
  - Delete boards
- Boards cannot be deleted if:
  - Tasks exist
  - Shared users exist

---

## Tech Stack
- Backend: FastAPI (Python)
- Frontend: HTML, CSS, JavaScript
- Authentication: Firebase Authentication
- Database: Firestore (NoSQL)

---

## Setup Instructions

### 1. Create Firebase Project
- Enable Email/Password Authentication
- Create Firestore Database

---

### 2. Replace Firebase Config (Frontend)
Update: `static/firebase-config.js`  
Add your Firebase project configuration.

---

### 3. Replace Firebase Admin Credentials (Backend)
Replace: `firebase-credentials.json`  
With your own Firebase Admin SDK key. Do not share this file publicly.

---

### 4. Run the Application
If uvicorn is not installed:
pip install uvicorn 
Start the server:
uvicorn main:app --reload --port 8002
Open in browser:
http://127.0.0.1:8002 

## Project Structure
The following tree outlines the organization of the project files.

```text
task-management-system/
│
├── static/                  # Frontend assets
│   ├── firebase-config.js   # Firebase configuration settings
│   ├── firebase-login.js    # Authentication logic
│   └── styles.css           # Custom application styling
│
├── templates/               # HTML templates for FastAPI
│   └── index.html           # Main application interface
│
├── firebase-credentials.json # Service account key (requires manual setup)
├── main.py                  # FastAPI server and backend logic
└── README.md                # Project documentation