"""Gold Mine: a tiny game for the watched hour. Run it with:  python game.py

You dig for gold, buy a better pick, and save. Everything the tests check is in the functions below.
"""
import json, os, random

SAVE = "save.json"
PICKS = {"wood": (1, 0), "iron": (3, 20), "steel": (6, 60)}      # name: (gold per dig, price)


def new_game():
    return {"gold": 0, "pick": "wood", "digs": 0}


def dig(state, luck=None):
    """One dig. A lucky dig (1 in 10) finds double."""
    luck = random.random() if luck is None else luck
    found = PICKS[state["pick"]][0] * (2 if luck < 0.1 else 1)
    state["gold"] += found
    state["digs"] += 1
    return found


def buy(state, pick):
    """Buy a pick if there is enough gold. True when bought."""
    if pick not in PICKS or pick == state["pick"]:
        return False
    price = PICKS[pick][1]
    if state["gold"] < price:
        return False
    state["gold"] -= price
    state["pick"] = pick
    return True


def save(state, path=SAVE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def load(path=SAVE):
    if not os.path.exists(path):
        return new_game()
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    if state.get("gold", 0) < 0 or state.get("pick") not in PICKS:
        return new_game()                                         # a broken save starts a new game
    return state


def main():
    state = load()
    print("Gold Mine. Type: dig, buy iron, buy steel, save, quit")
    while True:
        print(f"gold {state['gold']}  pick {state['pick']}  digs {state['digs']}")
        cmd = input("> ").strip().lower()
        if cmd == "dig":
            print(f"You found {dig(state)} gold.")
        elif cmd.startswith("buy "):
            print("Bought." if buy(state, cmd[4:]) else "You can't buy that.")
        elif cmd == "save":
            save(state); print("Saved.")
        elif cmd == "quit":
            save(state); break


if __name__ == "__main__":
    main()
