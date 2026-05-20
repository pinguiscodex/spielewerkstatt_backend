-- Run this once before switching an existing database to the Django app.
-- It is idempotent for MySQL 8+/MariaDB versions that support IF NOT EXISTS.

ALTER TABLE developers ADD COLUMN IF NOT EXISTS is_admin TINYINT(1) DEFAULT 0;
UPDATE developers SET is_admin = 1 WHERE username = 'Pengu';

ALTER TABLE games ADD COLUMN IF NOT EXISTS changelog TEXT NULL;

ALTER TABLE data_folder_files MODIFY COLUMN folder_id INT NULL;

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    location VARCHAR(255),
    creator_id INT NOT NULL,
    max_attendees INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES developers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_attendees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES developers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_event_user (event_id, user_id)
);
