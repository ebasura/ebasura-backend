import pymysql  # type: ignore


class Database:
    def __init__(self, host, user, password, db):
        """Initialize the Database connection."""
        self.host = host
        self.user = user
        self.password = password
        self.db = db

    def connect(self):
        """Create a new database connection."""
        return pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            db=self.db,
            cursorclass=pymysql.cursors.DictCursor
        )

    def execute(self, query, args=None):
        """Execute a query that does not return results (INSERT, UPDATE, DELETE)."""
        try:
            connection = self.connect()
            with connection.cursor() as cursor:
                cursor.execute(query, args)
            connection.commit()
            return True
        except Exception as e:
            print(f"Error: {str(e)}")
            return False
        finally:
            connection.close()

    def fetch(self, query, args=None):
        """Execute a SELECT query and fetch the results."""
        try:
            connection = self.connect()
            with connection.cursor() as cursor:
                cursor.execute(query, args)
                result = cursor.fetchall()
            return result
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
        finally:
            connection.close()

    def fetch_one(self, query, args=None):
        """Execute a SELECT query and fetch a single result."""
        try:
            connection = self.connect()
            with connection.cursor() as cursor:
                cursor.execute(query, args)
                result = cursor.fetchone()
            return result
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
        finally:
            connection.close()

    def update(self, query, args=None):
        """Execute an UPDATE query."""
        return self.execute(query, args)

    def delete(self, query, args=None):
        """Execute a DELETE query."""
        return self.execute(query, args)
