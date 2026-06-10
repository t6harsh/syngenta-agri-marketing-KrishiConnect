"""
Analytics Engine
=================
Computes real conversion attribution and campaign performance metrics
from the provided datasets. No simulated KPIs — everything is computed
from actual POS, WhatsApp, digital funnel, and grower scan data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, Any, List

from backend.data_loader import get_data_store


class AnalyticsEngine:
    """Computes campaign performance and conversion attribution from real data."""

    def __init__(self):
        self.store = get_data_store()

    @staticmethod
    def _resolve_column(df: pd.DataFrame, names: List[str]) -> str:
        """Return the first matching column name, allowing minor schema variants."""
        lookup = {str(col).strip().lower(): col for col in df.columns}
        for name in names:
            match = lookup.get(name.lower())
            if match is not None:
                return match
        return ""

    @staticmethod
    def _truthy_series(df: pd.DataFrame, col: str) -> pd.Series:
        """Convert a boolean-like column to a bool series; missing columns are false."""
        if not col or col not in df.columns:
            return pd.Series(False, index=df.index)
        true_values = {"true", "1", "yes", "y", "delivered", "opened", "clicked"}
        return df[col].apply(lambda x: str(x).strip().lower() in true_values)

    @staticmethod
    def _empty_whatsapp_metrics(missing_columns: List[str] = None) -> Dict[str, Any]:
        result = {
            "total_messages": 0,
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "delivery_rate": 0,
            "open_rate": 0,
            "click_rate": 0,
            "by_product": {},
        }
        if missing_columns:
            result["missing_columns"] = missing_columns
        return result

    def get_whatsapp_funnel_metrics(self) -> Dict[str, Any]:
        """Compute real open/click/delivery rates from WhatsApp log."""
        wa = self.store.whatsapp_log.copy()

        if wa.empty:
            return self._empty_whatsapp_metrics()

        delivered_col = self._resolve_column(
            wa, ["delivered_status", "delivered", "delivery_status", "is_delivered"]
        )
        opened_col = self._resolve_column(
            wa, ["opened_status", "opened", "open_status", "read_status", "is_opened"]
        )
        clicked_col = self._resolve_column(
            wa, ["clicked_status", "clicked", "click_status", "is_clicked"]
        )
        product_col = self._resolve_column(
            wa,
            ["campaign_product", "product", "product_name", "sku_name", "campaign_sku"],
        )

        total = len(wa)
        delivered_series = self._truthy_series(wa, delivered_col)
        opened_series = self._truthy_series(wa, opened_col)
        clicked_series = self._truthy_series(wa, clicked_col)
        delivered = delivered_series.sum()
        opened = opened_series.sum()
        clicked = clicked_series.sum()

        # By product
        by_product = {}
        if product_col:
            products = wa[product_col].fillna("unknown").unique()
        else:
            products = ["all"]

        for product in products:
            subset = (
                wa[wa[product_col].fillna("unknown") == product] if product_col else wa
            )
            n = len(subset)
            d = int(delivered_series.loc[subset.index].sum())
            o = int(opened_series.loc[subset.index].sum())
            c = int(clicked_series.loc[subset.index].sum())
            by_product[product] = {
                "sent": int(n),
                "delivered": int(d),
                "opened": int(o),
                "clicked": int(c),
                "delivery_rate": round(d / n, 4) if n > 0 else 0,
                "open_rate": round(o / d, 4) if d > 0 else 0,
                "click_rate": round(c / o, 4) if o > 0 else 0,
                "ctr_overall": round(c / n, 4) if n > 0 else 0,
            }

        missing_columns = [
            name
            for name, col in {
                "delivered_status": delivered_col,
                "opened_status": opened_col,
                "clicked_status": clicked_col,
            }.items()
            if not col
        ]

        result = {
            "total_messages": int(total),
            "delivered": int(delivered),
            "opened": int(opened),
            "clicked": int(clicked),
            "delivery_rate": round(delivered / total, 4) if total else 0,
            "open_rate": round(opened / delivered, 4) if delivered else 0,
            "click_rate": round(clicked / opened, 4) if opened else 0,
            "by_product": by_product,
        }
        if missing_columns:
            result["missing_columns"] = missing_columns
        return result

    def get_digital_funnel_metrics(self) -> Dict[str, Any]:
        """Aggregate digital funnel performance by campaign."""
        df = self.store.digital_funnel.copy()

        campaigns = {}
        for cid in df["campaign_id"].unique():
            subset = df[df["campaign_id"] == cid]
            crop = subset["campaign_crop"].iloc[0]
            product = subset["campaign_product"].iloc[0]
            total_imps = int(subset["social_post_impression"].sum())
            total_visits = int(subset["landing_page_visits"].sum())
            total_leads = int(subset["lead_form_submission"].sum())

            # Weekly trend
            weekly_trend = []
            for _, row in subset.sort_values("week_start_date").iterrows():
                weekly_trend.append(
                    {
                        "week": row["week_start_date"].strftime("%Y-%m-%d"),
                        "impressions": int(row["social_post_impression"]),
                        "visits": int(row["landing_page_visits"]),
                        "leads": int(row["lead_form_submission"]),
                    }
                )

            campaigns[cid] = {
                "campaign_crop": crop,
                "campaign_product": product,
                "total_impressions": total_imps,
                "total_visits": total_visits,
                "total_leads": total_leads,
                "impression_to_visit_rate": (
                    round(total_visits / total_imps, 4) if total_imps else 0
                ),
                "visit_to_lead_rate": (
                    round(total_leads / total_visits, 4) if total_visits else 0
                ),
                "overall_conversion": (
                    round(total_leads / total_imps, 6) if total_imps else 0
                ),
                "weeks": len(subset),
                "weekly_trend": weekly_trend,
            }

        return {"campaigns": campaigns}

    def get_conversion_attribution(self) -> Dict[str, Any]:
        """
        Attribution: correlate WhatsApp campaigns with downstream product scans and POS.
        This is the core Campaign-to-Action metric.
        """
        store = self.store
        wa = store.whatsapp_log.copy()
        growers = store.growers.copy()

        if wa.empty or growers.empty:
            return {
                "total_messages": 0,
                "total_clicked": 0,
                "total_converted_scan": 0,
                "campaign_to_action_rate": 0,
                "click_to_scan_rate": 0,
                "by_crop": {},
            }

        clicked_col = self._resolve_column(
            wa, ["clicked_status", "clicked", "click_status", "is_clicked"]
        )
        sent_date_col = self._resolve_column(
            wa, ["message_sent_date", "sent_date", "campaign_date", "created_at"]
        )
        crop_col = self._resolve_column(wa, ["campaign_crop", "crop"])

        required_wa = ["grower_id"]
        if (
            not all(col in wa.columns for col in required_wa)
            or not clicked_col
            or not sent_date_col
        ):
            return {
                "total_messages": int(len(wa)),
                "total_clicked": int(self._truthy_series(wa, clicked_col).sum()),
                "total_converted_scan": 0,
                "campaign_to_action_rate": 0,
                "click_to_scan_rate": 0,
                "by_crop": {},
                "missing_columns": [
                    col
                    for col, present in {
                        "grower_id": "grower_id" in wa.columns,
                        "clicked_status": bool(clicked_col),
                        "message_sent_date": bool(sent_date_col),
                    }.items()
                    if not present
                ],
            }

        # Join WhatsApp messages with grower product scans
        grower_cols = [
            col
            for col in [
                "grower_id",
                "product_scan",
                "product_name",
                "product_scan_datetime",
                "tehsil",
                "crop",
            ]
            if col in growers.columns
        ]
        wa_grower = wa.merge(growers[grower_cols], on="grower_id", how="left")

        # Convert dates to check attribution window
        wa_grower["msg_date"] = pd.to_datetime(
            wa_grower[sent_date_col], errors="coerce"
        )
        if "product_scan_datetime" in wa_grower.columns:
            wa_grower["scan_date"] = pd.to_datetime(
                wa_grower["product_scan_datetime"], errors="coerce"
            )
        else:
            wa_grower["scan_date"] = pd.NaT

        # Clicked AND scanned within 14 days AFTER the message
        wa_grower["clicked"] = self._truthy_series(wa_grower, clicked_col)

        # Valid scan condition: happened, and occurred between msg_date and msg_date + 14 days
        # Use pandas isnull() to safely handle NaT
        product_scan = self._truthy_series(wa_grower, "product_scan")
        wa_grower["valid_scan"] = (
            product_scan
            & ~wa_grower["scan_date"].isnull()
            & (wa_grower["scan_date"] >= wa_grower["msg_date"])
            & (wa_grower["scan_date"] <= wa_grower["msg_date"] + timedelta(days=14))
        )

        total_messages = len(wa_grower)
        total_clicked = int(wa_grower["clicked"].sum())
        total_scanned_after_msg = int(
            (wa_grower["clicked"] & wa_grower["valid_scan"]).sum()
        )

        # Campaign-to-action rate
        cta_rate = (
            round(total_scanned_after_msg / total_messages, 4) if total_messages else 0
        )
        click_to_scan = (
            round(total_scanned_after_msg / total_clicked, 4) if total_clicked else 0
        )

        # By crop
        by_crop = {}
        if crop_col and crop_col in wa_grower.columns:
            crop_series = wa_grower[crop_col]
        elif "crop" in wa_grower.columns:
            crop_series = wa_grower["crop"]
        else:
            crop_series = pd.Series("unknown", index=wa_grower.index)

        for crop in crop_series.fillna("unknown").unique():
            subset = wa_grower[crop_series.fillna("unknown") == crop]
            n = len(subset)
            cl = int(subset["clicked"].sum())
            sc = int((subset["clicked"] & subset["valid_scan"]).sum())
            by_crop[crop] = {
                "messages": int(n),
                "clicked": cl,
                "scanned_after_click": sc,
                "campaign_to_action_rate": round(sc / n, 4) if n else 0,
            }

        return {
            "total_messages": total_messages,
            "total_clicked": total_clicked,
            "total_converted_scan": total_scanned_after_msg,
            "campaign_to_action_rate": cta_rate,
            "click_to_scan_rate": click_to_scan,
            "by_crop": by_crop,
        }

    def get_pos_trends(self, sku_name: str = None, state: str = None) -> Dict[str, Any]:
        """Get POS sales trends by week, optionally filtered."""
        pos = self.store.retailer_pos.copy()

        if sku_name:
            pos = pos[pos["sku_name"] == sku_name]
        if state:
            # Join with retailers to get state
            retailers = self.store.retailers[["retailer_id", "state"]]
            pos = pos.merge(retailers, on="retailer_id", how="left")
            pos = pos[pos["state"] == state]

        pos["week"] = (
            pos["transaction_date"].dt.to_period("W").apply(lambda x: x.start_time)
        )
        weekly = (
            pos.groupby("week")
            .agg(
                total_qty=("sku_qty", "sum"),
                total_revenue=(
                    "sku_price",
                    lambda x: (x * pos.loc[x.index, "sku_qty"]).sum(),
                ),
                transaction_count=("transaction_id", "nunique"),
            )
            .reset_index()
        )

        weekly_data = []
        for _, row in weekly.sort_values("week").iterrows():
            weekly_data.append(
                {
                    "week": row["week"].strftime("%Y-%m-%d"),
                    "total_qty": int(row["total_qty"]),
                    "total_revenue": round(float(row["total_revenue"]), 2),
                    "transactions": int(row["transaction_count"]),
                }
            )

        return {
            "filter_sku": sku_name,
            "filter_state": state,
            "total_weeks": len(weekly_data),
            "weekly_data": weekly_data,
        }

    def get_inventory_health(self) -> Dict[str, Any]:
        """Compute current inventory health: out-of-stock rates by product and region."""
        inv = self.store.retailer_inventory.copy()
        latest_week = inv["week_end_date"].max()
        current = inv[inv["week_end_date"] == latest_week]

        # Join with retailer locations
        retailers = self.store.retailers[["retailer_id", "state", "district", "tehsil"]]
        current = current.merge(retailers, on="retailer_id", how="left")

        # By SKU
        by_sku = {}
        for sku in current["sku_name"].unique():
            subset = current[current["sku_name"] == sku]
            total_retailers = len(subset)
            out_of_stock = int((subset["sku_qty"] == 0).sum())
            avg_stock = round(subset["sku_qty"].mean(), 1)
            by_sku[sku] = {
                "retailers_carrying": total_retailers,
                "out_of_stock_count": out_of_stock,
                "out_of_stock_rate": (
                    round(out_of_stock / total_retailers, 4) if total_retailers else 0
                ),
                "avg_stock_qty": avg_stock,
            }

        # By state
        by_state = {}
        for state in current["state"].unique():
            subset = current[current["state"] == state]
            total = len(subset)
            oos = int((subset["sku_qty"] == 0).sum())
            by_state[state] = {
                "total_sku_retailer_combos": total,
                "out_of_stock": oos,
                "oos_rate": round(oos / total, 4) if total else 0,
            }

        return {
            "snapshot_week": latest_week.strftime("%Y-%m-%d"),
            "by_sku": by_sku,
            "by_state": by_state,
        }

    def get_field_activity_summary(self) -> Dict[str, Any]:
        """Summarize rep field activities from visit logs."""
        visits = self.store.retailer_visits.copy()

        by_type = visits["visit_type"].value_counts().to_dict()
        by_product = visits["product_recommended"].value_counts().to_dict()

        # Monthly trend
        visits["month"] = (
            visits["visit_date"].dt.to_period("M").apply(lambda x: x.start_time)
        )
        monthly = visits.groupby("month").size().reset_index(name="visit_count")
        monthly_data = [
            {"month": row["month"].strftime("%Y-%m"), "visits": int(row["visit_count"])}
            for _, row in monthly.sort_values("month").iterrows()
        ]

        return {
            "total_visits": len(visits),
            "by_type": {k: int(v) for k, v in by_type.items()},
            "by_product": {k: int(v) for k, v in by_product.items()},
            "monthly_trend": monthly_data,
        }

    def get_campaign_revenue_impact(self) -> Dict[str, Any]:
        """
        Estimate revenue impact of WhatsApp campaigns by comparing POS sales
        in the 4 weeks before vs 4 weeks after each (product, state) campaign
        launch. Uses real transaction data — no simulation.
        """
        store = self.store
        wa = store.whatsapp_log.copy()
        pos = store.retailer_pos.copy()
        growers = store.growers.copy()
        retailers = store.retailers.copy()

        if wa.empty or pos.empty or growers.empty or retailers.empty:
            return {
                "total_attributed_revenue": 0,
                "by_product": {},
                "by_state": {},
                "attribution_window_days": 28,
            }

        # Resolve columns
        product_col = self._resolve_column(
            wa,
            [
                "campaign_product",
                "product",
                "product_name",
                "sku_name",
                "campaign_sku",
            ],
        )
        sent_date_col = self._resolve_column(
            wa,
            [
                "message_sent_date",
                "sent_date",
                "campaign_date",
                "created_at",
            ],
        )

        # Join WhatsApp with growers to get state
        wa_grower = wa.merge(
            growers[["grower_id", "state"]], on="grower_id", how="left"
        )
        wa_grower["msg_date"] = pd.to_datetime(
            wa_grower[sent_date_col], errors="coerce"
        )
        wa_grower = wa_grower.dropna(subset=["msg_date", "state"])

        # Join POS with retailers for state
        pos_retailer = pos.merge(
            retailers[["retailer_id", "state"]], on="retailer_id", how="left"
        )
        pos_retailer["txn_date"] = pd.to_datetime(
            pos_retailer["transaction_date"], errors="coerce"
        )
        pos_retailer["revenue"] = (
            pos_retailer["sku_qty"] * pos_retailer["sku_price"]
        )
        pos_retailer["week"] = (
            pos_retailer["txn_date"]
            .dt.to_period("W")
            .apply(lambda x: x.start_time)
        )
        pos_retailer = pos_retailer.dropna(subset=["state"])

        # Analyze each (product, state) pair
        by_product = {}
        by_state = {}
        total_attributed = 0.0

        for (product, state), msgs in wa_grower.groupby([product_col, "state"]):
            first_campaign = msgs["msg_date"].min()

            state_pos = pos_retailer[
                (pos_retailer["sku_name"] == product)
                & (pos_retailer["state"] == state)
            ]
            if state_pos.empty:
                continue

            weekly = (
                state_pos.groupby("week")
                .agg(total_revenue=("revenue", "sum"))
                .reset_index()
            )

            # 4-week window before vs after first campaign message
            pre_start = first_campaign - timedelta(weeks=4)
            pre_end = first_campaign - timedelta(days=1)
            post_start = first_campaign
            post_end = first_campaign + timedelta(weeks=4) - timedelta(days=1)

            pre_weeks = weekly[
                (weekly["week"] >= pre_start) & (weekly["week"] <= pre_end)
            ]
            post_weeks = weekly[
                (weekly["week"] >= post_start) & (weekly["week"] <= post_end)
            ]

            pre_avg = (
                pre_weeks["total_revenue"].mean() if len(pre_weeks) > 0 else 0
            )
            post_avg = (
                post_weeks["total_revenue"].mean() if len(post_weeks) > 0 else 0
            )

            uplift = (post_avg / pre_avg - 1) if pre_avg > 0 else 0
            attributed = (
                (post_avg - pre_avg) * len(post_weeks)
                if len(post_weeks) > 0
                else 0
            )
            total_attributed += attributed

            entry = {
                "campaign_messages": int(len(msgs)),
                "first_campaign_date": first_campaign.strftime("%Y-%m-%d"),
                "pre_avg_weekly_revenue": round(pre_avg, 2),
                "post_avg_weekly_revenue": round(post_avg, 2),
                "attributed_revenue": round(attributed, 2),
                "uplift_pct": round(uplift, 4),
            }

            if product not in by_product:
                by_product[product] = {
                    "campaign_messages": 0,
                    "states": {},
                    "total_attributed": 0.0,
                }
            by_product[product]["campaign_messages"] += int(len(msgs))
            by_product[product]["states"][state] = entry
            by_product[product]["total_attributed"] += attributed

            by_state[state] = by_state.get(state, 0) + attributed

        for p in by_product:
            by_product[p]["total_attributed"] = round(
                by_product[p]["total_attributed"], 2
            )

        return {
            "total_attributed_revenue": round(total_attributed, 2),
            "by_product": dict(
                sorted(
                    by_product.items(),
                    key=lambda x: x[1]["total_attributed"],
                    reverse=True,
                )
            ),
            "by_state": {
                k: round(v, 2)
                for k, v in sorted(
                    by_state.items(), key=lambda x: x[1], reverse=True
                )
            },
            "attribution_window_days": 28,
        }

    def get_segment_engagement(self) -> Dict[str, Any]:
        """
        Rank segments by engagement score computed from WhatsApp logs.
        Engagement Score = 0.5 × Open Rate (opened/delivered) + 0.5 × Click Rate (clicked/delivered).
        Grouped by (crop, stage, state) for actionable marketing insights.
        """
        store = self.store
        wa = store.whatsapp_log.copy()
        growers = store.growers.copy()

        if wa.empty or growers.empty:
            return {"segments": [], "total_segments": 0, "top_performing": [], "bottom_performing": []}

        # Resolve WhatsApp columns
        delivered_col = self._resolve_column(
            wa, ["delivered_status", "delivered", "delivery_status", "is_delivered"]
        )
        opened_col = self._resolve_column(
            wa, ["opened_status", "opened", "open_status", "read_status", "is_opened"]
        )
        clicked_col = self._resolve_column(
            wa, ["clicked_status", "clicked", "click_status", "is_clicked"]
        )
        crop_col_wa = self._resolve_column(wa, ["campaign_crop", "crop"])

        # Join WhatsApp with growers to get state, language, device, crop
        grower_cols = [c for c in ["grower_id", "state", "crop", "language", "device_type"] if c in growers.columns]
        wa_grower = wa.merge(growers[grower_cols], on="grower_id", how="left")

        # Compute boolean series
        wa_grower["_delivered"] = self._truthy_series(wa_grower, delivered_col)
        wa_grower["_opened"] = self._truthy_series(wa_grower, opened_col)
        wa_grower["_clicked"] = self._truthy_series(wa_grower, clicked_col)

        # Precompute current stage for each unique grower
        REF_DATE = date(2026, 2, 1)
        gid_stage = {}
        for gid in wa_grower["grower_id"].unique():
            stage = store.get_grower_current_stage(gid, REF_DATE)
            gid_stage[gid] = stage if stage else "unknown"
        wa_grower["current_stage"] = wa_grower["grower_id"].map(gid_stage)

        # Use campaign_crop if available, else fall back to grower crop
        if crop_col_wa and crop_col_wa in wa_grower.columns:
            wa_grower["segment_crop"] = wa_grower[crop_col_wa].fillna("unknown")
        elif "crop" in wa_grower.columns:
            wa_grower["segment_crop"] = wa_grower["crop"].fillna("unknown")
        else:
            wa_grower["segment_crop"] = "unknown"

        wa_grower["segment_state"] = wa_grower.get("state", pd.Series("unknown", index=wa_grower.index)).fillna("unknown")
        wa_grower["segment_stage"] = wa_grower["current_stage"].fillna("unknown")

        # Group by (crop, stage, state) and compute metrics
        grouped = wa_grower.groupby(["segment_crop", "segment_stage", "segment_state"])

        segments_raw = []
        for (crop, stage, state), grp in grouped:
            n = len(grp)
            d = int(grp["_delivered"].sum())
            o = int(grp["_opened"].sum())
            c = int(grp["_clicked"].sum())
            unique_growers = int(grp["grower_id"].nunique())

            delivery_rate = round(d / n, 4) if n > 0 else 0
            open_rate = round(o / d, 4) if d > 0 else 0
            click_rate = round(c / d, 4) if d > 0 else 0
            engagement = round(0.5 * open_rate + 0.5 * click_rate, 4)

            segments_raw.append({
                "crop": crop,
                "stage": stage,
                "state": state,
                "grower_count": unique_growers,
                "messages_sent": int(n),
                "delivered": d,
                "opened": o,
                "clicked": c,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "engagement_score": engagement,
            })

        # Sort descending by engagement
        segments_raw.sort(key=lambda s: s["engagement_score"], reverse=True)

        # Assign rank
        for i, s in enumerate(segments_raw, 1):
            s["rank"] = i

        top_performing = segments_raw[:10]
        bottom_performing = segments_raw[-10:] if len(segments_raw) >= 10 else segments_raw.copy()
        # Reverse bottom so worst is first
        bottom_performing.reverse()

        return {
            "segments": segments_raw,
            "total_segments": len(segments_raw),
            "top_performing": top_performing,
            "bottom_performing": bottom_performing,
        }

    def get_optimal_send_times(self) -> Dict[str, Any]:
        """
        Analyze WhatsApp logs to find the best day-of-week for each
        (state, crop, device_type) segment based on open rate.
        """
        store = self.store
        wa = store.whatsapp_log.copy()
        growers = store.growers.copy()

        if wa.empty or growers.empty:
            return {"segments": [], "total_segments": 0}

        DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        delivered_col = self._resolve_column(
            wa, ["delivered_status", "delivered", "delivery_status", "is_delivered"]
        )
        opened_col = self._resolve_column(
            wa, ["opened_status", "opened", "open_status", "read_status", "is_opened"]
        )
        sent_date_col = self._resolve_column(
            wa, ["message_sent_date", "sent_date", "campaign_date", "created_at"]
        )

        grower_cols = [c for c in ["grower_id", "state", "crop", "device_type"] if c in growers.columns]
        wa_grower = wa.merge(growers[grower_cols], on="grower_id", how="left")

        wa_grower["_delivered"] = self._truthy_series(wa_grower, delivered_col)
        wa_grower["_opened"] = self._truthy_series(wa_grower, opened_col)

        # Parse date and extract day of week
        wa_grower["msg_date"] = pd.to_datetime(wa_grower[sent_date_col], errors="coerce")
        wa_grower = wa_grower.dropna(subset=["msg_date"])
        wa_grower["day_of_week"] = wa_grower["msg_date"].dt.dayofweek

        wa_grower["seg_state"] = wa_grower.get("state", pd.Series("unknown", index=wa_grower.index)).fillna("unknown")
        wa_grower["seg_crop"] = wa_grower.get("crop", pd.Series("unknown", index=wa_grower.index)).fillna("unknown")
        wa_grower["seg_device"] = wa_grower.get("device_type", pd.Series("unknown", index=wa_grower.index)).fillna("unknown")

        # Build per-segment optimal day analysis
        segments_map = {}
        for (state, crop, device), grp in wa_grower.groupby(["seg_state", "seg_crop", "seg_device"]):
            total_msgs = len(grp)

            # Compute per-day metrics
            day_metrics = []
            for day in range(7):
                day_grp = grp[grp["day_of_week"] == day]
                n = len(day_grp)
                if n == 0:
                    continue
                d = int(day_grp["_delivered"].sum())
                o = int(day_grp["_opened"].sum())
                day_metrics.append({
                    "day": DAYS[day],
                    "day_index": day,
                    "messages": int(n),
                    "delivered": d,
                    "opened": o,
                    "delivery_rate": round(d / n, 4) if n else 0,
                    "open_rate": round(o / d, 4) if d else 0,
                })

            if not day_metrics:
                continue

            day_metrics.sort(key=lambda x: x["open_rate"], reverse=True)
            best_day = day_metrics[0]
            # Compute lift vs average
            avg_open = sum(d["open_rate"] for d in day_metrics) / len(day_metrics)
            uplift = ((best_day["open_rate"] / avg_open) - 1) if avg_open > 0 else 0

            key = f"{state}|{crop}|{device}"
            segments_map[key] = {
                "state": state,
                "crop": crop,
                "device_type": device,
                "total_messages": total_msgs,
                "days_with_data": len(day_metrics),
                "optimal_day": best_day["day"],
                "optimal_open_rate": best_day["open_rate"],
                "avg_open_rate": round(avg_open, 4),
                "uplift_vs_avg": round(uplift, 4),
                "day_details": day_metrics,
            }

        # Global weekday analysis
        global_days = []
        for day in range(7):
            day_grp = wa_grower[wa_grower["day_of_week"] == day]
            n = len(day_grp)
            if n == 0:
                continue
            d = int(day_grp["_delivered"].sum())
            o = int(day_grp["_opened"].sum())
            global_days.append({
                "day": DAYS[day],
                "day_index": day,
                "messages": int(n),
                "delivered": d,
                "opened": o,
                "delivery_rate": round(d / n, 4) if n else 0,
                "open_rate": round(o / d, 4) if d else 0,
            })
        global_days.sort(key=lambda x: x["open_rate"], reverse=True)

        segments_list = list(segments_map.values())
        segments_list.sort(key=lambda s: s["total_messages"], reverse=True)

        return {
            "total_messages_analyzed": int(len(wa_grower)),
            "total_segments": len(segments_list),
            "global_weekday_ranking": global_days,
            "segments": segments_list,
        }

    def get_business_overview(self) -> Dict[str, Any]:
        """Aggregate high-level business KPIs for the main dashboard."""
        store = self.store
        total_growers = len(store.growers)

        # Segment summary
        from backend.segmentation import SegmentationEngine
        seg_engine = SegmentationEngine()
        ref = date(2026, 2, 1)
        segments = seg_engine.build_segments(ref)
        total_segments = len(segments)
        top_segments = sorted(
            segments, key=lambda s: s["grower_count"], reverse=True
        )[:5]

        # WhatsApp funnel KPIs
        wa = self.get_whatsapp_funnel_metrics()

        # Conversion KPIs
        conv = self.get_conversion_attribution()

        # Grower distribution
        growers = store.growers
        by_state = growers["state"].value_counts().to_dict()
        by_crop = growers["crop"].value_counts().to_dict()
        by_device = growers["device_type"].value_counts().to_dict()

        return {
            "total_growers": int(total_growers),
            "total_segments": int(total_segments),
            "total_campaigns_sent": int(wa.get("total_messages", 0)),
            "overall_delivery_rate": round(wa.get("delivery_rate", 0), 4),
            "overall_open_rate": round(wa.get("open_rate", 0), 4),
            "overall_click_rate": round(wa.get("click_rate", 0), 4),
            "campaign_to_action_rate": round(
                conv.get("campaign_to_action_rate", 0), 4
            ),
            "click_to_scan_rate": round(conv.get("click_to_scan_rate", 0), 4),
            "total_converted_scans": int(conv.get("total_converted_scan", 0)),
            "top_segments": [
                {
                    "segment_id": s["segment_id"],
                    "crop": s["crop"],
                    "stage": s["stage"],
                    "state": s["state"],
                    "grower_count": s["grower_count"],
                }
                for s in top_segments
            ],
            "by_state": {k: int(v) for k, v in by_state.items()},
            "by_crop": {k: int(v) for k, v in by_crop.items()},
            "by_channel": {
                str(k).lower(): int(v) for k, v in by_device.items()
            },
        }
