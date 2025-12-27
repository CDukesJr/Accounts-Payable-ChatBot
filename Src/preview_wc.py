import csv

CSV_FILE = "APAgingDetail - WC - 12.15.25.csv"

try:
    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        print("=== WC FILE ===")
        print("Column Names:", reader.fieldnames)
        print("\nFirst 2 rows:")
        for i, row in enumerate(reader):
            if i >= 2:
                break
            for key, value in row.items():
                print(f"  {key}: {value}")
            print()
except Exception as e:
    print(f"Error: {e}")
