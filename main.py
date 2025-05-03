
# ==========================================================================================
# author: Zambelli Greminger Maximiliano

import os
from dotenv import load_dotenv
import argparse
import pandas as pd
import requests
import yaml

load_dotenv()  # reads .env into os.environ

TRELLO_KEY   = os.environ.get("TRELLO_KEY")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN")

if not TRELLO_KEY or not TRELLO_TOKEN:
    raise RuntimeError("Missing TRELLO_KEY or TRELLO_TOKEN in environment")

# ==========================================================================================
# FUNCTIONS


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_card_data(row, cfg):

    # list id, where to put the card
    # this is set in the config.yaml, so we can use the same list for all cards
    list_id = cfg["list_id"]

    # 1) Title & Description via str.format
    # so we fill the template with the row data
    title = cfg["title_template"].format(**row)

    desc  = cfg["description_template"].format(**row)

    # 2) Members lookup
    # we get the member name from the row and look it up in the member_map
    # multiple members can be handled in the config.yaml with a composite key and list of member ids
    member_key = row.get("Member", "")
    member_key = str(member_key).strip()  # remove leading/trailing whitespace
    # if the member is not found, we set it to None (no member)
    if member_key == "":
        members = None
        print(f"[WARNING] No member found for row {row}")
    else:
        members  = cfg["member_map"].get(member_key, None)

    # 3) Labels lookup
    label_key = row.get("Label", "")
    label_key = str(label_key).strip()  # remove leading/trailing whitespace
    # if the label is not found, we set it to None (no label)
    if label_key == "":
        labels = None
        print(f"[WARNING] No label found for row {row}")

    else:
        labels    = cfg["label_map"].get(label_key, None)

    return list_id, title, desc, members, labels

def add_checklists_to_card(card_id: str, cfg: dict, debug: bool = False):
    """
    For each checklist in cfg['checklists'], create the checklist on Trello,
    then add each item (unchecked) to it.
    """
    for checklist in cfg.get("checklists", []):
        # 1) create the empty checklist container
        cl_params = {
            "key":    TRELLO_KEY,
            "token":  TRELLO_TOKEN,
            "idCard": card_id,
            "name":   checklist["name"],
        }
        cl_resp = requests.post(
            "https://api.trello.com/1/checklists",
            params=cl_params
        )
        cl_resp.raise_for_status()
        cl_id = cl_resp.json()["id"]
        if debug:
            print(f"[DEBUG] Created checklist '{checklist['name']}' (id={cl_id})")

        # 2) add each item, all start unchecked
        for item_name in checklist.get("items", []):
            item_params = {
                "key":         TRELLO_KEY,
                "token":       TRELLO_TOKEN,
                "idChecklist": cl_id,
                "name":        item_name,
                "checked":     "false",
            }
            item_resp = requests.post(
                f"https://api.trello.com/1/checklists/{cl_id}/checkItems",
                params=item_params
            )
            item_resp.raise_for_status()
            if debug:
                print(f"[DEBUG]   ↳ Added item '{item_name}'")


def import_to_trello(file_path, cfg, debug=False):
    try:
        if os.path.exists(file_path):
            data = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
        else:
            raise FileNotFoundError(f"File not found: {file_path}")
        
        for idx, row in data.iterrows():
            list_id, title, desc, members, labels = build_card_data(row, cfg)

            params = {
                "key":   TRELLO_KEY,
                "token": TRELLO_TOKEN,
                "idList":list_id,
                "name":  title,
                "desc":  desc,
            }
            if members:
                params["idMembers"] = members
            if labels:
                params["idLabels"] = labels

            if debug:
                print(f"[DEBUG] Creating card: {title}")
            
            try:
                resp = requests.post("https://api.trello.com/1/cards", params=params)
                resp.raise_for_status()
                card_id = resp.json()["id"]

                # add checklists
                if cfg.get("checklists"):
                    add_checklists_to_card(card_id, cfg, debug=debug)
            
            except requests.RequestException as e:
                print(f"[ERROR] Failed at row {idx}: {e}")
                continue

    except Exception as e:
        print(f"[ERROR] Exception in import_to_trello {e}")
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-upload cards to Trello")
    parser.add_argument("file", help="path to .csv or .xlsx")
    parser.add_argument("--config", default="config.yaml", help="path to config file")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    import_to_trello(args.file, cfg, debug=args.debug)
