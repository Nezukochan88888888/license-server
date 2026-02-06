from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import datetime
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# Supabase Configuration
# These will be set in Vercel Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_db():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return jsonify({"status": "active", "service": "Quiz License Server"}), 200

@app.route('/activate', methods=['POST'])
def activate_license():
    data = request.json
    key = data.get('key')
    hwid = data.get('hwid')

    if not key or not hwid:
        return jsonify({"error": "Missing key or hwid"}), 400

    db = get_db()
    if not db:
        return jsonify({"error": "Server misconfiguration"}), 500

    # 1. Check if key exists
    try:
        response = db.table('licenses').select("*").eq('key', key).execute()
        
        if not response.data:
            return jsonify({"error": "Invalid License Key"}), 404
        
        license_data = response.data[0]

        # 2. Check status
        if license_data['status'] in ['banned', 'refunded']:
             return jsonify({"error": "License is banned or refunded"}), 403

        # 3. HWID Logic
        if license_data['hwid'] is None:
            # First time activation! Bind it.
            db.table('licenses').update({
                "hwid": hwid,
                "status": "active",
                "activated_at": datetime.datetime.utcnow().isoformat()
            }).eq('key', key).execute()
            
            return jsonify({
                "success": True, 
                "message": "Activated successfully",
                "type": license_data.get('type', 'standard')
            }), 200
            
        elif license_data['hwid'] == hwid:
            # Re-activation on same PC (Allowed)
            return jsonify({
                "success": True, 
                "message": "Welcome back",
                "type": license_data.get('type', 'standard')
            }), 200
            
        else:
             # Key used on different PC
             return jsonify({"error": "License already used on another machine"}), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check', methods=['POST'])
def check_license():
    """Silent background check"""
    data = request.json
    key = data.get('key')
    hwid = data.get('hwid')
    
    db = get_db()
    if not db: 
        return jsonify({"valid": False}), 500
        
    try:
        response = db.table('licenses').select("*").eq('key', key).execute()
        if not response.data:
            return jsonify({"valid": False, "reason": "not_found"}), 200
            
        lic = response.data[0]
        
        if lic['status'] != 'active':
             return jsonify({"valid": False, "reason": "status_invalid"}), 200
             
        if lic['hwid'] != hwid:
             return jsonify({"valid": False, "reason": "hwid_mismatch"}), 200
             
        return jsonify({"valid": True, "type": lic.get('type', 'standard')}), 200
        
    except:
        return jsonify({"valid": False, "reason": "error"}), 200
