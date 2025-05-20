# Database Setup for Exam Platform

This file provides instructions for setting up the database for the Exam Platform application.

## Prerequisites

- MySQL server installed
- MySQL client or command-line tool

## Setup Instructions

1. Open a command prompt (CMD) or PowerShell
2. Navigate to the directory containing the SQL file:
   ```
   cd c:\Users\Ivermectin\Music\Tanush\Try 3
   ```

3. Connect to MySQL and import the database:

   Using MySQL command-line client:
   ```
   mysql -u root -p < exam_platform.sql
   ```

   If you have a specific MySQL password, use:
   ```
   mysql -u root -p < exam_platform.sql
   ```
   (You'll be prompted to enter your password)

4. Alternatively, you can import using MySQL Workbench or another GUI tool:
   - Open MySQL Workbench
   - Connect to your MySQL server
   - Go to Server → Data Import
   - Choose "Import from Self-Contained File" and select the exam_platform.sql file
   - Click "Start Import"

5. Verify the database was created successfully:
   ```
   mysql -u root -p
   ```
   
   Once logged in:
   ```sql
   USE exam_platform;
   SHOW TABLES;
   ```

## Database Structure

The database includes the following tables:

- **users**: Stores user information (admin, teachers, students)
- **exams**: Contains exam details created by teachers
- **questions**: Stores questions for each exam
- **question_options**: Contains options for multiple-choice questions
- **exam_attempts**: Tracks student attempts at exams
- **answers**: Stores student answers to exam questions
- **exam_reviews**: Contains student reviews of exams
- **notifications**: Stores notifications for users

## Sample Data

The SQL file includes sample data with:
- 1 admin user, 2 teachers, and 3 students
- 5 exams with questions (4 published, 1 unpublished)
- Sample exam attempts, answers, reviews, and notifications

## Access Information

Default user credentials (username/password):
- Admin: admin@example.com / password123
- Teachers: teacher1@example.com / password123, teacher2@example.com / password123
- Students: student1@example.com / password123, student2@example.com / password123, student3@example.com / password123
