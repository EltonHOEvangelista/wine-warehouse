from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from .stock_manager import get_total_stock, update_stock_after_sale
from datetime import datetime
import calendar

sales_bp = Blueprint('sales', __name__)

def init_sale_routes(sales_collection, wines_collection, warehouses_collection):
    
    # Get customer's orders by account id
    @sales_bp.route('/sales/customer/<account_id>', methods=['GET'])
    def get_orders_by_customer_id(account_id):
        try:
            # Query MongoDB with account id
            orders = list(sales_collection.find({"account_id": ObjectId(account_id)}))

            # Convert ObjectId to string for JSON serialization
            for order in orders:
                order['_id'] = str(order['_id'])
                order['account_id'] = str(order['account_id'])
            
            response = {
                "invoices": orders
            }
            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    
    # Get customer's orders not dispatched.
    @sales_bp.route('/sales/customer/dispatch/<dispatch_status>', methods=['GET'])
    def get_orders_not_dispatched(dispatch_status):
        try:
            # Query MongoDB with account id
            orders = list(sales_collection.find({"dispatch_status": int(dispatch_status)}))

            # Convert ObjectId to string for JSON serialization
            for order in orders:
                order['_id'] = str(order['_id'])
                order['account_id'] = str(order['account_id'])
                
            response = {
                "invoices": orders
            }
            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        
    #Place customer's order.
    @sales_bp.route('/sales', methods=['POST'])
    def process_sales_cart():
        # Extract and validate JSON data
        data = request.get_json()
    
        account = data.get("account")
    
        items = data.get("items", [])
        
        shipping_address = data.get("shipping_address")

        total_price = 0
        insufficient_stock_items = []
        processed_items = []

        for item in items:
            wine_id = item.get("wine_id")
            quantity_requested = item.get("quantity")
    
            # Update stock and process sale
            sale_item = update_stock_after_sale(warehouses_collection, wine_id, quantity_requested)
            
            if not sale_item or not isinstance(sale_item, list) or "success" not in sale_item[0]:
                return jsonify({"error": f"Failed to process item: {item}"}), 400
    
            if not sale_item[0]["success"]:
                insufficient_stock_items.append({
                    "wine_id": str(wine_id),
                    "available_stock": int(sale_item[0].get("stock", 0)),
                    "requested_quantity": int(quantity_requested)
                })
            else:
                wine = wines_collection.find_one({"_id": ObjectId(wine_id)})
    
                price_per_unit = round(wine["sale_price"] * (1 - wine["discount"]), 2)
                item_total = round(price_per_unit * quantity_requested, 2)
                total_price += item_total
    
                processed_items.append({
                    "wine_id": str(wine_id),
                    "name": wine["name"],
                    "sale_price": round(wine["sale_price"], 2),
                    "discount": round(wine["discount"], 2),
                    "final_price_per_unit": price_per_unit,
                    "quantity": quantity_requested,
                    "item_total": item_total,
                    "stock_location": sale_item[1:]
                })
                
        response = {
            "invoices": [],
            "sale_refused": insufficient_stock_items
        }
        
        # Issue new invoice
        if processed_items:
            
            new_invoice = {
                "account_id": ObjectId(account["account_id"]),
                "items": processed_items,
                "total_price": round(total_price, 2),
                "sales_date": datetime.utcnow(),
                "shipping_address": shipping_address,
                "dispatch_status": 0
            }
            result = sales_collection.insert_one(new_invoice)
            new_invoice["_id"] = str(result.inserted_id)
            new_invoice["account_id"] = str(new_invoice["account_id"])
        
            # Append the new invoice to the "invoices" list
            response["invoices"].append(new_invoice)
        
        return jsonify(response), 200
        
    @sales_bp.route('/sales', methods=['GET'])
    def get_cumulative_sales():
        try:
            # Parse and validate dates
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            if not start_date or not end_date:
                return jsonify({"error": "Please provide start_date and end_date"}), 400
    
            try:
                start_date = datetime.fromisoformat(start_date)
                end_date = datetime.fromisoformat(end_date)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use ISO format (YYYY-MM-DD)."}), 400
            
            # Build filter criteria for wine names
            filter_criteria = {}
            name_query = request.args.get('name')
            
            if name_query:
                filter_criteria['name'] = {"$regex": name_query, "$options": "i"}
    
            wine_types = request.args.get('type')
            
            if wine_types:
                filter_criteria['type'] = {"$in": [wine_type.strip() for wine_type in wine_types.split(",")]}
            
            # Fetch wine names if filter criteria exists
            wine_names = []
            if filter_criteria:
                wines = list(wines_collection.find(filter_criteria))
                #wines = list(wines_collection.find(filter_criteria, {"name": 1}))
                wine_names = [wine["name"] for wine in wines]
    
            # Helper function to create $group stage
            def create_group_stage():
                return {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d %H:%M:%S", "date": "$sales_date"}
                        },
                        "total_sales_unit": {"$sum": "$items.quantity"},
                        "total_sales_amount": {"$sum": "$items.item_total"}
                    }
                }
    
            # Build aggregation pipeline
            match_stage = {
                "$match": {
                    "sales_date": {"$gte": start_date, "$lte": end_date}
                }
            }
    
            if wine_names:
                match_stage["$match"]["items.name"] = {"$in": wine_names}
    
            sales_pipeline = [
                match_stage,
                {"$unwind": "$items"},  # Flatten items array
                create_group_stage(),
                {"$sort": {"_id": 1}}
            ]
    
            # Execute the aggregation pipeline
            sales_results = list(sales_collection.aggregate(sales_pipeline))
    
            # Format the results
            result = [
                {
                    "date": sale["_id"],
                    "cumulative_sales_unit": sale["total_sales_unit"],
                    "cumulative_sales_amount": sale["total_sales_amount"]
                }
                for sale in sales_results
            ]
    
            return jsonify(result)
    
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # Create initial list of stock
    @sales_bp.route('/sales/all', methods=['POST'])
    def create_initial_sales():
        data_list = request.json
        
        if not isinstance(data_list, list):
            return jsonify({
                "message": "Input data must be a list",
                "response_status": False
            }), 400

        def create_sales_list():
            sales_list = []
            for data in data_list:
                new_sales = {
                    "account_id": data.get("account_id"),
                    "items": data.get("items"),
                    "total_price": data.get("total_price"),
                    # "sales_date": datetime.strptime(data.get("sales_date"), "%Y-%m-%d %H:%M:%S"),
                    "sales_date": datetime.fromisoformat(data.get("sales_date")),
                    "shipping_address": data.get("shipping_address"),
                    "dispatch_status": data.get("dispatch_status")
                }
                sales_list.append(new_sales)
            
            try:
                result = sales_collection.insert_many(sales_list)
                return sales_list
            except Exception as e:
                return None, str(e)
                
        sales_order_list = create_sales_list()
        if not sales_order_list:
            return jsonify({
                "message": "Error creating purchase order list",
                "response_status": False
            }), 500
        
        # Prepare response order list
        response = {
            "message": "Sales order list registered successfully",
            "response_status": True
        }
        return jsonify(response), 201