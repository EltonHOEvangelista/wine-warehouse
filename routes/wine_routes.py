from flask import Blueprint, jsonify, request
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
from .stock_manager import get_total_stock, get_wine_locations_and_stock, get_wines_below_min_stock

wines_bp = Blueprint('wines', __name__)

def init_wine_routes(wines_collection, warehouses_collection):
    
    @wines_bp.route('/wines', methods=['GET'])
    def get_wines():
        # Initialize an empty filter dictionary
        filter_criteria = {}

        # Partial name filter
        name_query = request.args.get('name')
        if name_query:
            filter_criteria['name'] = {"$regex": name_query, "$options": "i"}  # Case-insensitive regex

        # Wine type filter
        wine_types = request.args.get('type')
        if wine_types:
            wine_types_list = wine_types.split(",")
            filter_criteria['$or'] = [{"type": {"$regex": f"^{wine_type.strip()}$", "$options": "i"}} for wine_type in wine_types_list]

        # Grape filter
        grape = request.args.get('grape')
        if grape:
            filter_criteria['grapes'] = {"$elemMatch": {"$regex": grape, "$options": "i"}}  # Case-insensitive regex

        # Food pairing filter
        food_pair = request.args.get('food_pair')
        if food_pair:
            filter_criteria['food_pair'] = {"$elemMatch": {"$regex": food_pair, "$options": "i"}}  # Case-insensitive regex

        # Harvest year range filter
        min_harvest = request.args.get('min_harvest')
        max_harvest = request.args.get('max_harvest')
        if min_harvest or max_harvest:
            filter_criteria['harvest_year'] = {}
            if min_harvest:
                filter_criteria['harvest_year']['$gte'] = int(min_harvest)
            if max_harvest:
                filter_criteria['harvest_year']['$lte'] = int(max_harvest)

        # Country filter
        country = request.args.get('country')
        if country:
            filter_criteria['country'] = {"$regex": country, "$options": "i"}

        # Producer filter
        producer = request.args.get('producer')
        if producer:
            filter_criteria['producer'] = {"$regex": producer, "$options": "i"}

        # Discount threshold filter
        discount_threshold = request.args.get('discount')
        if discount_threshold:
            filter_criteria['discount'] = {"$gte": float(discount_threshold)}

        # Price range filter
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        if min_price or max_price:
            filter_criteria['sale_price'] = {}
            if min_price:
                filter_criteria['sale_price']['$gte'] = float(min_price)
            if max_price:
                filter_criteria['sale_price']['$lte'] = float(max_price)

        # Sorting by price
        sort_order = request.args.get('sort_price_order', 'asc')
        sort_direction = 1 if sort_order == 'asc' else -1

        # Pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        skip = (page - 1) * limit

        # Query MongoDB with the constructed filter, apply sorting and pagination
        wines = list(
            wines_collection.find(filter_criteria)
            .sort("sale_price", sort_direction)  # Apply sorting by price
            .skip(skip)
            .limit(limit)
        )

        # Convert ObjectId to string for JSON serialization
        # set stock in each wine
        for wine in wines:
            wine['_id'] = str(wine['_id'])
            wine['stock'] = get_total_stock(warehouses_collection, wine['_id'])
            wine['stock_location'] = get_wine_locations_and_stock(warehouses_collection, wine['_id'])

        # Get the total count of wines matching the filter
        total_count = wines_collection.count_documents(filter_criteria)

        # Prepare paginated response
        response = {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "wines": wines
        }
        return jsonify(response)
    
    # get wines with low stock level    
    @wines_bp.route('/wines/low', methods=['GET'])
    def get_wines_low_stock():
        """
        Endpoint to get wines with stock below a certain level.
        """
        # Extract and validate the `min_stock` parameter
        min_stock = request.args.get('min_stock')
        if min_stock is None or not min_stock.isdigit():
            return jsonify({"error": "min_stock parameter is required and must be an integer"}), 400
    
        min_stock = int(min_stock)
    
        # Get wines with stock below the specified minimum
        low_stock_wines = get_wines_below_min_stock(warehouses_collection, min_stock)
        
        wines = []
        for wine in low_stock_wines:
            wine_data = get_wine(wine["wine_id"])  # Ensure this returns a serializable object
            if isinstance(wine_data, dict):  # Verify wine_data is serializable
                wines.append(wine_data)
            else:
                return jsonify({"error": f"Unexpected data format for wine_id {wine['wine_id']}"}), 500
    
        response = {
            "wines": wines
        }
        return jsonify(response)

    # Get a single wine by ID
    @wines_bp.route('/wines/<id>', methods=['GET'])
    def get_wine(id):
        """
        Retrieve wine details by ID.
        """
        wine = wines_collection.find_one({"_id": ObjectId(id)})
        if wine:
            wine['_id'] = str(wine['_id'])  # Convert ObjectId to string
            wine['stock'] = get_total_stock(warehouses_collection, wine['_id'])  # Load stock from warehouse
            wine['stock_location'] = get_wine_locations_and_stock(warehouses_collection, wine['_id'])
            return wine  # Return as a dictionary
        
        return {"error": "Wine not found"}, 404  # Return error as a dictionary

    # Create a new wine.
    @wines_bp.route('/wines', methods=['POST'])
    def create_wine():
        data = request.json
        
        # Function to create new wine
        def create_wine(data):
            new_wine = {
                "image_path": data.get("image_path"),
                "name": data.get("name"),
                "producer": data.get("producer"),
                "country": data.get("country"),
                "harvest_year": data.get("harvest_year"),
                "type": data.get("type"),
                "rate": data.get("rate"),
                "description": data.get("description"),
                "reviews": data.get("reviews"),
                "grapes": data.get("grapes"),
                "taste_characteristics": data.get("taste_characteristics"),
                "food_pair": data.get("food_pair"),
                "sale_price": data.get("sale_price"),
                "discount": data.get("discount"),
                "stock": data.get("stock")
            }
            try:
                result = wines_collection.insert_one(new_wine)
                new_wine["_id"] = str(result.inserted_id) #Convert ObjectId to string
                return new_wine
            except Exception as e:
                return None, str(e)
        
        wine = create_wine(data)
        if not wine:
            return jsonify({
                "message": "Error creating wine",
                "response_status": False
            }), 500
        
        # Prepare response with wine data
        response = {
            "response_id": wine["_id"],
            "message": "Wine registered successfully",
            "response_status": True
        }
        return jsonify(response), 201

    # Update an existing wine
    @wines_bp.route('/wines/<id>', methods=['PATCH'])
    def update_wine(id):
        try:
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400
    
            # Verify the wine exists before updating
            existing_wine = wines_collection.find_one({"_id": ObjectId(id)})
            if not existing_wine:
                return jsonify({"error": "Wine not found"}), 404
    
            # Prepare the updated data, excluding fields that shouldn't be updated
            updated_data = {key: value for key, value in data.items() if key != "_id"}
    
            if not updated_data:
                return jsonify({"error": "No valid fields to update"}), 400
    
            # Perform the update
            result = wines_collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": updated_data}
            )
    
            if result.modified_count == 0:
                return jsonify({"message": "No changes were made"}), 200
    
            # Prepare and return a success response
            response = {
                "response_id": str(existing_wine["_id"]),
                "message": "Wine updated successfully",
                "response_status": True
            }
            return jsonify(response), 200
    
        except Exception as e:
            print(f"Error updating wine: {e}")
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    # Delete a wine
    @wines_bp.route('/wines/<id>', methods=['DELETE'])
    def delete_wine(id):
        result = wines_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count:
            return jsonify({"message": "Wine deleted successfully"})
        return jsonify({"error": "Wine not found"}), 404

    # Search wines by partial name with pagination
    @wines_bp.route('/wines/search', methods=['GET'])
    def search_wines():
        query = request.args.get('q', '')  # 'q' is the search term
        page = int(request.args.get('page', 1))  # Default to page 1
        limit = int(request.args.get('limit', 10))  # Default to 10 items per page
        skip = (page - 1) * limit

        # Query MongoDB with regex and pagination
        wines = list(wines_collection.find({"name": {"$regex": query, "$options": "i"}}).skip(skip).limit(limit))
        for wine in wines:
            wine['_id'] = str(wine['_id'])
            wine['stock'] = get_total_stock(warehouses_collection, wine['_id'])

        # Get total count of wines matching the search query
        total_count = wines_collection.count_documents({"name": {"$regex": query, "$options": "i"}})

        # Prepare paginated response
        response = {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "wines": wines
        }
        return jsonify(response)

    # Filter wines by type
    @wines_bp.route('/wines/filter', methods=['GET'])
    def filter_wines_by_type():
        wine_type = request.args.get('type')
        wines = list(wines_collection.find({"type": wine_type}))
        for wine in wines:
            wine['_id'] = str(wine['_id'])
            wine['stock'] = get_total_stock(warehouses_collection, wine['_id'])
        return jsonify(wines)

    # Remove all wines and create initial list
    @wines_bp.route('/wines/all', methods=['POST'])
    def create_initial_wines():
        
        #function to delete all existing wines on wine_warehouse
        delete_all_wines()
        
        data_list = request.json
        if not isinstance(data_list, list):
            return jsonify({"error": "Input data must be a list"}), 400
        wine_list = []
        for data in data_list:
            new_wine = {
                "image_path": data.get("image_path"),
                "name": data.get("name"),
                "producer": data.get("producer"),
                "country": data.get("country"),
                "harvest_year": data.get("harvest_year"),
                "type": data.get("type"),
                "rate": data.get("rate"),
                "description": data.get("description"),
                "reviews": data.get("reviews"),
                "grapes": data.get("grapes"),
                "taste_characteristics": data.get("taste_characteristics"),
                "food_pair": data.get("food_pair"),
                "sale_price": data.get("sale_price"),
                "discount": data.get("discount"),
                "stock": data.get("stock")
            }
            wine_list.append(new_wine)
        try:
            result = wines_collection.insert_many(wine_list)
            if result.inserted_ids:
                return jsonify({"message": "List of wines created successfully"}), 201
        except PyMongoError as e:
            return jsonify({"error": f"Failed to create list of wines: {str(e)}"}), 500
        return jsonify({"error": "Unknown error occurred"}), 500
        
    # Delete all wines
    @wines_bp.route('/wines', methods=['DELETE'])
    def delete_all_wines():
        result = wines_collection.delete_many({})
        if result.deleted_count > 0:
            return jsonify({"message": "All wines deleted successfully"}), 200
        return jsonify({"error": "No wines found to delete"}), 404
    
    #get wines by ids
    @wines_bp.route('/wines/bulk', methods=['POST'])
    def get_wines_by_ids():
        try:
            # Retrieve the list of wine IDs from the request
            wine_ids = request.json.get("wine_ids", [])
            if not wine_ids:
                return jsonify({"error": "No wine IDs provided"}), 400

            # Convert string IDs to ObjectId for MongoDB query
            object_ids = [ObjectId(wine_id) for wine_id in wine_ids]

            # Query MongoDB for wines with the provided IDs
            wines = list(wines_collection.find({"_id": {"$in": object_ids}}))

            # Convert ObjectId to string for JSON serialization
            for wine in wines:
                wine['_id'] = str(wine['_id'])
                wine['stock'] = get_total_stock(warehouses_collection, wine['_id'])

            return jsonify(wines), 200

        except PyMongoError as e:
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            