from flask import Blueprint, jsonify
from ..engine import fetch_waste_bin_levels

fill_level_bp = Blueprint('fill_level', __name__)


@fill_level_bp.route('/gauge', methods=['GET'])
@fill_level_bp.route('/gauge/<waste_type>', methods=['GET'])
def gauge(waste_type=None):
    if waste_type:
        data = fetch_waste_bin_levels(waste_type)

        gauge_values = {
            "recyclable_bin": int(
                next((item['current_fill_level'] for item in data if item['name'] == 'Recyclable'), 0)),
            "non_recyclable_bin": int(
                next((item['current_fill_level'] for item in data if item['name'] == 'Non-Recyclable'), 0)),
        }
        return jsonify(gauge_values)
