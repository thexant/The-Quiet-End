#!/usr/bin/env python3
"""
Quick test to verify the PostgreSQL schema changes work correctly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_postgresql import Database

def test_schema():
    try:
        print("🔄 Testing PostgreSQL schema initialization...")
        
        # This will attempt to initialize the database with the new schema
        db = Database()
        
        print("✅ Schema initialization successful!")
        
        # Test that the pending_robberies table exists
        result = db.execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'pending_robberies' AND table_schema = 'public'",
            fetch='one'
        )
        
        if result:
            print("✅ pending_robberies table exists")
        else:
            print("❌ pending_robberies table not found")
            return False
        
        # Test that shop_items has stock_quantity column
        result = db.execute_query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'shop_items' AND column_name = 'stock_quantity'",
            fetch='one'
        )
        
        if result:
            print("✅ shop_items.stock_quantity column exists")
        else:
            print("❌ shop_items.stock_quantity column not found")
            return False
        
        print("✅ All database schema tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.cleanup()
        except:
            pass

if __name__ == "__main__":
    success = test_schema()
    sys.exit(0 if success else 1)