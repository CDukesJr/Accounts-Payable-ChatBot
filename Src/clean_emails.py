import json
import re

INPUT_FILE = "outlook_emails.jsonl"
OUTPUT_FILE = "cleaned_emails.jsonl"

def clean_text(text):
    if not text:
        return ""

    # Remove Outlook reply markers
    text = re.sub(r"On .* wrote:", "", text, flags=re.IGNORECASE)

    # Remove signature blocks
    text = re.sub(r"(?s)--\s*.+$", "", text)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# Try multiple encodings to handle the file properly
encodings_to_try = ['utf-8', 'utf-16', 'latin-1', 'cp1252']

for encoding in encodings_to_try:
    try:
        with open(INPUT_FILE, "r", encoding=encoding) as infile, \
             open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
            
            print(f"Successfully opened file with {encoding} encoding")
            
            for line in infile:
                try:
                    record = json.loads(line)
                    
                    # Clean the text body
                    record["clean_text"] = clean_text(record.get("text", ""))
                    
                    outfile.write(json.dumps(record, ensure_ascii=False) + "\n")
                except json.JSONDecodeError as e:
                    print(f"Skipping invalid JSON line: {e}")
                    continue
            
            print("Cleaning complete. File saved as:", OUTPUT_FILE)
            break  # Exit loop if successful
            
    except UnicodeDecodeError:
        print(f"Failed with {encoding} encoding, trying next...")
        continue
    except FileNotFoundError:
        print(f"Error: Could not find file '{INPUT_FILE}'")
        print("Make sure the file exists in C:\\APchatbot\\")
        break
else:
    print("Error: Could not read file with any supported encoding")



