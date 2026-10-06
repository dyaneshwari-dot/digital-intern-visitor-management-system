# Digital Intern & Visitor Management System

Project for Jeevan Ankur Trust, Chembur.

## Technology
- HTML
- CSS
- JavaScript
- Python Flask
- MySQL

## Main features
1. Home page
2. New user registration
3. Existing user login
4. User dashboard/profile
5. Time-slot booking
6. Green = available, Red = booked
7. Booking confirmation
8. Check-in/check-out
9. Visit history
10. Admin dashboard
11. Digital records
12. Mobile-friendly layout

## Setup

### 1. Install Python
Install Python 3.10+ and make sure `python --version` works.

### 2. Start MySQL
If using XAMPP, open XAMPP and start MySQL.

### 3. Create database
Open phpMyAdmin and run:

CREATE DATABASE jeevan_ankur_db;

The Flask app creates the tables automatically.

### 4. Install packages
Open terminal in this project folder:

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

### 5. Check MySQL settings
Open `app.py` and edit DB_CONFIG if required:

host = localhost
user = root
password = your MySQL password
database = jeevan_ankur_db

### 6. Run
python app.py

Open:
http://127.0.0.1:5000

## Admin demo login
Username: admin
Password: admin123

For a real deployment, change the secret key and admin password.
