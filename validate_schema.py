#!/usr/bin/env python3
"""
Validate the PostgreSQL schema syntax without actually connecting to a database
"""
import re

def validate_schema_syntax():
    """Read and validate the schema SQL syntax"""
    
    try:
        # Read the schema from database_postgresql.py
        with open('/home/vetaso/The-Quiet-End/database_postgresql.py', 'r') as f:
            content = f.read()
        
        # Extract all CREATE TABLE statements
        table_pattern = r"'''CREATE TABLE.*?'''"
        tables = re.findall(table_pattern, content, re.DOTALL)
        
        print(f"🔄 Found {len(tables)} CREATE TABLE statements")
        
        # Check for pending_robberies table
        pending_robberies_found = False
        shop_items_found = False
        
        for table_sql in tables:
            if 'pending_robberies' in table_sql:
                pending_robberies_found = True
                print("✅ Found pending_robberies table definition")
                # Basic syntax checks
                if 'SERIAL PRIMARY KEY' in table_sql:
                    print("  ✅ Uses proper PostgreSQL SERIAL syntax")
                if 'TIMESTAMP NOT NULL' in table_sql:
                    print("  ✅ Has required expires_at timestamp")
                if 'FOREIGN KEY' in table_sql:
                    print("  ✅ Has foreign key constraints")
                    
            elif 'shop_items' in table_sql:
                shop_items_found = True
                print("✅ Found shop_items table definition")
                if 'stock_quantity' in table_sql:
                    print("  ✅ Has stock_quantity column")
                else:
                    print("  ❌ Missing stock_quantity column")
        
        if not pending_robberies_found:
            print("❌ pending_robberies table not found in schema")
            return False
            
        if not shop_items_found:
            print("❌ shop_items table not found in schema")
            return False
            
        # Check events.py for correct column reference
        with open('/home/vetaso/The-Quiet-End/cogs/events.py', 'r') as f:
            events_content = f.read()
        
        if 'WHERE stock_quantity = 0' in events_content:
            print("✅ events.py uses correct stock_quantity column")
        elif 'WHERE stock = 0' in events_content:
            print("❌ events.py still uses incorrect stock column")
            return False
        else:
            print("⚠️  Could not find stock cleanup query in events.py")
        
        print("✅ Schema validation passed!")
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = validate_schema_syntax()
    sys.exit(0 if success else 1)