-- SQL script to update all user passwords to a single hash value
-- This script is for testing/development purposes only

-- Description: Updates all user passwords to the same hash value
-- Hash value corresponds to a known password for testing
-- Generated on: May 19, 2025

BEGIN TRANSACTION;

-- Update all password hashes in the users table
UPDATE users 
SET password_hash = 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2';

-- Confirm how many records were updated (outputs the count)
SELECT COUNT(*) as "Passwords Updated" FROM users;

-- Optional: You can display the first few updated users to verify
-- SELECT id, username, email, password_hash FROM users LIMIT 5;

COMMIT;

-- Note: After running this script, all users will have the same password
-- This should only be used in testing/development environments
