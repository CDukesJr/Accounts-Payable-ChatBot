import json

# Create a training dataset with Q&A pairs or instruction format
def prepare_training_data():
    with open("cleaned_emails.jsonl", "r", encoding="utf-8") as infile, \
         open("training_data.jsonl", "w", encoding="utf-8") as outfile:
        
        count = 0
        for line in infile:
            record = json.loads(line)
            
            # Format for instruction-based training
            training_example = {
                "instruction": "Answer this accounts payable question based on email history:",
                "input": record.get("subject", ""),
                "output": record.get("clean_text", ""),
                "metadata": {
                    "sender": record.get("sender", ""),
                    "date": record.get("date", "")
                }
            }
            
            outfile.write(json.dumps(training_example) + "\n")
            count += 1
        
        print(f"Successfully processed {count} emails")
        print("Training data saved as: training_data.jsonl")

if __name__ == "__main__":
    prepare_training_data()
