import asyncio
from pulse.db.database import get_session
from pulse.db.crud import get_transactions

async def main():
    print("--- Your Expense Database ---")
    
    # We will fetch transactions for your specific thread_id (user ID)
    # The logs showed your ID is: 1485978523
    user_id = "1485978523"
    
    async with get_session() as session:
        txns = await get_transactions(session, thread_id=user_id)
        
        if not txns:
            print("No transactions found.")
        
        for t in txns:
            print(f"ID: {t.id} | Date: {t.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {t.currency} {t.amount} | Vendor: {t.vendor} | Category: {t.category}")
            print(f"    Source text: '{t.source_text}'\n")

if __name__ == "__main__":
    asyncio.run(main())
