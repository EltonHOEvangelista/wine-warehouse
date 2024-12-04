from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from datetime import datetime

financial_bp = Blueprint('financial', __name__)

def init_financial_routes(purchases_collection, sales_collection):
    @financial_bp.route('/financial', methods=['GET'])
    def get_cumulative_cost_revenue_by_date():
        try:
            # Get date range from request arguments
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Validate and parse dates
            if not start_date or not end_date:
                return jsonify({"error": "Please provide start_date and end_date"}), 400
            
            start_date = datetime.fromisoformat(start_date)
            end_date = datetime.fromisoformat(end_date)
            
            # Pipeline for cumulative cost from purchases
            purchases_pipeline = [
                {
                    "$match": {
                        "date": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$addFields": {
                        "cumulative_cost": {"$multiply": ["$cost_price", "$amount"]}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d %H:%M:%S", 
                                "date": "$date"
                            }
                        },
                        "total_cost": {"$sum": "$cumulative_cost"}
                    }
                },
                {
                    "$sort": {"_id": 1}  # Sort by date (ascending)
                }
            ]
            
            purchases_results = list(purchases_collection.aggregate(purchases_pipeline))
            
            # Pipeline for cumulative sales from sales
            sales_pipeline = [
                {
                    "$match": {
                        "sales_date": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d %H:%M:%S", 
                                "date": "$sales_date"
                            }
                        },
                        "total_sales": {"$sum": "$total_price"}
                    }
                },
                {
                    "$sort": {"_id": 1}  # Sort by date (ascending)
                }
            ]
            
            sales_results = list(sales_collection.aggregate(sales_pipeline))
            
            # Merge results by date
            financial_data = {}
            
            # Add purchases data
            for purchase in purchases_results:
                date = purchase["_id"]
                financial_data[date] = {
                    "date": date,
                    "cumulative_cost": purchase["total_cost"],
                    "cumulative_sales": 0  # Default value
                }
            
            # Add sales data
            for sale in sales_results:
                date = sale["_id"]
                if date in financial_data:
                    financial_data[date]["cumulative_sales"] = sale["total_sales"]
                else:
                    financial_data[date] = {
                        "date": date,
                        "cumulative_cost": 0,  # Default value
                        "cumulative_sales": sale["total_sales"]
                    }
            
            # Convert merged data to a sorted list
            result = sorted(financial_data.values(), key=lambda x: x["date"])
            
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500