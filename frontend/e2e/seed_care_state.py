#!/usr/bin/env python3
"""Seed a fresh user with a garden plant, reminders, and a light measurement.

Used for the care-tools visual verification of frontend-care-tools-redesign.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg2
import requests

API_BASE = "http://localhost:3000"
DB_DSN = (
    "host=localhost port=5432 dbname=fotosintesis "
    "user=fotosintesis password=fotosintesis"
)


def register_user() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    email = f"care-verify-{int(time.time())}-{suffix}@example.com"
    password = "password123"
    resp = requests.post(
        f"{API_BASE}/api/auth/register",
        json={"name": "Care Verify", "email": email, "password": password},
        timeout=10,
    )
    if resp.status_code != 201:
        raise SystemExit(f"register failed: {resp.status_code} {resp.text}")
    return email, password


def seed_state(email: str) -> None:
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_id = cur.fetchone()[0]

    image_id = uuid4()
    cur.execute(
        """
        INSERT INTO identification_images
            (id, user_id, storage_path, mime_type, size_bytes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s::json, %s)
        """,
        (
            str(image_id),
            user_id,
            f"identifications/{user_id}/{image_id}.jpg",
            "image/jpeg",
            12345,
            json.dumps({"filename": "seed.jpg", "bucket": "fotosintesis-local"}),
            "confirmed",
        ),
    )

    candidate_id = uuid4()
    cur.execute(
        """
        INSERT INTO identification_candidates
            (id, identification_id, common_name, suggested_scientific_name,
             confidence_label, visible_traits, possible_match_copy,
             validation_status, confirmed_at, accepted_scientific_name,
             binomial_name, taxonomic_status, family, genus, species)
        VALUES (%s, %s, %s, %s, %s, %s::json, %s, %s, now(), %s, %s, %s, %s, %s, %s)
        """,
        (
            str(candidate_id),
            str(image_id),
            "Pothos dorado",
            "Epipremnum aureum",
            "high",
            json.dumps(["hojas acorazonadas", "tallos verdes largos"]),
            "Coincidencia validada por GBIF.",
            "validated",
            "Epipremnum aureum",
            "Epipremnum aureum",
            "accepted",
            "Araceae",
            "Epipremnum",
            "Epipremnum aureum",
        ),
    )

    scientific = "Epipremnum aureum"
    cur.execute(
        """
        INSERT INTO plant_profiles
            (id, scientific_name, common_name, aliases, sections, sources, confidence, limitations)
        VALUES (%s, %s, %s, %s::json, %s::json, %s::json, %s, %s::json)
        ON CONFLICT (scientific_name) DO NOTHING
        RETURNING id
        """,
        (
            str(uuid4()),
            scientific,
            "Pothos dorado",
            json.dumps([{"name": "Pothos dorado", "language": "es"}]),
            json.dumps({}),
            json.dumps([]),
            0.9,
            json.dumps([]),
        ),
    )
    cur.execute("SELECT id FROM plant_profiles WHERE scientific_name = %s", (scientific,))
    profile_id = cur.fetchone()[0]

    plant_id = uuid4()
    cur.execute(
        """
        INSERT INTO garden_plants
            (id, user_id, profile_id, confirmed_candidate_id, nickname, location, custom_data, active_reminders)
        VALUES (%s, %s, %s, %s, %s, %s, %s::json, %s)
        """,
        (
            str(plant_id),
            user_id,
            profile_id,
            str(candidate_id),
            "Pothos del living",
            "Living room",
            json.dumps({}),
            2,
        ),
    )

    now = datetime.now(timezone.utc)
    for offset_days, action, recurrence, justification in [
        (2, "Riego", "weekly", "Sustrato seco al tacto, hojas firmes."),
        (5, "Fertilizante", "monthly", "Etapa de crecimiento activo, requiere nutrientes."),
    ]:
        cur.execute(
            """
            INSERT INTO reminders
                (id, user_id, garden_plant_id, action, due_at, recurrence, status, suggestion_justification)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                user_id,
                str(plant_id),
                action,
                (now + timedelta(days=offset_days)).replace(microsecond=0),
                recurrence,
                "pending",
                justification,
            ),
        )

    cur.execute(
        """
        INSERT INTO light_measurements
            (id, user_id, garden_plant_id, classification, lux, reliability, measured_at, source, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::json)
        """,
        (
            str(uuid4()),
            user_id,
            str(plant_id),
            "media",
            1200.0,
            "low",
            now - timedelta(hours=3),
            "manual",
            json.dumps({"manualLabel": "Media"}),
        ),
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded user_id={user_id} plant_id={plant_id}")


def main() -> None:
    email, password = register_user()
    seed_state(email)
    print(f"EMAIL={email}")
    print(f"PASSWORD={password}")


if __name__ == "__main__":
    main()
