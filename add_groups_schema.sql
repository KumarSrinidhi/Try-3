-- Add groups and group_membership tables
-- First create groups table (note: groups is a reserved word, so we use backticks)
CREATE TABLE IF NOT EXISTS `groups` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    subject VARCHAR(50),
    section VARCHAR(20),
    room VARCHAR(20),
    code VARCHAR(6) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    teacher_id INT NOT NULL,
    archived BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (teacher_id) REFERENCES users(id),
    INDEX idx_teacher (teacher_id),
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create group membership table
CREATE TABLE IF NOT EXISTS group_membership (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (group_id) REFERENCES `groups`(id),
    UNIQUE KEY uk_user_group (user_id, group_id),
    INDEX idx_group_users (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add group_id column to exams table
ALTER TABLE exams ADD COLUMN group_id INT;
ALTER TABLE exams ADD CONSTRAINT fk_exam_group FOREIGN KEY (group_id) REFERENCES `groups`(id);
