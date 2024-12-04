from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId

accounts_bp = Blueprint('account', __name__)

def init_account_routes(accounts_collection):
    @accounts_bp.route('/account/signup', methods=['POST'])
    def signup():
        data = request.get_json()
    
        # Check if this is the first account
        if check_existing_accounts() == 0:
            data["type"] = 1 # set as admin
        elif get_account_by_email(data.get("email")):
            return jsonify({
                "message": "User already exists",
                "response_status": False
            }), 400
    
        # Function to create an account
        def create_account(data):
            hashed_password = generate_password_hash(data['password'])
            new_account = {
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email": data.get("email"),
                "password": hashed_password,
                "phone": data.get("phone"),
                "status": data.get("status"),
                "type": data.get("type"),
                "address": data.get("address")
            }
            try:
                result = accounts_collection.insert_one(new_account)
                new_account["_id"] = str(result.inserted_id)
                return new_account
            except Exception as e:
                return None, str(e)
        
        account = create_account(data)
        if not account:
            return jsonify({
                "message": "Error creating account",
                "response_status": False
            }), 500
        
        # Prepare response with account data
        response = {
            "message": "Account registered successfully",
            "response_status": True,
            "_account": account
        }
        return jsonify(response), 201

    
    @accounts_bp.route('/account/signin', methods=['POST'])
    def signin():
        data = request.get_json()
        account = get_account_by_email(data["email"])
        
        if account:
            if verify_password(account["password"], data["password"]):
                # Prepare response
                response = {
                    "message": "Account successfully Authenticated and validated",
                    "response_status": True,
                    "_account": account
                }
                return jsonify(response), 201
            else:
                # Prepare response
                response = {
                    "message": "Invalid email or password",
                    "response_status": False
                }
                return jsonify(response), 401
        # Prepare response
        response = {
            "message": "Invalid email or password",
            "response_status": False
        }
        return jsonify(response), 401
        

    @accounts_bp.route('/account/delete', methods=['DELETE'])
    def delete_account():
        
        # Extract email and password from query parameters
        email = request.args.get('email')
        password = request.args.get('password')
    
        # Validate input
        if not email or not password:
            return jsonify({
                "message": "Invalid request data",
                "response_status": False
            }), 400
        
        # Retrieve account
        account = get_account_by_email(email)
        if account:
            # Verify password
            if verify_password(account["password"], password):
                # Delete account in the database using the account's unique identifier (_id)
                result = accounts_collection.delete_one({"_id": ObjectId(account["_id"])})
                if result.deleted_count > 0:
                    return jsonify({
                        "message": "Account successfully deleted",
                        "response_status": True
                    }), 200
                else:
                    return jsonify({
                        "message": "Failed to delete account",
                        "response_status": False
                    }), 500
            else:
                return jsonify({
                    "message": "Invalid credentials",
                    "response_status": False
                }), 401
    
        return jsonify({
            "message": "Account not found",
            "response_status": False
        }), 404

    def get_account_by_email(email):
        account = accounts_collection.find_one({"email": email})
        if account:
            # Convert _id to string to make it JSON serializable
            account["_id"] = str(account["_id"])
        return account
    
    def verify_password(stored_password, provided_password):
        return check_password_hash(stored_password, provided_password)
        
    def check_existing_accounts():
        return accounts_collection.count_documents({})
