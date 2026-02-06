import os
import psycopg2

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    print("   Please set it or enter manually:")
    DATABASE_URL = input("Database URL: ").strip()

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'overview_history'
        )
    """)
    table_exists = cursor.fetchone()[0]
    
    if not table_exists:
        print("⚠️ Table 'overview_history' does not exist yet")
        print("   It will be created on first scrape")
        cursor.close()
        conn.close()
        exit(0)
    
    # Check if placed_gmv column exists
    cursor.execute("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'overview_history'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    
    print("\n📊 Current schema of 'overview_history':")
    print("-" * 60)
    has_gmv = False
    for col in columns:
        col_name, col_type, col_default = col
        print(f"  {col_name:<20} {col_type:<15} (default: {col_default})")
        if col_name == 'placed_gmv':
            has_gmv = True
    
    if not has_gmv:
        print("\n❌ Column 'placed_gmv' NOT FOUND!")
        print("   Run the scraper once to add this column")
    else:
        print("\n✅ Column 'placed_gmv' exists!")
    
    # Check data
    cursor.execute("SELECT COUNT(*) FROM overview_history")
    total_count = cursor.fetchone()[0]
    
    if has_gmv:
        cursor.execute("SELECT COUNT(*) FROM overview_history WHERE placed_gmv > 0")
        gmv_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM overview_history WHERE placed_gmv = 0")
        zero_count = cursor.fetchone()[0]
        
        print(f"\n📈 Data summary:")
        print(f"  Total records: {total_count}")
        print(f"  Records with GMV > 0: {gmv_count}")
        print(f"  Records with GMV = 0: {zero_count}")
        
        if gmv_count > 0:
            # Show sample data
            cursor.execute("""
                SELECT session_id, session_title, placed_gmv, views, pcu, archived_at::date
                FROM overview_history 
                WHERE placed_gmv > 0
                ORDER BY archived_at DESC
                LIMIT 5
            """)
            print(f"\n📋 Sample records with GMV (latest 5):")
            print("-" * 80)
            for row in cursor.fetchall():
                sid, title, gmv, views, pcu, date = row
                print(f"  {date} | {sid} | GMV: {gmv:,} | Views: {views} | PCU: {pcu}")
        
        if zero_count > 0 and zero_count == total_count:
            print("\n⚠️ All records have GMV = 0")
            print("   This might be old data before GMV column was added")
            print("   New scrapes will have actual GMV values")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Check complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
