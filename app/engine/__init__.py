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
    SELECT * FROM bin_fill_levels 
    INNER JOIN waste_type ON waste_type.waste_type_id = bin_fill_levels.waste_type 
    WHERE bin_fill_levels.bin_id = %s ORDER BY record_id DESC LIMIT 10;

    """
    args = (bin_id,)
    rows = db.fetch(sql, args)

    if rows:
        return rows
    else:
        return []
