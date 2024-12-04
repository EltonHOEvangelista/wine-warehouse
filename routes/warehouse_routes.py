from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from .stock_manager import update_wine_stock, get_warehouse_id

warehouses_bp = Blueprint('warehouse', __name__)

def init_warehouse_routes(warehouses_collection):
    #Update wine stock at the warehouse
    @warehouses_bp.route('/warehouse', methods=['POST'])
    def update_warehouse_stock():
        data = request.get_json()
        
        location = data.get("location")
        location_id = get_warehouse_id(warehouses_collection, location)
        aisles = data.get("aisles")
    
        first_aisle = aisles[0]
        aisle = first_aisle.get("aisle")
        shelves = first_aisle.get("shelves")
        
        first_shelf = shelves[0]
        shelf = first_shelf.get('shelf')
        wines = first_shelf.get('wines')
        
        first_wine = wines[0]
        wine_id = first_wine.get('wine_id')
        stock_to_add = int(first_wine.get('stock'))
        
        #function to update stock in the required warehouse location
        result = update_wine_stock(
                    warehouses_collection,
                    location_id,
                    aisle,
                    shelf,
                    wine_id,
                    stock_to_add)
                    
        if result["success"]:
            return jsonify({
                "message": "New stock registered successfully",
                "response_status": True
            }), 201
        else:
            return jsonify({
                "message": "Error adding stock",
                "response_status": False
            }), 500

    # Create initial list of stock
    @warehouses_bp.route('/warehouse/all', methods=['POST'])
    def create_initial_stock():
        data_list = request.json
        
        if not isinstance(data_list, list):
            return jsonify({
                "message": "Input data must be a list",
                "response_status": False
            }), 400

        def create_stock_list():
            stock_list = []
            for data in data_list:
                new_stock = {
                    "location": data.get("location"),
                    "aisles": data.get("aisles")
                }
                stock_list.append(new_stock)
                
            try:
                result = warehouses_collection.insert_many(stock_list)
                return stock_list
            except Exception as e:
                return None, str(e)
                
        stock = create_stock_list()
        if not stock:
            return jsonify({
                "message": "Error adding stock list",
                "response_status": False
            }), 500
        
        # Prepare response stock list
        response = {
            "message": "Stock list registered successfully",
            "response_status": True
        }
        return jsonify(response), 201