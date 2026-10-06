"""
FemCare AI - Personalized Wellness Recommendation Engine

This module combines the user's saved wellness profile and ML risk
estimates into explainable, preference-aware wellness suggestions.

The recommendations are for wellness support and awareness only.
They are not medical diagnosis or treatment instructions.
"""


def build_wellness_plan(profile, predictions, meal_plan=None):
    profile = profile or {}
    predictions = predictions or {}

    def high_risk(name):
        return (
            (predictions.get(f"{name}_prediction") or 0) == 1
            or (predictions.get(f"{name}_percentage") or 0) >= 50
        )

    flags = {
        "diabetes": high_risk("diabetes"),
        "pcos": high_risk("pcos"),
        "anemia": high_risk("anemia"),
        "thyroid": high_risk("thyroid"),
    }

    bmi = float(profile.get("bmi") or 0)
    cycle = int(profile.get("cycle_length") or 28)
    stress_focus = []
    movement = []
    hydration = "Aim for regular water intake throughout the day."

    if bmi >= 25:
        movement.append("Take a 20–30 minute comfortable walk or other moderate movement.")
    else:
        movement.append("Aim for a short daily walk and gentle movement.")

    if flags["pcos"]:
        movement.append("Add gentle yoga or mobility work and keep movement consistent.")
        stress_focus.append("Try 5–10 minutes of breathing or meditation.")

    if flags["diabetes"]:
        movement.append("Break up long sitting periods with short movement breaks.")
        hydration = "Keep water nearby and choose water instead of sugary drinks."

    if flags["anemia"]:
        movement.append("Choose comfortable, low-to-moderate activity and rest if you feel unusually tired or dizzy.")

    if flags["thyroid"]:
        stress_focus.append("Keep a regular sleep and relaxation routine.")

    if not stress_focus:
        stress_focus.append("Try 5 minutes of breathing, meditation, or another calming activity.")

    cycle_note = ""
    if cycle >= 35:
        cycle_note = "Your cycle is longer than the typical 21–35 day range; continue tracking your cycle and symptoms."

    nutrition = []
    if flags["anemia"]:
        nutrition.append("Prioritize iron-rich foods and pair plant sources with vitamin-C-rich foods.")
    if flags["pcos"]:
        nutrition.append("Prefer balanced meals with protein, vegetables and high-fibre carbohydrates.")
    if flags["diabetes"]:
        nutrition.append("Prefer fibre-rich meals and limit added-sugar foods and drinks.")
    if flags["thyroid"]:
        nutrition.append("Keep meals balanced with protein, vegetables and whole foods.")
    if not nutrition:
        nutrition.append("Choose balanced meals with vegetables, protein, whole grains and regular hydration.")

    return {
        "flags": flags,
        "nutrition": nutrition,
        "movement": movement[:3],
        "stress": stress_focus[:2],
        "hydration": hydration,
        "cycle_note": cycle_note,
        "meal_plan": meal_plan or {},
    }
