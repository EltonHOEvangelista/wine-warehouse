from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from datetime import datetime
import pytz

purchases_bp = Blueprint('purchases', __name__)

def init_purchase_routes(purchases_collection):
    
    #Place purchase order (Expanding stock).
    @purchases_bp.route('/purchase', methods=['POST'])
    def place_purchase_order():
        data = request.get_json()
        
        # Function to create a purchase order
        def create_purchase_order(data):
            new_order = {
                "wine_id": data.get("wine_id"),
                "cost_price": data.get("cost_price"),
                "amount": data.get("amount"),
                "date": datetime.now(pst)
            }
            try:
                result = purchases_collection.insert_one(new_order)
                new_order["_id"] = str(result.inserted_id)
                return new_order
            except Exception as e:
                return None, str(e)
        
        purchase_order = create_purchase_order(data)
        if not purchase_order:
            return jsonify({
                "message": "Error creating account",
                "response_status": False
            }), 500
        
        # Prepare response with account data
        response = {
            "message": "Purchase order registered successfully",
            "response_status": True
        }
        return jsonify(response), 201
        
    # Create initial list of stock
    @purchases_bp.route('/purchase/all', methods=['POST'])
    def create_initial_purchase():
        data_list = request.json
        
        if not isinstance(data_list, list):
            return jsonify({
                "message": "Input data must be a list",
                "response_status": False
            }), 400

        def create_order_list():
            order_list = []
            for data in data_list:
                new_order = {
                    "wine_id": data.get("wine_id"),
                    "cost_price": data.get("cost_price"),
                    "amount": data.get("amount"),
                    "date": datetime.now(pst)  # Server timestamp
                }
                order_list.append(new_order)
                
            try:
                result = purchases_collection.insert_many(order_list)
                return order_list
            except Exception as e:
                return None, str(e)
                
        purchase_order_list = create_order_list()
        if not purchase_order_list:
            return jsonify({
                "message": "Error creating purchase order list",
                "response_status": False
            }), 500
        
        # Prepare response order list
        response = {
            "message": "Purchase order list registered successfully",
            "response_status": True
        }
        return jsonify(response), 201
















































