from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta

from backend.database.db import get_db
from backend.models.models import Sales, Items, SalesItems
from backend.schemas.summary_schemas import LowStockItems, ItemSummary, DailySummaryResponse, RangeSummaryResponse, Insight

import logging

router = APIRouter(prefix='/summary', tags=["Summary"])

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

@router.get('/daily', response_model=DailySummaryResponse)
def get_daily_summary(user_id: int, db: Session=Depends(get_db)):
  try:
    today = date.today()

    start_dt = datetime.combine(today, datetime.min.time()) 
    end_dt = start_dt + timedelta(days=1)

    total_sales_amount = (
      db.query(
        func.coalesce(func.sum(Sales.total_amount), 0).label("total_sales_amount"),
        func.count(Sales.id).label("total_orders")
      )
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at < end_dt)
      .scalar()
    )

    total_orders = (
      db.query(func.count(Sales.id))
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at < end_dt)
      .scalar()
    )

    top_items_query = (
      db.query(
          Items.id.label("item_id"),
          Items.name.label("item_name"),
          func.sum(SalesItems.quantity).label("total_quantity_sold"),
          func.sum(SalesItems.line_total).label("total_revenue"),
      )
      .join(SalesItems, Items.id == SalesItems.item_id)
      .join(Sales, Sales.id == SalesItems.sales_id)
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at < end_dt)
      .group_by(Items.id, Items.name)
      .order_by(func.sum(SalesItems.quantity).desc())
      .limit(5)
      .all()
    )

    top_items = [
      ItemSummary(
        item_id=row.item_id,
        item_name=row.item_name,
        total_quantity_sold=row.total_quantity_sold,
        total_revenue=row.total_revenue,
      )
      for row in top_items_query
    ]

    LOW_STOCK_THRESHOLD = 5

    low_stock_query = (
        db.query(
            Items.id.label("item_id"),
            Items.name.label("item_name"),
            Items.current_stock.label("current_stock"),
        )
        .filter(Items.user_id == user_id)
        .filter(Items.current_stock <= LOW_STOCK_THRESHOLD)
        .all()
    )

    low_stock_items = [
      LowStockItems(
        item_id=row.item_id,
        item_name=row.item_name,
        current_stock=row.current_stock,
      )
      for row in low_stock_query
    ]

    insights = []

    if total_sales_amount == 0:
      insights.append(
        Insight(
          type="warning",
          message="No sales recorded today."
        )
      )

    if low_stock_items:
      insights.append(
        Insight(
          type="warning",
          message="Some items are running low on stock."
        )
      )

    return DailySummaryResponse(
      date=today,
      total_sales_amount=total_sales_amount,
      total_orders=total_orders,
      top_items=top_items,
      low_stock_items=low_stock_items or None,
      insights=insights or None
    )
  
  except Exception as e:
    logger.error(f"Daily summary retrieval was not successful {str(e)}")
    raise HTTPException(
      status_code = 500,
      detail = f"An error occured while retrieving daily summary {str(e)}"
    )
  
@router.get('/', response_model=RangeSummaryResponse)
def get_range_summary(
  user_id: int,
  start_date: str = Query(None, description = "YYYY-MM-DD"),
  end_date: str = Query(None, description = "YYYY-MM-DD"),
  db: Session = Depends(get_db)
):
  try:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    end_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)

    total_sales_amount = (
      db.query(func.coalesce(func.sum(Sales.total_amount), 0))
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at <= end_dt)
      .scalar()
    )

    total_orders = (
      db.query(func.count(Sales.id))
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at <= end_dt)
      .scalar()
    )

    top_items = (
      db.query(
          Items.id.label("item_id"),
          Items.name.label("item_name"),
          func.sum(SalesItems.quantity).label("total_quantity_sold"),
          func.sum(SalesItems.line_total).label("total_revenue")
      )
      .join(SalesItems, Items.id == SalesItems.item_id)
      .join(Sales, Sales.id == SalesItems.sales_id)
      .filter(Sales.user_id == user_id)
      .filter(Sales.created_at >= start_dt)
      .filter(Sales.created_at <= end_dt)
      .group_by(Items.id, Items.name)
      .order_by(func.sum(SalesItems.quantity).desc())
      .limit(5)
      .all()
    )

    slow_items = (
      db.query(
        Items.id.label("item_id"),
        Items.name.label("item_name"),
        func.coalesce(func.sum(SalesItems.quantity), 0).label("total_quantity_sold"),
        func.coalesce(func.sum(SalesItems.line_total), 0).label("total_revenue")
      )
      .outerjoin(SalesItems, Items.id == SalesItems.item_id)
      .outerjoin(Sales, Sales.id == SalesItems.sales_id)
      .filter(Items.user_id == user_id)
      .group_by(Items.id, Items.name)
      .order_by(func.coalesce(func.sum(SalesItems.quantity), 0).asc())
      .limit(5)
      .all()
    )

    return {
      "start_date": start_date,
      "end_date": end_date,
      "total_sales_amount": float(total_sales_amount or 0),
      "total_orders": total_orders or 0,
      "average_daily_sales": round(float(total_sales_amount or 0) / max((end_dt - start_dt).days, 1)),
      "top_items": top_items,
      "slow_moving_items": slow_items
    }

  except Exception as e:
    logger.error(f"Range date summary retrieval was not successful {str(e)}")
    raise HTTPException(
      status_code = 500,
      detail = f"An error occured while retrieving range date summary {str(e)}"
    )