"""
Segmentation Engine
====================
Builds micro-segments from real grower data along multiple dimensions:
crop, stage, language, device, geography, engagement history.
"""

import pandas as pd
from datetime import date
from typing import List, Dict, Any
from backend.data_loader import get_data_store

# ──────────────────────────────────────────────────────
# Product-Crop mapping derived from actual dataset
# ──────────────────────────────────────────────────────
CROP_PRODUCT_MAP = {
    "wheat": ["Topik 15 WP", "Tilt 250 EC", "Axial 50 EC"],
    "mustard": ["Score 250 EC", "Tilt 250 EC"],
    "chickpea": ["Actara 25 WG", "Amistar 250 SC"],
    "potato": ["Kavach 75 WP", "Amistar 250 SC"],
    "barley": ["Tilt 250 EC", "Axial 50 EC"],
    "lentil": ["Actara 25 WG", "Score 250 EC"],
    "safflower": ["Score 250 EC", "Amistar 250 SC"],
    "maize": ["Cruiser 350 FS", "Actara 25 WG"],
    "cumin": ["Score 250 EC", "Kavach 75 WP"],
}

# Stage-based threat profiles (real agronomic knowledge)
STAGE_THREAT_MAP = {
    "sowing": {"threat": "Seed-borne diseases", "category": "seed_treatment"},
    "tillering": {"threat": "Yellow rust / Aphid infestation", "category": "fungicide"},
    "flowering": {
        "threat": "Powdery mildew / Pod borer",
        "category": "fungicide_insecticide",
    },
    "harvested": {"threat": None, "category": None},
    "unknown": {"threat": "General crop protection", "category": "general"},
}


class SegmentationEngine:
    """Creates multi-dimensional micro-segments from real grower data."""

    def __init__(self):
        self.store = get_data_store()

    def build_segments(self, reference_date: date = None) -> List[Dict[str, Any]]:
        """
        Build a list of micro-segments.
        Each segment = unique combination of (crop, stage, state, language, device_type).
        """
        if reference_date is None:
            reference_date = date.today()

        growers_df = self.store.growers.copy()

        # Compute current stage for each grower
        current_stages = []
        for _, row in growers_df.iterrows():
            stage = self.store.get_grower_current_stage(
                row["grower_id"], reference_date
            )
            current_stages.append(stage)
        growers_df["current_stage"] = current_stages

        # Group by segment dimensions
        segment_keys = ["crop", "current_stage", "state", "language", "device_type"]
        grouped = growers_df.groupby(segment_keys, dropna=False)

        segments = []
        for keys, group in grouped:
            crop, stage, state, language, device = keys
            threat_info = STAGE_THREAT_MAP.get(stage, STAGE_THREAT_MAP["unknown"])
            products = CROP_PRODUCT_MAP.get(crop, [])

            segment = {
                "segment_id": f"{crop}_{stage}_{state}_{language}_{device}".replace(
                    " ", "_"
                ).lower(),
                "crop": crop,
                "stage": stage,
                "state": state,
                "language": language,
                "device_type": device,
                "grower_count": len(group),
                "grower_ids": group["grower_id"].tolist(),
                "avg_farm_size": round(group["grower_farm_size"].mean(), 2),
                "avg_age": round(group["grower_age"].mean(), 1),
                "threat": threat_info["threat"],
                "threat_category": threat_info["category"],
                "recommended_products": products,
                "tehsils": group["tehsil"].unique().tolist(),
            }
            segments.append(segment)

        return segments

    def build_segments_grouped(
        self,
        reference_date: date = None,
        group_by: List[str] = None,
        filters: Dict[str, str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build segments grouped by a chosen set of dimensions.
        group_by: subset of ['crop','stage','state','language','device_type'].
        filters: optional {dim: value} to pre-filter growers.
        When group_by has fewer dimensions, segments merge across the omitted ones.
        """
        if reference_date is None:
            reference_date = date.today()
        VALID_DIMS = {"crop", "stage", "state", "language", "device_type"}
        if not group_by:
            group_by = list(VALID_DIMS)
        group_by = [d for d in group_by if d in VALID_DIMS]
        if not group_by:
            group_by = ["crop"]

        growers_df = self.store.growers.copy()

        # Compute current stage for each grower
        current_stages = []
        for _, row in growers_df.iterrows():
            stage = self.store.get_grower_current_stage(row["grower_id"], reference_date)
            current_stages.append(stage)
        growers_df["current_stage"] = current_stages

        # Apply filters
        if filters:
            for dim, val in filters.items():
                if val and dim == "stage":
                    growers_df = growers_df[growers_df["current_stage"] == val]
                elif val and dim in growers_df.columns:
                    growers_df = growers_df[growers_df[dim] == val]

        if growers_df.empty:
            return []

        # Group by the chosen dimensions
        group_cols = []
        dim_map = {"crop": "crop", "stage": "current_stage", "state": "state",
                    "language": "language", "device_type": "device_type"}
        for d in group_by:
            col = dim_map.get(d)
            if col and col in growers_df.columns:
                group_cols.append(col)

        if not group_cols:
            group_cols = ["crop"]

        grouped = growers_df.groupby(group_cols, dropna=False)

        segments = []
        for keys, group in grouped:
            keys_list = keys if isinstance(keys, tuple) else [keys]
            key_dict = dict(zip(group_cols, keys_list))

            crop = key_dict.get("crop", group["crop"].mode().iloc[0] if not group["crop"].mode().empty else "unknown")
            stage = key_dict.get("current_stage", group["current_stage"].mode().iloc[0] if not group["current_stage"].mode().empty else "unknown")
            state = key_dict.get("state", group["state"].mode().iloc[0] if not group["state"].mode().empty else "unknown")
            language = key_dict.get("language", group["language"].mode().iloc[0] if not group["language"].mode().empty else "unknown")
            device = key_dict.get("device_type", group["device_type"].mode().iloc[0] if not group["device_type"].mode().empty else "unknown")

            threat_info = STAGE_THREAT_MAP.get(stage, STAGE_THREAT_MAP["unknown"])
            products = CROP_PRODUCT_MAP.get(crop, [])

            # Build segment_id from group-by dimensions only
            id_parts = []
            for d in group_by:
                val = {"crop": crop, "stage": stage, "state": state,
                       "language": language, "device_type": device}.get(d, "unknown")
                id_parts.append(str(val).replace(" ", "_").lower())
            segment_id = "_".join(id_parts)

            segment = {
                "segment_id": segment_id,
                "crop": crop,
                "stage": stage,
                "state": state,
                "language": language,
                "device_type": device,
                "group_by": group_by,
                "grower_count": len(group),
                "grower_ids": group["grower_id"].tolist(),
                "avg_farm_size": round(group["grower_farm_size"].mean(), 2),
                "avg_age": round(group["grower_age"].mean(), 1),
                "threat": threat_info["threat"],
                "threat_category": threat_info["category"],
                "recommended_products": products,
                "tehsils": group["tehsil"].unique().tolist(),
            }
            segments.append(segment)

        segments.sort(key=lambda s: s["grower_count"], reverse=True)
        return segments

    def get_grower_context(
        self, grower_id: str, reference_date: date = None
    ) -> Dict[str, Any]:
        """Build a complete context profile for a single grower."""
        if reference_date is None:
            reference_date = date.today()

        store = self.store
        grower = store.grower_index.get(grower_id)
        if not grower:
            return {"error": f"Grower {grower_id} not found"}

        stage = store.get_grower_current_stage(grower_id, reference_date)
        crop = grower.get("crop", "unknown")
        tehsil = grower.get("tehsil", "")
        threat_info = STAGE_THREAT_MAP.get(stage, STAGE_THREAT_MAP["unknown"])
        products = CROP_PRODUCT_MAP.get(crop, [])

        # Check local inventory for recommended products
        available_products = []
        for prod in products:
            inv = store.get_local_inventory(tehsil, prod)
            total_stock = int(inv["sku_qty"].sum()) if not inv.empty else 0
            available_products.append(
                {
                    "product": prod,
                    "local_stock": total_stock,
                    "in_stock": bool(total_stock > 0),
                }
            )

        # WhatsApp history
        wa_history = store.get_grower_whatsapp_history(grower_id)
        wa_summary = {
            "total_messages": int(len(wa_history)),
            "delivered": (
                int(
                    wa_history["delivered_status"]
                    .apply(lambda x: str(x).strip().lower() == "true")
                    .sum()
                )
                if not wa_history.empty
                else 0
            ),
            "opened": (
                int(
                    wa_history["opened_status"]
                    .apply(lambda x: str(x).strip().lower() == "true")
                    .sum()
                )
                if not wa_history.empty
                else 0
            ),
            "clicked": (
                int(
                    wa_history["clicked_status"]
                    .apply(lambda x: str(x).strip().lower() == "true")
                    .sum()
                )
                if not wa_history.empty
                else 0
            ),
        }

        # Channel recommendation based on device & history
        device = str(grower.get("device_type", "unknown"))
        if device == "smartphone":
            if wa_summary["opened"] > 0:
                channel = "whatsapp"
            else:
                channel = "whatsapp"  # still try, smartphone available
        elif device == "keypad":
            channel = "voice_call"
        else:
            channel = "sms"

        # If WhatsApp was delivered but never opened, downgrade
        if (
            wa_summary["total_messages"] >= 2
            and wa_summary["opened"] == 0
            and device == "smartphone"
        ):
            channel = "sms"

        context = {
            "grower_id": str(grower_id),
            "state": str(grower.get("state", "")),
            "district": str(grower.get("district", "")),
            "tehsil": str(tehsil),
            "language": str(grower.get("language", "Hindi")),
            "device_type": device,
            "age": int(grower.get("grower_age", 0)),
            "gender": str(grower.get("gender", "")),
            "farm_size_acres": float(grower.get("grower_farm_size", 0)),
            "crop": str(crop),
            "current_stage": str(stage),
            "threat": threat_info["threat"],
            "threat_category": threat_info["category"],
            "recommended_products": available_products,
            "product_scanned": str(grower.get("product_scan", "false")).strip().lower()
            == "true",
            "offline_attended": str(grower.get("offline_campaign_attended", "false"))
            .strip()
            .lower()
            == "true",
            "whatsapp_history": wa_summary,
            "recommended_channel": channel,
        }
        return context

    def get_segment_context(
        self, segment: Dict[str, Any], reference_date: date = None
    ) -> Dict[str, Any]:
        """Build aggregated context for a segment (group of growers)."""
        if reference_date is None:
            reference_date = date.today()

        store = self.store
        crop = segment.get("crop", "unknown")
        stage = segment.get("stage", "unknown")
        state = segment.get("state", "")
        language = segment.get("language", "Hindi")
        device = segment.get("device_type", "unknown")
        threat_info = STAGE_THREAT_MAP.get(stage, STAGE_THREAT_MAP["unknown"])
        products = CROP_PRODUCT_MAP.get(crop, [])

        # Aggregate inventory across tehsils in this segment
        tehsils = segment.get("tehsils", [])
        available_products = []
        for prod in products:
            total_stock = 0
            for tehsil in tehsils:
                inv = store.get_local_inventory(tehsil, prod)
                total_stock += int(inv["sku_qty"].sum()) if not inv.empty else 0
            available_products.append({
                "product": prod,
                "total_stock": total_stock,
                "in_stock": bool(total_stock > 0),
            })

        best_product = "Syngenta product"
        for p in available_products:
            if p["in_stock"]:
                best_product = p["product"]
                break
        if best_product == "Syngenta product" and available_products:
            best_product = available_products[0]["product"]

        # Channel recommendation based on device type in segment
        if device == "smartphone":
            channel = "whatsapp"
        elif device == "keypad":
            channel = "voice_call"
        else:
            channel = "sms"

        grower_count = segment.get("grower_count", 0)
        avg_farm_size = segment.get("avg_farm_size", 0)
        avg_age = segment.get("avg_age", 0)

        return {
            "segment_id": segment.get("segment_id", ""),
            "crop": crop,
            "current_stage": stage,
            "state": state,
            "district": segment.get("tehsils", [""])[0] if segment.get("tehsils") else "",
            "tehsils": tehsils,
            "language": language,
            "device_type": device,
            "grower_count": grower_count,
            "avg_farm_size_acres": avg_farm_size,
            "avg_age": avg_age,
            "threat": threat_info["threat"],
            "threat_category": threat_info["category"],
            "recommended_products": available_products,
            "product_recommended": best_product,
            "recommended_channel": channel,
        }

    def get_segment_summary(self, reference_date: date = None) -> Dict[str, Any]:
        """High-level summary statistics across all segments."""
        segments = self.build_segments(reference_date)
        total_growers = sum(s["grower_count"] for s in segments)

        by_crop = {}
        by_stage = {}
        by_channel = {}
        for s in segments:
            crop = s["crop"]
            by_crop[crop] = by_crop.get(crop, 0) + s["grower_count"]
            stage = s["stage"]
            by_stage[stage] = by_stage.get(stage, 0) + s["grower_count"]
            dev = s["device_type"]
            ch = (
                "whatsapp"
                if dev == "smartphone"
                else ("voice_call" if dev == "keypad" else "sms")
            )
            by_channel[ch] = by_channel.get(ch, 0) + s["grower_count"]

        return {
            "total_growers": total_growers,
            "total_segments": len(segments),
            "by_crop": by_crop,
            "by_stage": by_stage,
            "by_channel": by_channel,
        }
