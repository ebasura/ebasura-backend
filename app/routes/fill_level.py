from flask import Blueprint, jsonify
from ..engine import fetch_waste_bin_levels
import numpy as np
fill_level_bp = Blueprint('fill_level', __name__)

@fill_level_bp.route('/gauge', methods=['GET'])
@fill_level_bp.route('/gauge/<waste_type>', methods=['GET'])
def gauge(waste_type=None):
    if waste_type:
        data = fetch_waste_bin_levels(waste_type)

        # Calculate median fill level for recyclable and non-recyclable bins
        recyclable_levels = [item['current_fill_level'] for item in data if item['name'] == 'Recyclable']
        non_recyclable_levels = [item['current_fill_level'] for item in data if item['name'] == 'Non-Recyclable']

        recyclable_median = int(np.median(recyclable_levels)) if recyclable_levels else 0
        non_recyclable_median = int(np.median(non_recyclable_levels)) if non_recyclable_levels else 0

        gauge_values = {
            "recyclable_bin": recyclable_median,
            "non_recyclable_bin": non_recyclable_median
        }
        return jsonify(gauge_values)