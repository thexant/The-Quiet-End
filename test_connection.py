#!/usr/bin/env python3
"""
Simple test script to verify PostgreSQL connection works
"""

import sys
from database import Database

def test_connection():
    try:
        print("🧪 Testing PostgreSQL connection...")
        db = Database()
        
        # Test basic connection
        result = db.execute_read_query("SELECT 1 as test", fetch='one')
        if result and result['test'] == 1:
            print("✅ Basic connection test passed")
        else:
            print("❌ Basic connection test failed")
            return False
            
        # Test table listing
        tables = db.execute_read_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """, fetch='all')
        
        print(f"✅ Found {len(tables)} tables in database")
        
        # Test PostgreSQL SERIAL syntax
        try:
            db.execute_query("""
                CREATE TABLE IF NOT EXISTS test_conversion (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            print("✅ SQL syntax test passed (PostgreSQL SERIAL)")
            
            # Clean up test table
            db.execute_query("DROP TABLE IF EXISTS test_conversion")
            
        except Exception as e:
            print(f"❌ SQL syntax test failed: {e}")
            return False
            
        print("🎉 All tests passed! PostgreSQL is ready for the bot.")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    finally:
        try:
            db.cleanup()
        except:
            pass

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)