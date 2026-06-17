from typing import Optional
from pydantic import BaseModel, Field

class QueryModel(BaseModel):
    event_id: Optional[int] = Field(None)

try:
    # Test empty string coercion
    m = QueryModel(event_id="")
    print("Parsed event_id='':", m.event_id)
except Exception as e:
    print("Error parsing event_id='':", type(e).__name__, str(e))
