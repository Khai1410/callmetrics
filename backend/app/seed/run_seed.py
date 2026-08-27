import json
import os

from .. import models
from ..database import SessionLocal

SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_data.json")


def run():
    db = SessionLocal()
    try:
        with open(SEED_FILE, encoding="utf-8") as f:
            data = json.load(f)

        for cs_data in data["criteria_sets"]:
            existing = db.query(models.CriteriaSet).filter_by(code=cs_data["code"]).first()
            if existing:
                print(f"Skip existing criteria set: {cs_data['code']}")
                continue

            criteria_list = cs_data.pop("criteria")
            criteria_set = models.CriteriaSet(**cs_data)
            db.add(criteria_set)
            db.flush()

            for c_data in criteria_list:
                criterion = models.Criterion(criteria_set_id=criteria_set.id, **c_data)
                db.add(criterion)

            print(f"Seeded criteria set: {cs_data['code']} ({len(criteria_list)} criteria)")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
