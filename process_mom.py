import os
import json

def load_mom_data(file_path: str = "mom_data.json") -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_key(key: str) -> str:
    """Remove trailing spaces from dictionary keys."""
    return key.strip()

def normalize_mom_data(raw_data: dict) -> dict:
    """Normalize MOM data by stripping whitespace from keys and values."""
    cleaned = {}
    for k, v in raw_data.items():
        key = clean_key(k)
        if isinstance(v, str):
            cleaned[key] = v.strip()
        elif isinstance(v, list):
            cleaned[key] = [
                {clean_key(ik): iv.strip() if isinstance(iv, str) else iv for ik, iv in item.items()}
                for item in v
            ]
        else:
            cleaned[key] = v
    return cleaned

def get_action_items(mom: dict) -> list:
    """Extract all action items (remarks) that require follow-up."""
    actions = []
    for item in mom.get("items", []):
        site = item.get("site", "").strip()
        topic = item.get("topic", "").strip()
        desc = item.get("desc", "").strip()
        rem = item.get("rem", "").strip()
        if rem and not any(skip in rem.lower() for skip in ["in progress", "na", "n/a"]):
            actions.append({
                "site": site,
                "topic": topic,
                "description": desc,
                "action_required": rem
            })
    return actions

if __name__ == "__main__":
    # Load and process MOM
    raw = load_mom_data()
    mom = normalize_mom_data(raw)
    
    # Get pending action items
    pending_actions = get_action_items(mom)
    
    # Output results
    print(json.dumps(pending_actions, indent=2))