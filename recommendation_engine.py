"""
FemCare AI - Personalized Recommendation Engine

The engine combines the saved wellness profile, ML risk estimates,
dietary restrictions and a larger recipe library to select daily meals.

Recommendations are for general wellness support and are not medical
diagnosis or treatment.
"""

from datetime import date
from recipe_data import RECIPE_LIBRARY


def _as_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _high_risk(predictions, name):
    prediction = predictions.get(f"{name}_prediction") or 0
    percentage = predictions.get(f"{name}_percentage") or 0
    return prediction == 1 or percentage >= 50


def _normalise_tokens(value):
    return {
        token.strip().lower()
        for token in str(value or "").replace(";", ",").split(",")
        if token.strip()
    }


def _food_is_blocked(recipe, preference, allergies, dislikes):
    """
    Return True when a recipe violates a saved dietary restriction.

    Allergy filtering is intentionally performed BEFORE recommendation
    scoring so an excluded food can never win the recommendation.
    """
    ingredients = " ".join(recipe.get("ingredients", [])).lower()
    allergy_text = str(allergies or "").lower()

    allergy_groups = {
        "nuts": ["almond", "walnut", "cashew", "pistachio", "hazelnut", "nut"],
        "peanuts": ["peanut", "groundnut"],
        "dairy": ["milk", "paneer", "curd", "yogurt", "yoghurt", "cheese", "ghee", "butter", "cream"],
        "gluten": ["wheat", "bread", "atta", "maida", "barley", "rye", "dalia", "broken wheat"],
        "soy": ["soy", "tofu", "soya"],
        "sesame": ["sesame", "til"],
        "seeds": ["seed", "chia", "flax", "sunflower", "pumpkin"],
    }

    selected_allergies = _normalise_tokens(allergy_text)

    for allergy, words in allergy_groups.items():
        if allergy in selected_allergies and any(word in ingredients for word in words):
            return True

    preference_lower = str(preference or "Vegetarian").strip().lower()
    recipe_diet = str(recipe.get("diet_type", "Vegetarian")).strip().lower()

    # Dietary preference is a hard filter before health scoring.
    if preference_lower == "vegetarian" and recipe_diet != "vegetarian":
        return True

    if preference_lower == "vegan":
        if recipe_diet != "vegetarian":
            return True
    elif preference_lower == "eggetarian":
        if recipe_diet not in {"vegetarian", "eggetarian"}:
            return True

    if "vegan" in preference_lower:
        if any(word in ingredients for word in [
            "milk", "paneer", "curd", "yogurt", "yoghurt",
            "cheese", "ghee", "butter", "cream"
        ]):
            return True

    # User-entered custom allergy such as other: coconut
    for part in allergy_text.split(","):
        part = part.strip()
        if part.startswith("other:"):
            custom = part.replace("other:", "", 1).strip()
            if custom and custom in ingredients:
                return True

    for dislike in _normalise_tokens(dislikes):
        if dislike and dislike in ingredients:
            return True

    return False


def _risk_flags(predictions):
    return {
        "diabetes": _high_risk(predictions, "diabetes"),
        "pcos": _high_risk(predictions, "pcos"),
        "anemia": _high_risk(predictions, "anemia"),
        "thyroid": _high_risk(predictions, "thyroid"),
    }


def _recipe_score(recipe, flags):
    tags = set(recipe.get("tags", []))
    score = 0

    # Personalised health-goal matching.
    tag_map = {
        "anemia": {"anemia", "iron_rich"},
        "pcos": {"pcos", "high_fiber", "protein"},
        "diabetes": {"diabetes", "high_fiber", "protein"},
        "thyroid": {"thyroid", "balanced", "protein"},
    }

    for condition, active in flags.items():
        if active:
            score += 5 * len(tags.intersection(tag_map[condition]))

    # General nutrition quality helps break ties.
    score += min(float(recipe.get("protein", 0)) / 5, 4)
    score += min(float(recipe.get("fiber", 0)) / 5, 3)

    return score


def build_personalized_meal_plan(profile, predictions, recommendation_date=None):
    """
    Select one recipe per meal slot from the 50+ recipe library.

    The selection changes over time while remaining deterministic for the
    same user/day. Restrictions are applied first; health/wellness tags
    are then used to score the remaining recipes.
    """
    profile = _as_dict(profile)
    predictions = _as_dict(predictions)

    preference = profile.get("diet_preference") or "Vegetarian"
    allergies = profile.get("allergies") or ""
    dislikes = profile.get("food_dislikes") or ""
    flags = _risk_flags(predictions)

    meal_slots = [
        ("breakfast", "Breakfast", "MORNING", "🍳"),
        ("snack", "Mid-Morning", "MID-MORNING", "🍎"),
        ("lunch", "Lunch", "AFTERNOON", "🥗"),
        ("evening", "Evening Snack", "EVENING", "🍵"),
        ("dinner", "Dinner", "NIGHT", "🥘"),
    ]

    chosen = []
    day_number = (
        recommendation_date.toordinal()
        if hasattr(recommendation_date, "toordinal")
        else date.today().toordinal()
    )

    for slot, label, time, icon in meal_slots:
        candidates = [
            recipe for recipe in RECIPE_LIBRARY
            if recipe.get("meal_type") == slot
            and not _food_is_blocked(recipe, preference, allergies, dislikes)
        ]

        # Never bypass allergy or dietary restrictions. If no safe recipe
        # exists for a meal slot, leave that slot empty rather than showing
        # a potentially unsuitable fallback.
        if not candidates:
            continue

        scored = [
            (recipe, _recipe_score(recipe, flags))
            for recipe in candidates
        ]

        scored.sort(
            key=lambda item: (
                -item[1],
                (item[0]["slug"] + str(day_number)) 
            )
        )

        # Rotate through similarly suitable recipes so the page does not
        # show the exact same meals every day.
        if scored:
            best_score = scored[0][1]
            top_pool = [item[0] for item in scored if item[1] >= best_score - 2.0]
            index = day_number % len(top_pool)
            recipe = top_pool[index]
        else:
            recipe = None

        if recipe:
            matched_reasons = []
            tags = set(recipe.get("tags", []))

            if flags["anemia"] and tags.intersection({"anemia", "iron_rich"}):
                matched_reasons.append("iron-focused")
            if flags["pcos"] and tags.intersection({"pcos", "high_fiber", "protein"}):
                matched_reasons.append("PCOS wellness")
            if flags["diabetes"] and tags.intersection({"diabetes", "high_fiber", "protein"}):
                matched_reasons.append("fibre/protein focused")
            if flags["thyroid"] and tags.intersection({"thyroid", "balanced", "protein"}):
                matched_reasons.append("balanced nutrition")

            if not matched_reasons:
                matched_reasons.append("balanced wellness")

            chosen.append({
                **recipe,
                "slot": slot,
                "label": label,
                "time": time,
                "icon": icon,
                "why": ", ".join(matched_reasons),
            })

    focus = []
    if flags["anemia"]:
        focus.append(("🩸", "Iron Support", "Choose iron-rich foods and pair plant sources with vitamin-C-rich foods."))
    if flags["pcos"]:
        focus.append(("🌸", "Balanced PCOS Wellness", "Favor protein, vegetables and high-fibre carbohydrates."))
    if flags["diabetes"]:
        focus.append(("🩺", "Blood-Sugar Friendly", "Favor fibre-rich meals and limit added-sugar foods and drinks."))
    if flags["thyroid"]:
        focus.append(("🦋", "Balanced Nutrition", "Choose balanced meals with protein, vegetables and whole foods."))
    if not focus:
        focus.append(("🥗", "Balanced Wellness", "Choose varied vegetables, protein, whole grains and regular hydration."))

    return {
        "meals": chosen,
        "focus": focus,
        "preference": preference,
        "allergies": allergies,
        "dislikes": dislikes,
        "risk_flags": flags,
        "recipe_count": len(RECIPE_LIBRARY),
    }


def build_wellness_plan(profile, predictions, meal_plan=None):
    profile = _as_dict(profile)
    predictions = _as_dict(predictions)

    flags = _risk_flags(predictions)

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
