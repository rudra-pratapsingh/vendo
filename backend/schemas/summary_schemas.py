from pydantic import BaseModel, Field
from typing import List, Literal
from datetime import datetime

class ItemSummary(BaseModel):
  item_id: int
  item_name: str
  total_quantity_sold: int
  total_revenue: float

class LowStockItems(BaseModel):
  item_name: str
  current_stock: int

class DailySummaryResponse(BaseModel):
  date: datetime
  total_sales_amount: float
  total_orders: int
  top_items: List[ItemSummary]
  low_stock_items: List[LowStockItems] | None

class RangeSummaryResponse(BaseModel):
  start_date: datetime
  end_date: datetime
  total_sales_amount: int
  total_orders: int
  average_daily_sales: int
  top_items: List[ItemSummary]
  slow_moving_items: List[ItemSummary]

class Insight(BaseModel):
  type: Literal["warning", "info", "positive"]
  message: str = Field(..., max_length=500, descripton="Human readeable insight message")