import csv
from datetime import datetime

CSV_ACC = "APAgingDetail - ACC - 12.15.25.csv"
CSV_WC = "APAgingDetail - WC - 12.15.25.csv"

def parse_date(date_str):
    """Parse date string to datetime object"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y")
    except:
        return None

def aging_priority(aging_str):
    """Convert aging bucket to numeric priority (higher = older)"""
    aging_map = {"Current": 0, "30": 1, "60": 2, "90": 3}
    return aging_map.get(aging_str.strip(), -1)

def load_all_invoices():
    """Load all invoices from both CSV files"""
    invoices = []
    
    for csv_file in [CSV_ACC, CSV_WC]:
        try:
            with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    invoices.append(row)
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    return invoices

def vendor_oldest_invoices():
    """Find which vendor has the oldest aged invoices"""
    invoices = load_all_invoices()
    
    # Group by vendor and find oldest aging bucket
    vendor_aging = {}
    
    for inv in invoices:
        vendor = inv.get("Vendor", "Unknown").strip()
        aging = inv.get("Aging", "Current").strip()
        due_date_str = inv.get("Due Date", "").strip()
        invoice_num = inv.get("Invoice #", "").strip()
        balance = inv.get("Open Balance", "$0").strip()
        
        if vendor not in vendor_aging:
            vendor_aging[vendor] = {
                "max_aging_priority": -1,
                "aging_bucket": "N/A",
                "count": 0,
                "total_balance": 0,
                "sample_invoice": None,
                "due_date": None
            }
        
        aging_priority_val = aging_priority(aging)
        
        # Update if this is older
        if aging_priority_val > vendor_aging[vendor]["max_aging_priority"]:
            vendor_aging[vendor]["max_aging_priority"] = aging_priority_val
            vendor_aging[vendor]["aging_bucket"] = aging
            vendor_aging[vendor]["sample_invoice"] = invoice_num
            vendor_aging[vendor]["due_date"] = due_date_str
        
        vendor_aging[vendor]["count"] += 1
        
        # Parse balance (remove $ and convert)
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            vendor_aging[vendor]["total_balance"] += balance_val
        except:
            pass
    
    # Sort by aging priority (descending = oldest first)
    sorted_vendors = sorted(
        vendor_aging.items(),
        key=lambda x: x[1]["max_aging_priority"],
        reverse=True
    )
    
    return sorted_vendors

def show_vendor_aging_summary():
    """Display vendor aging summary"""
    vendors = vendor_oldest_invoices()
    
    aging_map_reverse = {0: "Current", 1: "30 days", 2: "60 days", 3: "90+ days"}
    
    print("\n" + "="*80)
    print("VENDOR AGING SUMMARY - OLDEST INVOICES FIRST")
    print("="*80)
    
    for vendor, data in vendors[:15]:  # Show top 15
        aging_label = aging_map_reverse.get(data["max_aging_priority"], "Unknown")
        print(f"\nVendor: {vendor}")
        print(f"  Oldest Aging: {aging_label} (Sample Invoice: {data['sample_invoice']})")
        print(f"  Due Date: {data['due_date']}")
        print(f"  Total Open Balance: ${data['total_balance']:,.2f}")
        print(f"  Number of Invoices: {data['count']}")

if __name__ == "__main__":
    show_vendor_aging_summary()
