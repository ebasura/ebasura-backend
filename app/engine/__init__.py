from .database import Database

db = Database(
    '139.99.97.250',
    'ebasura',
    'kWeGKUsHM1nNIf-P',
    'monitoring_system'
)


def fetch_waste_bin_levels(bin_id):
    global db
    sql = """
    SELECT * 
    FROM waste_level
    INNER JOIN waste_type ON waste_type.waste_type_id = waste_level.waste_type_id
    WHERE waste_level.bin_id = %s
    """
    args = (bin_id,)
    rows = db.fetch(sql, args)

    if rows:
        return rows
    else:
        return []
