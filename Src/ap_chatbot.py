import json
import os
import csv
from datetime import datetime
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

EMAILS_FILE = "cleaned_emails.jsonl"
CSV_ACC = "APAgingDetail - ACC - 12.15.25.csv"
CSV_WC = "APAgingDetail - WC - 12.15.25.csv"

# ============= AGING QUERY FUNCTIONS =============

def aging_priority(aging_str):
    """Convert aging bucket to numeric priority (higher = older)"""
    aging_map = {"Current": 0, "30": 1, "60": 2, "90": 3, "90+": 3}
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
            pass
    
    return invoices

# ============= VENDOR QUERIES =============

def vendor_oldest_invoices():
    """Find which vendor has the oldest aged invoices"""
    invoices = load_all_invoices()
    vendor_aging = {}
    
    for inv in invoices:
        vendor = inv.get("Vendor", "Unknown").strip()
        aging = inv.get("Aging", "Current").strip()
        due_date_str = inv.get("Due Date", "").strip()
        invoice_num = inv.get("Invoice #", "").strip()
        balance = inv.get("Open Balance", "$0").strip()
        payment_status = inv.get("Payment Status", "").strip()
        
        if vendor not in vendor_aging:
            vendor_aging[vendor] = {
                "max_aging_priority": -1,
                "aging_bucket": "N/A",
                "count": 0,
                "total_balance": 0,
                "sample_invoice": None,
                "due_date": None,
                "unpaid_count": 0
            }
        
        aging_priority_val = aging_priority(aging)
        
        if aging_priority_val > vendor_aging[vendor]["max_aging_priority"]:
            vendor_aging[vendor]["max_aging_priority"] = aging_priority_val
            vendor_aging[vendor]["aging_bucket"] = aging
            vendor_aging[vendor]["sample_invoice"] = invoice_num
            vendor_aging[vendor]["due_date"] = due_date_str
        
        vendor_aging[vendor]["count"] += 1
        if payment_status.lower() == "unpaid":
            vendor_aging[vendor]["unpaid_count"] += 1
        
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            vendor_aging[vendor]["total_balance"] += balance_val
        except:
            pass
    
    sorted_vendors = sorted(
        vendor_aging.items(),
        key=lambda x: x[1]["max_aging_priority"],
        reverse=True
    )
    
    return sorted_vendors

def get_vendor_summary_text(limit=10):
    """Get vendor aging summary as text"""
    vendors = vendor_oldest_invoices()
    aging_map_reverse = {0: "Current", 1: "30 days", 2: "60 days", 3: "90+ days"}
    
    lines = ["VENDOR AGING SUMMARY (Oldest First):\n"]
    for vendor, data in vendors[:limit]:
        aging_label = aging_map_reverse.get(data["max_aging_priority"], "Unknown")
        lines.append(
            f"• {vendor}: {aging_label} | Invoice {data['sample_invoice']} | "
            f"Due {data['due_date']} | Balance: ${data['total_balance']:,.2f} | "
            f"Invoices: {data['count']} ({data['unpaid_count']} unpaid)"
        )
    
    return "\n".join(lines)

def get_vendor_invoices(vendor_name):
    """Get all invoices for a specific vendor"""
    invoices = load_all_invoices()
    vendor_invs = [inv for inv in invoices if vendor_name.lower() in inv.get("Vendor", "").lower()]
    
    if not vendor_invs:
        return f"No invoices found for vendor: {vendor_name}"
    
    lines = [f"INVOICES FOR {vendor_name.upper()} ({len(vendor_invs)} total):\n"]
    total = 0
    for inv in vendor_invs:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            balance_val = 0
        
        lines.append(
            f"• {inv.get('Invoice #', '')} | Due {inv.get('Due Date', '')} | "
            f"{inv.get('Aging', '')} days | {balance} | Status: {inv.get('Payment Status', '')}"
        )
    
    lines.append(f"\nTotal Due to {vendor_name}: ${total:,.2f}")
    return "\n".join(lines)

def get_vendor_total(vendor_name):
    """Get total amount due to a vendor"""
    invoices = load_all_invoices()
    vendor_invs = [inv for inv in invoices if vendor_name.lower() in inv.get("Vendor", "").lower()]
    
    total = 0
    unpaid_count = 0
    for inv in vendor_invs:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            pass
        
        if inv.get("Payment Status", "").lower() == "unpaid":
            unpaid_count += 1
    
    if not vendor_invs:
        return f"No invoices found for vendor: {vendor_name}"
    
    return f"Total due to {vendor_name}: ${total:,.2f} ({unpaid_count} unpaid invoices)"

def vendors_with_most_unpaid():
    """Get vendors with most unpaid invoices"""
    invoices = load_all_invoices()
    vendor_unpaid = {}
    
    for inv in invoices:
        if inv.get("Payment Status", "").lower() == "unpaid":
            vendor = inv.get("Vendor", "Unknown").strip()
            if vendor not in vendor_unpaid:
                vendor_unpaid[vendor] = 0
            vendor_unpaid[vendor] += 1
    
    sorted_vendors = sorted(vendor_unpaid.items(), key=lambda x: x[1], reverse=True)
    
    lines = ["VENDORS WITH MOST UNPAID INVOICES:\n"]
    for vendor, count in sorted_vendors[:10]:
        lines.append(f"• {vendor}: {count} unpaid invoices")
    
    return "\n".join(lines)

# ============= STATUS QUERIES =============

def get_by_status(status_type):
    """Get invoices by status (Unassigned, Approved, etc.)"""
    invoices = load_all_invoices()
    filtered = [inv for inv in invoices if status_type.lower() in inv.get("Status", "").lower()]
    
    if not filtered:
        return f"No invoices found with status: {status_type}"
    
    lines = [f"INVOICES WITH STATUS '{status_type.upper()}' ({len(filtered)} total):\n"]
    total = 0
    for inv in filtered:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            balance_val = 0
        
        lines.append(
            f"• {inv.get('Invoice #', '')} | {inv.get('Vendor', '')} | "
            f"{balance} | {inv.get('Aging', '')} days | {inv.get('Entity', '')}"
        )
    
    lines.append(f"\nTotal: ${total:,.2f}")
    return "\n".join(lines)

def get_by_payment_status(payment_status):
    """Get invoices by payment status (Paid, Unpaid)"""
    invoices = load_all_invoices()
    filtered = [inv for inv in invoices if payment_status.lower() in inv.get("Payment Status", "").lower()]
    
    if not filtered:
        return f"No invoices found with payment status: {payment_status}"
    
    lines = [f"INVOICES - PAYMENT STATUS '{payment_status.upper()}' ({len(filtered)} total):\n"]
    total = 0
    for inv in filtered[:20]:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            balance_val = 0
        
        lines.append(
            f"• {inv.get('Invoice #', '')} | {inv.get('Vendor', '')} | "
            f"Due {inv.get('Due Date', '')} | {balance}"
        )
    
    if len(filtered) > 20:
        lines.append(f"\n... and {len(filtered) - 20} more")
    
    lines.append(f"\nTotal: ${total:,.2f}")
    return "\n".join(lines)

# ============= ENTITY QUERIES =============

def entity_comparison():
    """Compare ACC vs WC aging"""
    invoices = load_all_invoices()
    entity_data = {"ACC": {"Current": 0, "30": 0, "60": 0, "90": 0}, 
                   "WC": {"Current": 0, "30": 0, "60": 0, "90": 0}}
    
    for inv in invoices:
        entity = inv.get("Entity", "").strip()
        aging = inv.get("Aging", "").strip()
        balance = inv.get("Open Balance", "$0").strip()
        
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            if entity in entity_data and aging in entity_data[entity]:
                entity_data[entity][aging] += balance_val
        except:
            pass
    
    lines = ["AGING COMPARISON: ACC vs WC\n"]
    lines.append("ACC Entity:")
    for bucket in ["Current", "30", "60", "90"]:
        lines.append(f"  {bucket} days: ${entity_data['ACC'][bucket]:,.2f}")
    
    lines.append("\nWC Entity:")
    for bucket in ["Current", "30", "60", "90"]:
        lines.append(f"  {bucket} days: ${entity_data['WC'][bucket]:,.2f}")
    
    return "\n".join(lines)

def get_entity_total(entity_name):
    """Get total open balance per entity"""
    invoices = load_all_invoices()
    entity_invs = [inv for inv in invoices if entity_name.upper() in inv.get("Entity", "").upper()]
    
    if not entity_invs:
        return f"No invoices found for entity: {entity_name}"
    
    total = 0
    for inv in entity_invs:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            pass
    
    return f"Total open balance for {entity_name}: ${total:,.2f} ({len(entity_invs)} invoices)"

# ============= DATE QUERIES =============

def invoices_due_soon(days=7):
    """Get invoices due in next N days"""
    invoices = load_all_invoices()
    due_soon = []
    
    today = datetime.now()
    
    for inv in invoices:
        due_date_str = inv.get("Due Date", "").strip()
        try:
            due_date = datetime.strptime(due_date_str, "%m/%d/%Y")
            days_until = (due_date - today).days
            if 0 <= days_until <= days and inv.get("Payment Status", "").lower() == "unpaid":
                due_soon.append((inv, days_until))
        except:
            pass
    
    if not due_soon:
        return f"No invoices due in the next {days} days"
    
    due_soon.sort(key=lambda x: x[1])
    
    lines = [f"INVOICES DUE IN NEXT {days} DAYS:\n"]
    total = 0
    for inv, days_left in due_soon:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            total += balance_val
        except:
            balance_val = 0
        
        lines.append(
            f"• {inv.get('Invoice #', '')} | {inv.get('Vendor', '')} | "
            f"Due {inv.get('Due Date', '')} ({days_left} days) | {balance}"
        )
    
    lines.append(f"\nTotal Due Soon: ${total:,.2f}")
    return "\n".join(lines)

# ============= AMOUNT QUERIES =============

def invoices_over_amount(amount_threshold):
    """Get invoices over a certain amount"""
    invoices = load_all_invoices()
    filtered = []
    
    for inv in invoices:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            if balance_val >= amount_threshold:
                filtered.append((inv, balance_val))
        except:
            pass
    
    if not filtered:
        return f"No invoices over ${amount_threshold:,.2f}"
    
    filtered.sort(key=lambda x: x[1], reverse=True)
    
    lines = [f"INVOICES OVER ${amount_threshold:,.2f} ({len(filtered)} total):\n"]
    total = 0
    for inv, balance_val in filtered[:15]:
        total += balance_val
        lines.append(
            f"• {inv.get('Invoice #', '')} | {inv.get('Vendor', '')} | "
            f"${balance_val:,.2f} | {inv.get('Aging', '')} days"
        )
    
    if len(filtered) > 15:
        lines.append(f"... and {len(filtered) - 15} more")
    
    lines.append(f"\nTotal: ${total:,.2f}")
    return "\n".join(lines)

def top_largest_invoices(limit=10):
    """Get top N largest invoices"""
    invoices = load_all_invoices()
    invoice_list = []
    
    for inv in invoices:
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            invoice_list.append((inv, balance_val))
        except:
            pass
    
    invoice_list.sort(key=lambda x: x[1], reverse=True)
    
    lines = [f"TOP {limit} LARGEST INVOICES:\n"]
    total = 0
    for inv, balance_val in invoice_list[:limit]:
        total += balance_val
        lines.append(
            f"• {inv.get('Invoice #', '')} | {inv.get('Vendor', '')} | "
            f"${balance_val:,.2f} | Due {inv.get('Due Date', '')} | {inv.get('Aging', '')} days"
        )
    
    lines.append(f"\nTotal: ${total:,.2f}")
    return "\n".join(lines)

# ============= OVERDUE & AGING QUERIES =============

def get_overdue_invoices():
    """Get list of overdue invoices"""
    invoices = load_all_invoices()
    overdue = []
    
    for inv in invoices:
        aging = inv.get("Aging", "").strip()
        if aging in ["30", "60", "90", "90+"]:
            overdue.append({
                "invoice": inv.get("Invoice #", ""),
                "vendor": inv.get("Vendor", ""),
                "due_date": inv.get("Due Date", ""),
                "balance": inv.get("Open Balance", "$0"),
                "aging": aging,
                "status": inv.get("Payment Status", ""),
                "entity": inv.get("Entity", "")
            })
    
    return sorted(overdue, key=lambda x: aging_priority(x["aging"]), reverse=True)

def get_overdue_summary():
    """Get overdue invoices summary as text"""
    overdue = get_overdue_invoices()
    
    if not overdue:
        return "No overdue invoices found."
    
    lines = [f"OVERDUE INVOICES ({len(overdue)} total):\n"]
    total = 0
    for inv in overdue[:20]:
        try:
            balance_val = float(inv['balance'].replace("$", "").replace(",", ""))
            total += balance_val
        except:
            balance_val = 0
        
        lines.append(
            f"• {inv['invoice']} | {inv['vendor']} | "
            f"Due {inv['due_date']} | {inv['aging']} days | "
            f"Balance: {inv['balance']} | Status: {inv['status']}"
        )
    
    if len(overdue) > 20:
        lines.append(f"... and {len(overdue) - 20} more")
    
    lines.append(f"\nTotal Overdue: ${total:,.2f}")
    return "\n".join(lines)

def get_aging_totals():
    """Get totals by aging bucket"""
    invoices = load_all_invoices()
    totals = {"Current": 0, "30": 0, "60": 0, "90": 0}
    counts = {"Current": 0, "30": 0, "60": 0, "90": 0}
    
    for inv in invoices:
        aging = inv.get("Aging", "").strip()
        balance = inv.get("Open Balance", "$0").strip()
        try:
            balance_val = float(balance.replace("$", "").replace(",", ""))
            if aging in totals:
                totals[aging] += balance_val
                counts[aging] += 1
        except:
            pass
    
    lines = ["TOTAL OPEN BALANCE BY AGING BUCKET:\n"]
    for bucket in ["Current", "30", "60", "90"]:
        lines.append(f"• {bucket} days: ${totals[bucket]:,.2f} ({counts[bucket]} invoices)")
    
    grand_total = sum(totals.values())
    lines.append(f"\nGrand Total: ${grand_total:,.2f}")
    
    return "\n".join(lines)

# ============= INVOICE-SPECIFIC QUERIES =============

def get_invoice_status(invoice_number):
    """Get status of a specific invoice"""
    invoices = load_all_invoices()
    
    for inv in invoices:
        if invoice_number.lower() in inv.get("Invoice #", "").lower():
            return (
                f"Invoice: {inv.get('Invoice #', 'N/A')}\n"
                f"Vendor: {inv.get('Vendor', 'N/A')}\n"
                f"Amount: {inv.get('Open Balance', 'N/A')}\n"
                f"Due Date: {inv.get('Due Date', 'N/A')}\n"
                f"Status: {inv.get('Status', 'N/A')}\n"
                f"Payment Status: {inv.get('Payment Status', 'N/A')}\n"
                f"Aging: {inv.get('Aging', 'N/A')} days\n"
                f"Entity: {inv.get('Entity', 'N/A')}\n"
                f"Date: {inv.get('Date', 'N/A')}"
            )
    
    return f"Invoice {invoice_number} not found"

def has_invoice_been_processed(invoice_number):
    """Check if an invoice has been processed"""
    invoices = load_all_invoices()
    
    for inv in invoices:
        if invoice_number.lower() in inv.get("Invoice #", "").lower():
            status = inv.get("Status", "").lower()
            if status == "approved":
                return f"✓ Invoice {invoice_number} HAS BEEN PROCESSED (Status: Approved)"
            elif status == "unassigned":
                return f"✗ Invoice {invoice_number} HAS NOT BEEN PROCESSED YET (Status: Unassigned)"
            else:
                return f"? Invoice {invoice_number} Status: {status}"
    
    return f"Invoice {invoice_number} not found in system"

def has_invoice_been_paid(invoice_number):
    """Check if an invoice has been paid"""
    invoices = load_all_invoices()
    
    for inv in invoices:
        if invoice_number.lower() in inv.get("Invoice #", "").lower():
            payment_status = inv.get("Payment Status", "").lower()
            if payment_status == "paid":
                return f"✓ Invoice {invoice_number} HAS BEEN PAID"
            elif payment_status == "unpaid":
                amount = inv.get("Open Balance", "unknown amount")
                due_date = inv.get("Due Date", "N/A")
                return f"✗ Invoice {invoice_number} HAS NOT BEEN PAID\n  Outstanding Amount: {amount}\n  Due Date: {due_date}"
            else:
                return f"? Invoice {invoice_number} Payment Status: {payment_status}"
    
    return f"Invoice {invoice_number} not found in system"

# ============= CHATBOT FUNCTIONS =============

def load_email_documents(limit=None):
    """Load email documents from JSONL file"""
    docs = []
    with open(EMAILS_FILE, "r", encoding="utf-8") as f:
        count = 0
        for line in f:
            record = json.loads(line)
            body = record.get("clean_text", "")
            subject = record.get("subject", "No Subject")
            sender = record.get("sender", "Unknown")
            date = record.get("date", "No Date")

            content = (
                f"[EMAIL]\n"
                f"Subject: {subject}\n"
                f"From: {sender}\n"
                f"Date: {date}\n"
                f"Content:\n{body}"
            )

            docs.append(
                Document(
                    page_content=content,
                    metadata={"type": "email", "subject": subject, "sender": sender, "date": date}
                )
            )
            count += 1
            if limit and count >= limit:
                break
    return docs

def load_csv_documents(csv_file):
    """Load aging detail documents from CSV file"""
    docs = []
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get("Status", "").strip()
            payment_status = row.get("Payment Status", "").strip()
            invoice = row.get("Invoice #", "").strip()
            date = row.get("Date", "").strip()
            vendor = row.get("Vendor", "").strip()
            due_date = row.get("Due Date", "").strip()
            aging = row.get("Aging", "").strip()
            balance = row.get("Open Balance", "").strip()
            entity = row.get("Entity", "").strip()

            text_lines = [
                "[AGING_INVOICE]",
                f"Entity: {entity}",
                f"Invoice #: {invoice}",
                f"Vendor: {vendor}",
                f"Date: {date}",
                f"Due Date: {due_date}",
                f"Aging Bucket: {aging}",
                f"Open Balance: {balance}",
                f"Status: {status}",
                f"Payment Status: {payment_status}",
            ]

            page_text = "\n".join(text_lines)

            docs.append(
                Document(
                    page_content=page_text,
                    metadata={
                        "type": "aging",
                        "entity": entity,
                        "invoice": invoice,
                        "vendor": vendor,
                        "due_date": due_date,
                        "aging_bucket": aging,
                        "balance": balance,
                        "status": status,
                        "payment_status": payment_status
                    }
                )
            )
    return docs

def build_vectorstore(email_limit=None):
    """Build vector database from emails and CSV aging files"""
    print("Loading emails...")
    email_docs = load_email_documents(limit=email_limit)
    
    print("Loading ACC aging details...")
    csv_acc_docs = load_csv_documents(CSV_ACC)
    
    print("Loading WC aging details...")
    csv_wc_docs = load_csv_documents(CSV_WC)
    
    all_docs = email_docs + csv_acc_docs + csv_wc_docs
    
    print(f"Loaded {len(email_docs)} emails, {len(csv_acc_docs)} ACC invoices, {len(csv_wc_docs)} WC invoices")

    print("Splitting documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(all_docs)
    print(f"Created {len(chunks)} chunks")

    print("Creating vector database... (this may take a few minutes)")
    embeddings = OpenAIEmbeddings()
    vstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./ap_chatbot_db"
    )
    print("Vector database created!")
    return vstore

def make_chain(vstore):
    """Create the QA chain"""
    retriever = vstore.as_retriever(search_kwargs={"k": 8})
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    template = """You are an Accounts Payable specialist. Use the context from both emails and AP aging CSV data.

IMPORTANT RULES:
- Use invoice data from aging details (amount, due date, status, aging bucket) as the source of truth
- Use emails only for communication context and additional explanations
- Always include invoice amounts and due dates when discussing invoices
- Format invoice lists clearly with: Invoice #, Vendor, Due Date, Amount, Aging Bucket, Status
- If asked about a specific invoice, provide all available details from aging
- Distinguish between ACC and WC entities when relevant

Context:
{context}

Question:
{question}

Answer concisely with specific invoice details from aging data."""

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question"]
    )

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain

# ============= MAIN CHATBOT INTERFACE =============

if __name__ == "__main__":
    print("Building AP Chatbot with Emails + Aging Details (ACC + WC)...\n")
    
    vectorstore = build_vectorstore(email_limit=None)
    chain = make_chain(vectorstore)

    print("\n" + "="*80)
    print("AP CHATBOT READY! (Emails + ACC + WC Aging Details)")
    print("="*80)
    print("\n📊 QUICK COMMANDS:")
    print("  'report'          - Vendor aging summary (oldest first)")
    print("  'overdue'         - List all overdue invoices")
    print("  'totals'          - Total open balance by aging bucket")
    print("  'compare'         - Compare ACC vs WC aging")
    print("  'top10'           - Top 10 largest invoices")
    print("  'due7'            - Invoices due in next 7 days")
    print("  'unpaid'          - All unpaid invoices")
    print("  'unassigned'      - All unassigned invoices")
    print("  'approved'        - All approved invoices")
    print("  'most_unpaid'     - Vendors with most unpaid invoices")
    print("\n❓ QUERY EXAMPLES:")
    print("  'vendor mitch'             - Show all invoices for that vendor")
    print("  'total mitch'              - Total amount due to vendor")
    print("  'over 5000'                - Show invoices over $5,000")
    print("  'invoice 630840'           - Get status of specific invoice")
    print("  'processed 630840'         - Has invoice been processed?")
    print("  'paid RB-386832-25'        - Has invoice been paid?")
    print("\n🤖 CHAT WITH AI (uses emails + aging data):")
    print("  Ask anything naturally - chatbot will search and answer!")
    print("\nType 'quit', 'exit', or 'bye' to stop.\n")

    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
            print("Goodbye!")
            break
        
        # Quick command: report
        if user_input.lower() == 'report':
            print(f"\nChatbot:\n{get_vendor_summary_text()}\n")
            continue
        
        # Quick command: overdue
        if user_input.lower() == 'overdue':
            print(f"\nChatbot:\n{get_overdue_summary()}\n")
            continue
        
        # Quick command: totals
        if user_input.lower() == 'totals':
            print(f"\nChatbot:\n{get_aging_totals()}\n")
            continue
        
        # Quick command: compare
        if user_input.lower() == 'compare':
            print(f"\nChatbot:\n{entity_comparison()}\n")
            continue
        
        # Quick command: top10
        if user_input.lower() == 'top10':
            print(f"\nChatbot:\n{top_largest_invoices(10)}\n")
            continue
        
        # Quick command: due7
        if user_input.lower() == 'due7':
            print(f"\nChatbot:\n{invoices_due_soon(7)}\n")
            continue
        
        # Quick command: unpaid
        if user_input.lower() == 'unpaid':
            print(f"\nChatbot:\n{get_by_payment_status('Unpaid')}\n")
            continue

        # Quick command: unassigned
        if user_input.lower() == 'unassigned':
            print(f"\nChatbot:\n{get_by_status('Unassigned')}\n")
            continue

        # Quick command: approved
        if user_input.lower() == 'approved':
            print(f"\nChatbot:\n{get_by_status('Approved')}\n")
            continue

        # Quick command: most_unpaid
        if user_input.lower() == 'most_unpaid':
            print(f"\nChatbot:\n{vendors_with_most_unpaid()}\n")
            continue

        # Vendor invoices
        if user_input.lower().startswith("vendor "):
            vendor_name = user_input.split("vendor ", 1)[1]
            print(f"\nChatbot:\n{get_vendor_invoices(vendor_name)}\n")
            continue

        # Vendor total
        if user_input.lower().startswith("total "):
            vendor_name = user_input.split("total ", 1)[1]
            print(f"\nChatbot:\n{get_vendor_total(vendor_name)}\n")
            continue

        # Invoices over amount
        if user_input.lower().startswith("over "):
            try:
                amount = float(user_input.split("over ", 1)[1].replace(",", ""))
                print(f"\nChatbot:\n{invoices_over_amount(amount)}\n")
                continue
            except:
                pass

        # Invoice status
        if user_input.lower().startswith("invoice "):
            invoice_num = user_input.split("invoice ", 1)[1]
            print(f"\nChatbot:\n{get_invoice_status(invoice_num)}\n")
            continue

        # Processed check
        if user_input.lower().startswith("processed "):
            invoice_num = user_input.split("processed ", 1)[1]
            print(f"\nChatbot:\n{has_invoice_been_processed(invoice_num)}\n")
            continue

        # Paid check
        if user_input.lower().startswith("paid "):
            invoice_num = user_input.split("paid ", 1)[1]
            print(f"\nChatbot:\n{has_invoice_been_paid(invoice_num)}\n")
            continue

        # =====================
        # LLM FALLBACK (RAG)
        # =====================
        try:
            response = chain.invoke(user_input)
            print(f"\nChatbot:\n{response}\n")
        except Exception as e:
            print("\nChatbot:\nSorry — I couldn’t process that request.\n")
