from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class PurchaseItem(BaseModel):
    wine_id: ObjectId
    quantity: int

class Purchase(BaseModel):
    user_id: ObjectId
    items: List[PurchaseItem]
    purchase_date: datetime = datetime.utcnow()
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None