import os
import mysql.connector
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

def update_database():
    # Extract connection details from DATABASE_URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL environment variable not set")
        return

    # Parse DATABASE_URL - format: mysql+mysqlconnector://username:password@host/database
    match = re.match(r'mysql\+mysqlconnector://([^:]+):([^@]+)@([^/]+)/(.+)', db_url)
    if not match:
        print(f"Error: Invalid DATABASE_URL format: {db_url}")
        return

    user, password, host, database = match.groups()
    
    # Setup database configuration
    db_config = {
        'host': host,
        'user': user,
        'password': password,
        'database': database
    }

    try:
        # Create connection
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        cursor = conn.cursor()        # Execute SQL to add groups tables and group_id column
        print("Adding groups tables and column to database...")
        with open('add_groups_schema.sql', 'r') as f:
            sql = f.read()
            # Split at semicolons but ignore those inside comments
            statements = []
            current_statement = ""
            for line in sql.split('\n'):
                line_stripped = line.strip()
                if line_stripped.startswith('--') or not line_stripped:  # Skip comments and empty lines
                    continue
                current_statement += line + "\n"
                if line_stripped.endswith(';'):
                    statements.append(current_statement)
                    current_statement = ""
            
            # Execute each statement separately
            for statement in statements:
                if statement.strip():
                    try:
                        print(f"\nExecuting: {statement.strip()[:60]}...")
                        cursor.execute(statement)
                        conn.commit()
                        print("Success!")
                    except mysql.connector.Error as err:
                        print(f"Error: {err}")
                    
        print("Database update completed.")
        
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")

if __name__ == "__main__":
    update_database()
